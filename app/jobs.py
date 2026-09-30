"""背景工作：整話 OCR → 翻譯 → 嵌字，介面輪詢進度。"""

from __future__ import annotations

import asyncio
import itertools
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Literal

from . import pipeline
from .series import Series
from .translate import ClaudeCodeTranslator, TranslationError
from .worker import EngineWorker

Step = Literal["ocr", "translate", "render"]
STEPS: tuple[Step, ...] = ("ocr", "translate", "render")


@dataclass
class Job:
    id: str
    series: str
    episode: str
    steps: list[str]
    force: bool = False
    status: Literal["queued", "running", "done", "error"] = "queued"
    step: str | None = None
    log: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    new_terms: int = 0
    error: str | None = None
    created: float = field(default_factory=time.time)
    finished: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class JobManager:
    def __init__(self, worker: EngineWorker, translator: ClaudeCodeTranslator, keep: int = 50):
        self.worker = worker
        self.translator = translator
        self.jobs: dict[str, Job] = {}
        self._ids = itertools.count(1)
        self._keep = keep

    def submit(self, series: Series, episode: str, steps: list[str], force: bool = False) -> Job:
        steps = [s for s in STEPS if s in steps]
        if not steps:
            raise ValueError("至少要選一個步驟")
        active = self.active_for(series.name, episode)
        if active:
            return active
        job = Job(id=str(next(self._ids)), series=series.name, episode=episode, steps=steps, force=force)
        self.jobs[job.id] = job
        self._trim()
        self.worker.submit(lambda engine: self._run(job, series, engine))
        return job

    def active_for(self, series: str, episode: str) -> Job | None:
        return next((j for j in self.jobs.values()
                     if j.series == series and j.episode == episode and j.status in ("queued", "running")), None)

    def list(self, series: str | None = None) -> list[Job]:
        jobs = [j for j in self.jobs.values() if series is None or j.series == series]
        return sorted(jobs, key=lambda j: j.created, reverse=True)

    async def _run(self, job: Job, series: Series, engine) -> None:
        job.status = "running"
        log = job.log.append
        try:
            if "ocr" in job.steps:
                job.step = "ocr"
                await pipeline.ocr_episode(engine, series, job.episode, force=job.force, progress=log)
            if "translate" in job.steps:
                job.step = "translate"
                warnings, added = await asyncio.to_thread(
                    pipeline.translate_episode, self.translator, series, job.episode, force=job.force, progress=log)
                job.warnings += warnings
                job.new_terms += added
            if "render" in job.steps:
                job.step = "render"
                await pipeline.render_episode(engine, series, job.episode, progress=log)
            job.status = "done"
        except (TranslationError, FileNotFoundError, ValueError) as e:
            job.status, job.error = "error", str(e)
        except Exception as e:  # noqa: BLE001 — 任何錯誤都要回報給介面
            job.status, job.error = "error", f"{type(e).__name__}: {e}"
            log(traceback.format_exc(limit=3))
        finally:
            job.step = None
            job.finished = time.time()

    def _trim(self) -> None:
        done = [j for j in self.list() if j.status in ("done", "error")]
        for j in done[self._keep:]:
            self.jobs.pop(j.id, None)
