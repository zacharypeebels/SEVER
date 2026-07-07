"""SEVER Workers — executes subscription actions (sever/pause/haggle).

Beta implementation: processes action jobs from an in-memory queue with
deterministic outcomes. In production this consumes from SQS, drives
virtual-card freezes, and files merchant cancellations.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionMode(str, Enum):
    CANCEL = "cancel"
    PAUSE = "pause"
    HAGGLE = "haggle"


class JobStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ActionJob:
    subscription_id: int
    merchant: str
    price: float
    cadence: str  # "mo" | "yr"
    mode: ActionMode
    status: JobStatus = JobStatus.PENDING
    result_message: str = ""
    reclaimed_monthly: float = 0.0
    new_price: Optional[float] = None


@dataclass
class WorkerQueue:
    jobs: list[ActionJob] = field(default_factory=list)

    def enqueue(self, job: ActionJob) -> None:
        self.jobs.append(job)

    def pending(self) -> list[ActionJob]:
        return [j for j in self.jobs if j.status == JobStatus.PENDING]


def monthly(price: float, cadence: str) -> float:
    return price / 12 if cadence == "yr" else price


HAGGLE_RETENTION_RATE = 0.62  # merchant keeps 62% of original price


def process_job(job: ActionJob) -> ActionJob:
    """Execute one action job. Idempotent: re-processing a done job is a no-op."""
    if job.status != JobStatus.PENDING:
        return job

    base = monthly(job.price, job.cadence)
    if job.mode in (ActionMode.CANCEL, ActionMode.PAUSE):
        job.reclaimed_monthly = round(base, 2)
        verb = "canceled" if job.mode == ActionMode.CANCEL else "paused"
        job.result_message = f"{job.merchant} {verb}. ${base:.2f}/mo reclaimed. Undo window: 72h."
    else:  # HAGGLE
        job.new_price = round(job.price * HAGGLE_RETENTION_RATE, 2)
        job.reclaimed_monthly = round(base - monthly(job.new_price, job.cadence), 2)
        job.result_message = f"{job.merchant} countered with a retention deal. New rate locked in."

    job.status = JobStatus.DONE
    return job


def drain(queue: WorkerQueue) -> tuple[int, float]:
    """Process all pending jobs. Returns (jobs_done, total_monthly_reclaimed)."""
    done = 0
    reclaimed = 0.0
    for job in queue.pending():
        process_job(job)
        done += 1
        reclaimed += job.reclaimed_monthly
    return done, round(reclaimed, 2)


def main() -> None:
    queue = WorkerQueue()
    queue.enqueue(ActionJob(3, "Peak Fitness Gym", 44.0, "mo", ActionMode.CANCEL))
    queue.enqueue(ActionJob(8, "Calm", 69.99, "yr", ActionMode.PAUSE))
    queue.enqueue(ActionJob(4, "Adobe Creative Cloud", 59.99, "mo", ActionMode.HAGGLE))
    done, reclaimed = drain(queue)
    print(f"Processed {done} jobs; ${reclaimed:.2f}/mo reclaimed.")
    for job in queue.jobs:
        print(f"  [{job.status.value}] {job.result_message}")

    # Service mode: stay alive as an ECS task until the SQS queue is wired in.
    if os.environ.get("SEVER_WORKER_MODE") == "loop":
        import time

        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
