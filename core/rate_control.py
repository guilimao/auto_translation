from __future__ import annotations

import asyncio
import time
from collections import deque


class GlobalRequestManager:
    def __init__(self, max_concurrent_requests: int, qps: float, qpm: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._lock = asyncio.Lock()
        self._request_times: deque[float] = deque()
        self._qps_interval = 1.0 / qps if qps > 0 else 0.0
        self._qpm = qpm
        self._last_request_time = 0.0

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._request_times and now - self._request_times[0] >= 60.0:
                    self._request_times.popleft()
                wait_for_qps = max(0.0, self._qps_interval - (now - self._last_request_time))
                wait_for_qpm = 0.0
                if len(self._request_times) >= self._qpm:
                    wait_for_qpm = max(0.0, 60.0 - (now - self._request_times[0]))
                wait_time = max(wait_for_qps, wait_for_qpm)
                if wait_time <= 0:
                    break
                await asyncio.sleep(wait_time)
            now = time.monotonic()
            self._last_request_time = now
            self._request_times.append(now)

    def release(self) -> None:
        self._semaphore.release()
