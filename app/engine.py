"""The ScreenGuard sharing engine, usable from the GUI.

Runs capture -> fail-closed guard -> masks -> MJPEG in a background thread.
The GUI tells it which screen rectangles to black out (its own window).
"""
import threading
import time


from app.buffer import FailClosedGuard
from app.capture import ScreenCapture
from app.main import encode_jpeg, load_analyzer
from app.mask import draw_status, panic_frame
from app.server import FrameHub, start_server
from app.worker import AnalyzerWorker


class Engine:
    def __init__(self, fake=False, monitor=1, port=8080, fps=10):
        self.fake_requested = fake
        self.monitor = monitor
        self.port = port
        self.fps = fps
        self.hub = FrameHub()
        self._server_started = False
        self._thread = None
        self._running = threading.Event()
        self.analyze_fn = None
        self.is_fake = None

        # read by the GUI
        self.preview = None          # latest masked frame (BGR), or None
        self.n_unchecked = 0
        self.last_analysis_s = None
        self.analyzer_errors = 0
        self.screen_size = None

        # written by the GUI
        self.exclude_rects = []      # [(x, y, w, h)] in screen coordinates
        self.panic = False

        self._worker = None
        self._guard = None
        self._hotkeys_done = False

    # ----- controls -----
    @property
    def running(self):
        return self._running.is_set()

    @property
    def paused(self):
        return bool(self._worker and self._worker.paused.is_set())

    def toggle_pause(self):
        if not self._worker:
            return
        if self._worker.paused.is_set():
            self._worker.paused.clear()
        else:
            self._worker.paused.set()

    def toggle_panic(self):
        self.panic = not self.panic

    def start(self):
        if self.running:
            return
        if self.analyze_fn is None:
            self.analyze_fn, self.is_fake = load_analyzer(self.fake_requested)
        if not self._server_started:
            start_server(self.hub, port=self.port, fps=self.fps)
            self._server_started = True
        self._setup_hotkeys()
        self._guard = FailClosedGuard()
        self._worker = AnalyzerWorker(self.analyze_fn, self._guard)
        self._worker.start()
        self.panic = False
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="capture")
        self._thread.start()

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2)
        if self._worker:
            self._worker.stop()
            self._worker = None
        self.preview = None
        if self.screen_size:
            w, h = self.screen_size
            self.hub.publish(encode_jpeg(panic_frame((h, w, 3), "The presenter has stopped sharing")))

    # ----- internals -----
    def _setup_hotkeys(self):
        if self._hotkeys_done:
            return
        self._hotkeys_done = True
        try:
            import keyboard
            keyboard.add_hotkey("f8", self.toggle_pause)
            keyboard.add_hotkey("f9", self.toggle_panic)
            print("[keys] global hotkeys: F8 pause AI, F9 hide screen")
        except Exception as e:  # noqa: BLE001
            print(f"[keys] global hotkeys unavailable ({e!r})")

    def _blank_excluded(self, frame, origin):
        fh, fw = frame.shape[:2]
        for (x, y, w, h) in list(self.exclude_rects):
            # widen to cover title bar and borders
            l = max(0, x - origin[0] - 12)
            t = max(0, y - origin[1] - 45)
            r = min(fw, x - origin[0] + w + 12)
            b = min(fh, y - origin[1] + h + 12)
            if r > l and b > t:
                frame[t:b, l:r] = 0

    def _loop(self):
        source = ScreenCapture(self.monitor)  # mss must be created in this thread
        self.screen_size = source.size
        period = 1 / self.fps
        while self._running.is_set():
            t0 = time.perf_counter()
            frame = source.grab()
            self._blank_excluded(frame, source.origin)

            safe, n = self._guard.compose(frame)
            if n:
                self._worker.offer(frame)

            if self.panic:
                out = panic_frame(safe.shape)
            else:
                out = safe
                if self.is_fake:
                    draw_status(out, "ScreenGuard: FAKE AI (testing only)", warn=True)
                elif self._worker.paused.is_set():
                    draw_status(out, "ScreenGuard active - AI paused, new content covered", warn=True)
                else:
                    draw_status(out, "ScreenGuard active")

            jpeg = encode_jpeg(out)
            if jpeg:
                self.hub.publish(jpeg)
            self.preview = out
            self.n_unchecked = n
            self.last_analysis_s = self._guard.last_analysis_s
            self.analyzer_errors = self._worker.errors

            elapsed = time.perf_counter() - t0
            if elapsed < period:
                time.sleep(period - elapsed)
