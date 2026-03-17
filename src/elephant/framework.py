# The framework for scheduling tasks to get information from the websites
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import schedule


@dataclass
class HarvesterResult:
    tags: dict[str, str]
    data: list[dict]


class Store:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def save(self, dataset_name: str, result: HarvesterResult):
        if not result.data:
            return

        # Build partition path from tags
        # Example: tags = {"ticker": "7203.T", "date": "2026-03-16"}
        # Note: tags must contain "date" as per spec
        parts = [f"{k}={v}" for k, v in result.tags.items()]
        partition_path = os.path.join(*parts)

        target_dir = os.path.join(self.root_dir, f"dataset={dataset_name}", partition_path)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, "data.parquet")

        new_df = pd.DataFrame(result.data)

        if os.path.exists(file_path):
            try:
                existing_df = pd.read_parquet(file_path)
                if "id" in new_df.columns and "id" in existing_df.columns:
                    # Deduplicate based on 'id'
                    combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["id"], keep="last")
                    combined_df.to_parquet(file_path, index=False)
                else:
                    new_df.to_parquet(file_path, index=False)
            except Exception as e:
                logging.error(f"Error saving to {file_path}: {e}")
                new_df.to_parquet(file_path, index=False)
        else:
            new_df.to_parquet(file_path, index=False)


class Harvester:
    def __init__(self, store: Store):
        self.store = store

    def get_url(self, params: dict) -> str:
        pass

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        # 1. send the request from headless browser
        # 2. scrape the HTML to get info
        # 3. react if page navigation, scrolling is needed
        # 4. repeat 2
        pass

    async def start(self, params: dict):
        url = self.get_url(params)
        scrape_result = await self.scrape(url, params)
        for dataset_name, result in scrape_result.items():
            self.store.save(dataset_name, result)


@dataclass
class HarvesterTask:
    harvester: Harvester
    scheduled_at: datetime
    args: dict


class Planner:
    def create(self) -> list[HarvesterTask]:
        return []


class Scheduler:
    def __init__(self, planner: Planner):
        self.planner = planner

    def plan(self):
        logging.info("Generating and scheduling daily plan...")
        schedule.clear("daily-scrapes")
        tasks = self.planner.create()
        for task in tasks:
            time_str = task.scheduled_at.strftime("%H:%M")
            schedule.every().day.at(time_str).do(
                self._run_task, task=task
            ).tag("daily-scrapes")
        logging.info(f"Scheduled {len(tasks)} tasks.")

    def _run_task(self, task: HarvesterTask):
        try:
            # We run the async start in a new event loop or the current one
            asyncio.run(task.harvester.start(task.args))
        except Exception:
            logging.exception(f"Failed to execute task with args {task.args}")

    def start(self):
        logging.info("Starting scheduler process...")
        self.plan()
        schedule.every().day.at("01:00").do(self.plan)
        while True:
            schedule.run_pending()
            time.sleep(1)
