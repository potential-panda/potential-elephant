import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import schedule

from elephant.config import SOURCE_REGISTRY_FILE
from elephant.source.availability import check_sources
from elephant.source.harvest import SourceHarvestTask, harvest_task
from elephant.source.registry import SourceRegistry
from elephant.source.scheduler import create_daily_plan


class SourceSchedulerService:
    """In-process scheduler for api2.

    The service owns one lightweight scheduling loop plus a small worker pool.
    It is designed to run inside the api2 process so deployment only needs one
    systemd service.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._tasks: list[SourceHarvestTask] = []
        self._started_at: str | None = None
        self._last_planned_at: str | None = None
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._availability_submitted = 0
        self._availability_completed = 0
        self._availability_failed = 0
        self._last_availability_check_at: str | None = None

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="source-harvest")
            self._thread = threading.Thread(target=self._loop, name="source-scheduler", daemon=True)
            self._started_at = datetime.now().isoformat(timespec="seconds")
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return False
            self._stop_event.set()
            schedule.clear("source-v2")
            executor = self._executor
            self._executor = None
        if executor:
            executor.shutdown(wait=False, cancel_futures=False)
        return True

    def replan(self) -> int:
        return self._plan_day()

    def status(self) -> dict:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            tasks = list(self._tasks)
            return {
                "running": running,
                "started_at": self._started_at,
                "last_planned_at": self._last_planned_at,
                "planned_tasks": len(tasks),
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
                "availability_submitted": self._availability_submitted,
                "availability_completed": self._availability_completed,
                "availability_failed": self._availability_failed,
                "last_availability_check_at": self._last_availability_check_at,
                "max_workers": self.max_workers,
                "next_tasks": [
                    {
                        "source_id": t.source_id,
                        "scope": t.scope,
                        "ticker": t.ticker,
                        "url": t.url,
                        "scheduled_at": t.scheduled_at.isoformat(),
                    }
                    for t in tasks[:20]
                ],
            }

    def _loop(self) -> None:
        logging.info("[api2 source scheduler] starting")
        self._plan_day()
        schedule.every().day.at("01:00").do(self._plan_day).tag("source-v2")
        schedule.every().sunday.at("03:00").do(self._submit_availability_check).tag("source-v2")
        while not self._stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
        logging.info("[api2 source scheduler] stopped")

    def _plan_day(self) -> int:
        registry = SourceRegistry(SOURCE_REGISTRY_FILE)
        tasks = create_daily_plan(registry=registry)
        schedule.clear("source-v2")
        schedule.every().day.at("01:00").do(self._plan_day).tag("source-v2")
        schedule.every().sunday.at("03:00").do(self._submit_availability_check).tag("source-v2")
        for task in tasks:
            schedule.every().day.at(task.scheduled_at.strftime("%H:%M")).do(self._submit_task, task=task).tag("source-v2")
        with self._lock:
            self._tasks = tasks
            self._last_planned_at = datetime.now().isoformat(timespec="seconds")
        logging.info("[api2 source scheduler] planned %d tasks", len(tasks))
        return len(tasks)

    def _submit_task(self, task: SourceHarvestTask):
        with self._lock:
            executor = self._executor
            self._submitted += 1
        if not executor:
            return schedule.CancelJob
        executor.submit(self._run_task, task)
        return schedule.CancelJob

    def _submit_availability_check(self):
        with self._lock:
            executor = self._executor
            self._availability_submitted += 1
        if not executor:
            return schedule.CancelJob
        executor.submit(self._run_availability_check)
        return schedule.CancelJob

    def _run_availability_check(self) -> None:
        try:
            asyncio.run(check_sources(registry=SourceRegistry(SOURCE_REGISTRY_FILE)))
            with self._lock:
                self._availability_completed += 1
                self._last_availability_check_at = datetime.now().isoformat(timespec="seconds")
        except Exception:
            logging.exception("[api2 source scheduler] availability check failed")
            with self._lock:
                self._availability_failed += 1

    def _run_task(self, task: SourceHarvestTask) -> None:
        try:
            asyncio.run(harvest_task(task))
            with self._lock:
                self._completed += 1
        except Exception:
            logging.exception("[api2 source scheduler] task failed: %s %s", task.source_id, task.ticker or "market")
            with self._lock:
                self._failed += 1


source_scheduler_service = SourceSchedulerService()
