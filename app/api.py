"""給介面用的 REST API（/api/…）。"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import __version__, fonts, paths
from .assets import AssetRegistry, UnknownAssetError, UnsupportedFormatError
from .languages import SOURCES, TARGETS, get_target
from .page import Page
from .pipeline import episode_images, output_image, page_json
from .series import RULES_TEMPLATE, SUMMARY_TEMPLATE, Series, episode_dirname
from .translate import ClaudeCodeTranslator

MAX_UPLOAD = 40 * 1024 * 1024
THUMB_WIDTHS = (160, 320, 640)


# ── 請求格式 ─────────────────────────────────────────────────

class SeriesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    format: str = Field("page", pattern="^(page|scroll)$")
    source_lang: str = "ja"
    target_lang: str = "zh-TW"


class EpisodeCreate(BaseModel):
    episode: str | None = None


class RunRequest(BaseModel):
    steps: list[str] = ["ocr", "translate", "render"]
    force: bool = False


class TermSet(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    category: str | None = Field(None, pattern="^(character|place|technique|item|other)$")
    note: str | None = None


class TermRef(BaseModel):
    source: str = Field(min_length=1)
    target: str | None = None


class Notes(BaseModel):
    rules: str
    summary: str


class OpenFolder(BaseModel):
    series: str | None = None
    episode: str | None = None


# ── 狀態計算 ─────────────────────────────────────────────────

def page_status(image: Path, target_code: str) -> dict:
    jp = page_json(image)
    info = {"stem": image.stem, "status": "new", "regions": 0, "translated_regions": 0}
    if not jp.is_file():
        return info
    page = Page.load(jp)
    info["regions"] = len(page.regions)
    info["translated_regions"] = sum(1 for r in page.regions if r.translation)
    out = output_image(image, get_target(target_code))
    if page.regions and not page.is_translated:
        info["status"] = "ocr"
    elif out.is_file() and out.stat().st_mtime >= jp.stat().st_mtime:
        info["status"] = "done"
    else:
        info["status"] = "translated"
    return info


def episode_summary(series: Series, ep_dir: Path, with_pages: bool = False) -> dict:
    target = series.settings.target_lang
    pages = [page_status(img, target) for img in episode_images(ep_dir)]
    counts = {k: sum(1 for p in pages if p["status"] == k) for k in ("new", "ocr", "translated", "done")}
    status = "empty" if not pages else "done" if counts["done"] == len(pages) else "partial" if counts["done"] else "todo"
    label = ep_dir.name[2:].lstrip("0") or "0"
    out = {"id": ep_dir.name, "label": label, "pages": len(pages), "counts": counts, "status": status}
    if with_pages:
        for p in pages:
            p.update(_page_urls(series, ep_dir, p["stem"], p["status"] == "done"))
        out["pages_detail"] = pages
    return out


def _v(path: Path) -> str:
    return str(int(path.stat().st_mtime * 1000)) if path.is_file() else "0"


def _page_urls(series: Series, ep_dir: Path, stem: str, done: bool) -> dict:
    image = _find_image(ep_dir, stem)
    base = f"/api/series/{_q(series.name)}/episodes/{ep_dir.name}/pages/{stem}/image"
    out = output_image(image, get_target(series.settings.target_lang)) if image else None
    return {
        "original": f"{base}?kind=original&v={_v(image) if image else 0}",
        "translated": f"{base}?kind=translated&v={_v(out)}" if done and out else None,
        "thumb": f"{base}?kind={'translated' if done else 'original'}&w=320&v={_v(out) if done else _v(image)}",
    }


def _q(s: str) -> str:
    return quote(s, safe="")


def _find_image(ep_dir: Path, stem: str) -> Path | None:
    if not re.fullmatch(r"[\w\-]+", stem):
        return None
    return next((p for p in episode_images(ep_dir) if p.stem == stem), None)


def _series(name: str) -> Series:
    try:
        return Series.open(name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e))


def _episode_dir(series: Series, episode: str) -> Path:
    try:
        ep = series.episode_dir(episode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ep.is_dir():
        raise HTTPException(404, f"找不到 {episode_dirname(episode)}")
    return ep


def _thumbnail(src: Path, width: int) -> Path:
    thumb = src.parent / ".cache" / "thumbs" / f"{src.stem}.{src.parent.name}.{width}.jpg"
    if thumb.is_file() and thumb.stat().st_mtime >= src.stat().st_mtime:
        return thumb
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((width, width * 4), Image.LANCZOS)
        im.save(thumb, quality=85)
    return thumb


def _cover(series: Series) -> str | None:
    """封面：第一話第一頁的縮圖。"""
    for ep in series.episodes():
        imgs = episode_images(series.root / ep)
        if imgs:
            return f"/api/series/{_q(series.name)}/episodes/{ep}/pages/{imgs[0].stem}/image?kind=original&w=320&v={_v(imgs[0])}"
    return None


def _claude_status(translator: ClaudeCodeTranslator, cache: dict) -> dict:
    now = time.time()
    if cache.get("at", 0) > now - 30:
        return cache["value"]
    value = {"installed": bool(translator.executable), "version": None, "logged_in": None, "subscription": None}
    if translator.executable:
        try:
            v = subprocess.run([translator.executable, "--version"], capture_output=True, text=True,
                               encoding="utf-8", timeout=15)
            value["version"] = v.stdout.strip().split(" ")[0] or None
            s = subprocess.run([translator.executable, "auth", "status", "--json"], capture_output=True, text=True,
                               encoding="utf-8", timeout=15)
            data = json.loads(s.stdout or "{}")
            # 只取需要的欄位，不把帳號 email 等資訊送到介面
            value["logged_in"] = bool(data.get("loggedIn"))
            value["subscription"] = data.get("subscriptionType")
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    cache.update(at=now, value=value)
    return value


def _gpu_status(device: str | None) -> dict:
    try:
        import torch

        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            return {"cuda": True, "name": p.name, "vram_gb": round(p.total_memory / 2**30, 1), "device": device}
        return {"cuda": False, "name": None, "vram_gb": None, "device": device}
    except ImportError:
        return {"cuda": False, "name": None, "vram_gb": None, "device": device}


# ── 路由 ─────────────────────────────────────────────────────

def build_router(state: dict) -> APIRouter:
    r = APIRouter(prefix="/api")
    assets = state.get("assets") or AssetRegistry()
    claude_cache: dict = {}

    @r.get("/status")
    def status():
        eng = state.get("engine_device")
        return {
            "version": __version__,
            "gpu": _gpu_status(eng),
            "claude": _claude_status(state["translator"], claude_cache),
            "data_home": str(paths.data_home()),
            "models_dir": str(paths.models_dir()),
            "languages": {
                "sources": [{"code": k, "name": v.name, "status": v.status, "reading_rtl": v.reading_rtl}
                            for k, v in SOURCES.items()],
                "targets": [{"code": k, "name": v.name, "status": v.status} for k, v in TARGETS.items()],
            },
        }

    # 作品
    @r.get("/series")
    def list_series():
        out = []
        for s in Series.list():
            episodes = [episode_summary(s, s.root / ep) for ep in s.episodes()]
            g = s.glossary()
            out.append({
                "name": s.name, "settings": vars(s.settings), "episodes": len(episodes),
                "pages": sum(e["pages"] for e in episodes),
                "done_pages": sum(e["counts"]["done"] for e in episodes),
                "pending_terms": len(g.pending), "cover": _cover(s),
            })
        return out

    @r.post("/series", status_code=201)
    def create_series(body: SeriesCreate):
        try:
            s = Series.create(body.name.strip(), format=body.format, source_lang=body.source_lang,
                              target_lang=body.target_lang)
        except FileExistsError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"name": s.name}

    @r.get("/series/{name}")
    def get_series(name: str):
        s = _series(name)
        g = s.glossary()
        return {
            "name": s.name, "settings": vars(s.settings),
            "episodes": [episode_summary(s, s.root / ep) for ep in s.episodes()],
            "glossary": {"confirmed": len(g.confirmed), "pending": len(g.pending)},
            "cover": _cover(s),
            "jobs": [j.to_dict() for j in state["jobs"].list(s.name)[:5]],
        }

    @r.post("/series/{name}/episodes", status_code=201)
    def create_episode(name: str, body: EpisodeCreate):
        s = _series(name)
        if body.episode:
            ep = s.episode_dir(body.episode)
        else:
            nums = [int(e[2:]) for e in s.episodes() if e[2:].isdigit()]
            ep = s.episode_dir(max(nums, default=0) + 1)
        ep.mkdir(parents=True, exist_ok=True)
        return episode_summary(s, ep)

    @r.get("/series/{name}/episodes/{episode}")
    def get_episode(name: str, episode: str):
        s = _series(name)
        ep = _episode_dir(s, episode)
        out = episode_summary(s, ep, with_pages=True)
        job = state["jobs"].active_for(s.name, ep.name)
        out["job"] = job.to_dict() if job else None
        return out

    @r.post("/series/{name}/episodes/{episode}/pages")
    async def upload_pages(name: str, episode: str, files: list[UploadFile]):
        s = _series(name)
        ep = _episode_dir(s, episode)
        existing = [int(p.stem) for p in episode_images(ep) if p.stem.isdigit()]
        n = max(existing, default=0)
        saved = []
        for f in sorted(files, key=lambda f: _natural_key(f.filename or "")):
            data = await f.read()
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, f"{f.filename} 超過 40 MB")
            try:
                with Image.open(io.BytesIO(data)) as im:
                    im = im.convert("RGB")
                    n += 1
                    target = ep / f"{n:03d}.png"
                    im.save(target)
                    saved.append(target.stem)
            except (UnidentifiedImageError, OSError):
                raise HTTPException(415, f"{f.filename} 不是圖片")
        return {"saved": saved}

    @r.get("/series/{name}/episodes/{episode}/pages/{stem}/image")
    def page_image(name: str, episode: str, stem: str, kind: str = "original", w: int | None = None):
        s = _series(name)
        ep = _episode_dir(s, episode)
        image = _find_image(ep, stem)
        if image is None:
            raise HTTPException(404, "找不到這一頁")
        src = image if kind == "original" else output_image(image, get_target(s.settings.target_lang))
        if not src.is_file():
            raise HTTPException(404, "這一頁還沒有譯圖")
        if w:
            src = _thumbnail(src, min(THUMB_WIDTHS, key=lambda t: abs(t - w)))
        return FileResponse(src, headers={"Cache-Control": "no-cache"})

    @r.post("/series/{name}/episodes/{episode}/run", status_code=202)
    def run_episode(name: str, episode: str, body: RunRequest):
        s = _series(name)
        ep = _episode_dir(s, episode)
        if not episode_images(ep):
            raise HTTPException(400, "這一話還沒有截圖")
        try:
            job = state["jobs"].submit(s, ep.name, body.steps, body.force)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return job.to_dict()

    @r.get("/jobs/{job_id}")
    def get_job(job_id: str):
        job = state["jobs"].jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "找不到這個工作")
        return job.to_dict()

    # 詞彙表與規則
    @r.get("/series/{name}/glossary")
    def get_glossary(name: str):
        s = _series(name)
        g = s.glossary()
        terms = []
        for t in sorted(g.terms, key=lambda t: (t.status != "pending", t.category, t.source)):
            item = vars(t).copy()
            item["thumb"] = None
            m = re.fullmatch(r"(ep[\w.\-]+)/([\w\-]+)", t.first_seen or "")
            if m and (s.root / m.group(1)).is_dir() and _find_image(s.root / m.group(1), m.group(2)):
                item["thumb"] = f"/api/series/{_q(s.name)}/episodes/{m.group(1)}/pages/{m.group(2)}/image?kind=original&w=160"
            terms.append(item)
        return {"target_lang": s.settings.target_lang, "terms": terms}

    @r.post("/series/{name}/glossary/set")
    def set_term(name: str, body: TermSet):
        s = _series(name)
        g = s.glossary()
        g.set(body.source.strip(), body.target.strip(), category=body.category, note=body.note)
        g.save()
        return get_glossary(name)

    @r.post("/series/{name}/glossary/confirm")
    def confirm_term(name: str, body: TermRef):
        s = _series(name)
        g = s.glossary()
        try:
            if body.target:
                g.set(body.source, body.target.strip())
            else:
                g.confirm(body.source)
        except KeyError:
            raise HTTPException(404, f"詞彙表裡沒有「{body.source}」")
        g.save()
        return get_glossary(name)

    @r.post("/series/{name}/glossary/remove")
    def remove_term(name: str, body: TermRef):
        s = _series(name)
        g = s.glossary()
        g.remove(body.source)
        g.save()
        return get_glossary(name)

    @r.get("/series/{name}/notes")
    def get_notes(name: str):
        s = _series(name)
        return {"rules": (s.root / "rules.md").read_text(encoding="utf-8"),
                "summary": (s.root / "summary.md").read_text(encoding="utf-8")}

    @r.put("/series/{name}/notes")
    def put_notes(name: str, body: Notes):
        s = _series(name)
        (s.root / "rules.md").write_text(body.rules or RULES_TEMPLATE, encoding="utf-8")
        (s.root / "summary.md").write_text(body.summary or SUMMARY_TEMPLATE, encoding="utf-8")
        return get_notes(name)

    # 外觀素材
    @r.get("/assets")
    def list_assets():
        out = []
        for asset_id in assets.specs:
            info = assets.inspect(asset_id)
            out.append({
                "id": asset_id, "purpose": info.spec.purpose, "purpose_en": info.spec.purpose_en,
                "size": info.spec.size, "background": info.spec.background, "source": info.source,
                "format": info.format, "pixel_size": info.pixel_size, "warnings": info.warnings,
                "url": f"/api/assets/{asset_id}/file?v={_v(info.path)}",
            })
        return out

    @r.get("/assets/{asset_id}/file")
    def asset_file(asset_id: str):
        try:
            path = assets.resolve(asset_id)
        except UnknownAssetError:
            raise HTTPException(404, "沒有這個素材代號")
        media = "image/svg+xml" if path.suffix == ".svg" else None
        return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})

    @r.post("/assets/{asset_id}")
    async def replace_asset(asset_id: str, file: UploadFile):
        suffix = Path(file.filename or "").suffix.lower()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / f"upload{suffix}"
            src.write_bytes(await file.read())
            try:
                assets.replace(asset_id, src)
            except UnknownAssetError:
                raise HTTPException(404, "沒有這個素材代號")
            except UnsupportedFormatError as e:
                raise HTTPException(415, str(e))
        return list_assets()

    @r.delete("/assets/{asset_id}")
    def restore_asset(asset_id: str):
        try:
            assets.restore_default(asset_id)
        except UnknownAssetError:
            raise HTTPException(404, "沒有這個素材代號")
        return list_assets()

    @r.post("/open-folder")
    def open_folder(body: OpenFolder):
        """在檔案總管打開作品或話數資料夾（只限 Yomitoki 的資料夾）。"""
        folder = paths.data_home()
        if body.series:
            s = _series(body.series)
            folder = _episode_dir(s, body.episode) if body.episode else s.root
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 — 只開啟本機的資料夾
        return {"path": str(folder)}

    return r


def mount_fonts(app) -> None:
    @app.get("/fonts/{font_id}.ttf", include_in_schema=False)
    def ui_font(font_id: str):
        if font_id not in fonts.UI_FONTS:
            raise HTTPException(404)
        return FileResponse(fonts.ensure_ui_font(font_id), media_type="font/ttf",
                            headers={"Cache-Control": "max-age=31536000, immutable"})


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]

