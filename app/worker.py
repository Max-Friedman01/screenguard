"""Runs the analyser (real or fake) in its own thread with its own asyncio loop.

Always analyses the NEWEST frame offered; older unanalysed frames are dropped.
If the analyser raises, nothing is submitted, so changed areas stay covered.
"""
import asyncio
import threading
import time
import traceback


class AnalyzerWorker(threading.Thread):
    def __init__(self, analyze_fn, guard):
        super().__init__(daemon=True, name="analyzer")
        self._analyze = analyze_fn
        self._guard = guard
        self._lock = threading.Lock()
        self._latest = None
        self.paused = threading.Event()
        self._stop = threading.Event()
        self.errors = 0

    def offer(self, frame) -> None:
        with self._lock:
            self._latest = frame

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        asyncio.run(self._loop())

    async def _loop(self) -> None:
        while not self._stop.is_set():
            if self.paused.is_set():
                await asyncio.sleep(0.05)
                continue
            with self._lock:
                frame, self._latest = self._latest, None
            if frame is None:
                await asyncio.sleep(0.02)
                continue
            t0 = time.perf_counter()
            try:
                boxes = await self._analyze(frame)
            except Exception:
                self.errors += 1
                if self.errors <= 3:
                    print("[analyzer] error, frame left covered:")
                    traceback.print_exc()
                continue
            if self.paused.is_set():
                continue  # paused mid-analysis: don't reveal anything new
            self._guard.submit_result(frame, boxes, time.perf_counter() - t0)
