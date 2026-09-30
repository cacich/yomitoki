"""本機翻譯 API。只綁 127.0.0.1，不對外開放；模型在啟動時載入並常駐。

    GET  /health                       狀態：運算裝置、Claude Code 是否可用
    POST /translate                    送 PNG（body 或 multipart 的 file 欄位），回傳譯好的 PNG
         ?series=<作品名>&episode=<話數>  選填：帶入作品記憶，並把截圖存進該話資料夾
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from .languages import get_source, get_target
from .pipeline import episode_images, output_image, translate_image
from .series import Series
from .translate import ClaudeCodeTranslator, ClaudeNotInstalledError, ClaudeNotLoggedInError, TranslationError

log = logging.getLogger("yomitoki.server")
MAX_UPLOAD = 40 * 1024 * 1024


def create_app(device: str = "auto", model: str | None = None, engine=None) -> FastAPI:
    state: dict = {"engine": engine, "translator": ClaudeCodeTranslator(model=model), "lock": asyncio.Lock()}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["engine"] is None:
            from .engine import Engine, EngineSettings

            state["engine"] = Engine(EngineSettings(device=device))
            await state["engine"].prepare(get_source("ja"))
        yield

    app = FastAPI(title="Yomitoki", version="0.0.1", lifespan=lifespan)

    @app.get("/health")
    async def health():
        eng = state["engine"]
        return {
            "status": "ok",
            "device": getattr(eng, "device", None),
            "claude_code": bool(state["translator"].executable),
        }

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

        async with state["lock"]:  # 顯卡一次只處理一張
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
                try:
                    report = await translate_image(state["engine"], state["translator"], image, series=s,
                                                   source=source, target=target, out=out)
                except ClaudeNotInstalledError as e:
                    raise HTTPException(503, str(e))
                except ClaudeNotLoggedInError as e:
                    raise HTTPException(401, str(e))
                except TranslationError as e:
                    raise HTTPException(502, str(e))
                png = out.read_bytes()

        headers = {
            "X-Yomitoki-Regions": str(len(report.page.regions)),
            "X-Yomitoki-New-Terms": str(report.new_terms),
            # 標頭只能放 ASCII，警告以 URL 編碼的 JSON 傳回
            "X-Yomitoki-Warnings": quote(json.dumps(report.warnings, ensure_ascii=False)),
            "X-Yomitoki-Seconds": quote(json.dumps({k: round(v, 2) for k, v in report.seconds.items()})),
        }
        return Response(png, media_type="image/png", headers=headers)

    return app


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
