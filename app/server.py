"""本機伺服器：翻譯 API、介面用的 /api，以及建置好的網頁介面。

只綁 127.0.0.1，不對外開放；模型在啟動時載入並常駐在引擎執行緒。

    GET  /health                       狀態：運算裝置、Claude Code 是否可用
    POST /translate                    送 PNG（body 或 multipart 的 file 欄位），回傳譯好的 PNG
         ?series=<作品名>&episode=<話數>  選填：帶入作品記憶，並把截圖存進該話資料夾
    /api/…                             介面用的 REST API（見 app/api.py）
    /                                  網頁介面（ui/dist）

安全：瀏覽器裡的任何網頁都能對 localhost 發請求，所以
- 只接受 Host 為 127.0.0.1 / localhost 的請求（擋 DNS rebinding）
- 會改變資料的請求必須帶 X-Yomitoki-Client 標頭；跨站請求帶自訂標頭會先送 preflight，
  而伺服器不回 CORS 許可，瀏覽器就會擋下
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image, UnidentifiedImageError

from . import __version__, paths
from .api import build_router, mount_fonts
from .jobs import JobManager
from .languages import get_source, get_target
from .pipeline import episode_images, output_image, translate_image
from .series import Series
from .translate import ClaudeCodeTranslator, ClaudeNotInstalledError, ClaudeNotLoggedInError, TranslationError
from .worker import EngineWorker

log = logging.getLogger("yomitoki.server")
MAX_UPLOAD = 40 * 1024 * 1024
CLIENT_HEADER = "x-yomitoki-client"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
UI_DIST = paths.REPO_ROOT / "ui" / "dist"


def create_app(device: str = "auto", model: str | None = None, engine=None, ui_dist: Path | None = UI_DIST) -> FastAPI:
    translator = ClaudeCodeTranslator(model=model)

    def make_engine():
        if engine is not None:
            return engine
        from .engine import Engine, EngineSettings

        return Engine(EngineSettings(device=device))

    async def prepare(e):
        await e.prepare(get_source("ja"))

    def cleanup():
        if engine is None:  # 測試用的假引擎不需要
            from .engine import release_gpu_memory

            release_gpu_memory()

    worker = EngineWorker(make_engine, prepare, cleanup)
    state: dict = {"translator": translator, "worker": worker, "jobs": JobManager(worker, translator)}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker.start()
        state["engine_device"] = getattr(worker.engine, "device", None)
        yield
        worker.stop()

    app = FastAPI(title="Yomitoki", version=__version__, lifespan=lifespan)
    app.state.yomitoki = state

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in ALLOWED_HOSTS and host != "::1":
            return JSONResponse({"detail": "只接受本機請求"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CLIENT_HEADER):
            return JSONResponse({"detail": f"缺少 {CLIENT_HEADER} 標頭"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok", "device": state.get("engine_device"), "claude_code": bool(translator.executable)}

    @app.post("/translate")
    async def translate(request: Request, series: str | None = None, episode: str | None = None,
                        source: str | None = None, target: str | None = None):
        data = await _read_image_bytes(request)
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(415, "上傳的檔案不是圖片")
        try:
            s = Series.open(series) if series else None
            if source:
                get_source(source)
            if target:
                get_target(target)
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(400, str(e))

        async def task(engine):
            with tempfile.TemporaryDirectory(prefix="yomitoki-api-") as tmp:
                if s and episode:
                    # 存進該話資料夾，之後可以整話重新翻譯或重新嵌字
                    ep = s.episode_dir(episode)
                    ep.mkdir(parents=True, exist_ok=True)
                    image = ep / f"{len(episode_images(ep)) + 1:03d}.png"
                    out = output_image(image, get_target(target or s.settings.target_lang))
                else:
                    image = Path(tmp) / "screenshot.png"
                    out = Path(tmp) / "result.png"
                Image.open(io.BytesIO(data)).convert("RGB").save(image)
                report = await translate_image(engine, translator, image, series=s, source=source,
                                               target=target, out=out)
                saved = (image.parent.name, image.stem) if s and episode else None
                return report, out.read_bytes(), saved

        try:
            report, png, saved = await worker.run(task)
        except ClaudeNotInstalledError as e:
            raise HTTPException(503, str(e))
        except ClaudeNotLoggedInError as e:
            raise HTTPException(401, str(e))
        except TranslationError as e:
            raise HTTPException(502, str(e))

        headers = {
            "X-Yomitoki-Regions": str(len(report.page.regions)),
            "X-Yomitoki-New-Terms": str(report.new_terms),
            # 標頭只能放 ASCII，警告以 URL 編碼的 JSON 傳回
            "X-Yomitoki-Warnings": quote(json.dumps(report.warnings, ensure_ascii=False)),
            "X-Yomitoki-Seconds": quote(json.dumps({k: round(v, 2) for k, v in report.seconds.items()})),
        }
        if saved:
            # 截圖存進了哪一話的哪一頁（插件用來開閱讀器）
            headers["X-Yomitoki-Episode"], headers["X-Yomitoki-Page"] = saved
        return Response(png, media_type="image/png", headers=headers)

    app.include_router(build_router(state))
    mount_fonts(app)
    if ui_dist and (ui_dist / "index.html").is_file():
        _mount_ui(app, ui_dist)
    return app


def _mount_ui(app: FastAPI, dist: Path) -> None:
    """單頁應用：找得到檔案就回檔案，其餘路徑一律回 index.html。"""
    dist = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str):
        target = (dist / path).resolve()
        if path and dist in target.parents and target.is_file():
            cache = "max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(target, headers={"Cache-Control": cache})
        if path.startswith(("api/", "fonts/")):
            raise HTTPException(404)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})


async def _read_image_bytes(request: Request) -> bytes:
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(400, "multipart 表單裡缺少 file 欄位")
        data = await upload.read()
    else:
        data = await request.body()
    if not data:
        raise HTTPException(400, "沒有收到圖片")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "圖片太大（上限 40 MB）")
    return data
