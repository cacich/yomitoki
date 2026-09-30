import asyncio

import pytest

from app.engine import auto_inpainting_size
from app.worker import EngineWorker


def test_auto_inpainting_size_by_vram():
    # 實測 GTX 1650（4 GB）用 1536 時峰值 4.3 GB，會超過實體容量
    assert auto_inpainting_size("cuda", 4.0) == 1024
    assert auto_inpainting_size("cuda", 6.0) == 1536
    assert auto_inpainting_size("cuda", 8.0) == 1536
    assert auto_inpainting_size("cuda", 12.0) == 2048
    assert auto_inpainting_size("cpu", None) == 1024
    assert auto_inpainting_size("cuda", None) == 1024


def test_worker_runs_tasks_in_order_and_cleans_up_after_each():
    events = []
    worker = EngineWorker(lambda: "engine", cleanup=lambda: events.append("cleanup"))
    worker.start(timeout=5)
    try:
        async def ok(engine):
            events.append(f"ok:{engine}")
            await asyncio.sleep(0)
            return 42

        async def boom(engine):
            events.append("boom")
            raise RuntimeError("x")

        assert worker.submit(ok).result(timeout=5) == 42
        with pytest.raises(RuntimeError):
            worker.submit(boom).result(timeout=5)
        # 啟動時清一次，之後每件工作（包括失敗的）結束都要清
        assert events == ["cleanup", "ok:engine", "cleanup", "boom", "cleanup"]
    finally:
        worker.stop()


def test_worker_reports_startup_failure():
    def broken():
        raise OSError("no gpu")

    with pytest.raises(OSError):
        EngineWorker(broken).start(timeout=5)
