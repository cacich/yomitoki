"""顯卡工作執行緒。

模型推論是同步運算，直接在 API 的 event loop 裡跑會卡住所有請求（包括進度查詢）。
所以引擎放在一條專屬的背景執行緒，所有用到它的工作都送到那裡，依序一次一件。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")
EngineTask = Callable[[object], Awaitable[T]]


class EngineWorker:
    def __init__(self, engine_factory: Callable[[], object], prepare: EngineTask | None = None,
                 cleanup: Callable[[], None] | None = None):
        self._factory = engine_factory
        self._prepare = prepare
        self._cleanup = cleanup  # 每件工作結束後呼叫，例如釋放顯示卡快取
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.engine = None
        self._lock: asyncio.Lock | None = None
        self._thread: threading.Thread | None = None

    def start(self, timeout: float | None = None) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, name="yomitoki-engine", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        if self._error:
            raise self._error

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self._lock = asyncio.Lock()
            self.engine = self._factory()
            if self._prepare:
                self.loop.run_until_complete(self._prepare(self.engine))
            if self._cleanup:
                self._cleanup()
        except BaseException as e:  # noqa: BLE001 — 回報給啟動的執行緒
            self._error = e
            self._ready.set()
            return
        self._ready.set()
        self.loop.run_forever()

    def submit(self, task: EngineTask[T]) -> "concurrent.futures.Future[T]":
        if not self.loop:
            raise RuntimeError("引擎尚未啟動")

        async def guarded():
            async with self._lock:
                try:
                    return await task(self.engine)
                finally:
                    if self._cleanup:
                        self._cleanup()

        return asyncio.run_coroutine_threadsafe(guarded(), self.loop)

    async def run(self, task: EngineTask[T]) -> T:
        """在 API 的 event loop 裡等待引擎執行緒完成工作。"""
        return await asyncio.wrap_future(self.submit(task))

    def stop(self) -> None:
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
