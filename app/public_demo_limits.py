"""Bounded, single-process public admission control and durable daily quota."""
import sqlite3
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException


class PublicLimits:
    def __init__(self, directory: Path, per_minute: int, daily: int, concurrency: int):
        directory.mkdir(parents=True, exist_ok=True)
        # Holding this transaction rejects a second worker/process using the same state.
        self.process_lock = sqlite3.connect(directory / "process-lock.sqlite3", timeout=0)
        try:
            self.process_lock.execute("BEGIN EXCLUSIVE")
        except Exception:
            self.process_lock.close()
            raise
        try:
            self.quota = sqlite3.connect(directory / "quota.sqlite3", check_same_thread=False)
            self.quota.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
            self.quota.commit()
        except Exception:
            self.process_lock.close()
            raise
        self.mutex = threading.Lock()
        self.slots = threading.BoundedSemaphore(concurrency)
        self.timestamps = deque()
        self.per_minute = per_minute
        self.daily = daily

    def admit(self) -> None:
        # Global limits cannot be bypassed using forged IP or identity headers.
        with self.mutex:
            now = time.monotonic()
            while self.timestamps and self.timestamps[0] <= now - 60:
                self.timestamps.popleft()
            if len(self.timestamps) >= self.per_minute:
                self.reject()
            if not self.slots.acquire(blocking=False):
                self.reject()
            try:
                day = datetime.now(UTC).date().isoformat()
                with self.quota:
                    self.quota.execute("INSERT OR IGNORE INTO usage VALUES (?, 0)", (day,))
                    cursor = self.quota.execute("UPDATE usage SET count=count+1 WHERE day=? AND count<?",
                                                (day, self.daily))
                    if cursor.rowcount != 1:
                        self.reject()
                self.timestamps.append(now)
            except Exception:
                self.slots.release()
                raise

    @staticmethod
    def reject() -> None:
        raise HTTPException(429, "利用上限に達しました。時間をおいて再試行してください。",
                            headers={"Retry-After": "60"})

    def close(self) -> None:
        self.quota.close()
        self.process_lock.close()
