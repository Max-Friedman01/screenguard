"""ScreenGuard sharer app.

Run from the repo root (venv active):
    python -m app.main            # real analyzer from ai/analyze.py (falls back to fake)
    python -m app.main --fake     # force the fake analyzer
    python -m app.main --image tests/screens/02_bank_light.png   # static image instead of screen

Keys (work from any window):
    F8  pause / resume the AI (new content stays covered: shows fail-closed)
    F9  panic: blank the stream / restore
In the preview window: q quits.
"""
import argparse
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.buffer import FailClosedGuard  # noqa: E402
from app.capture import ImageSource, ScreenCapture, blank_window_area, make_dpi_aware  # noqa: E402
from app.mask import draw_status, panic_frame  # noqa: E402
from app.server import FrameHub, start_server  # noqa: E402
from app.worker import AnalyzerWorker  # noqa: E402

WINDOW = "ScreenGuard preview"
PREVIEW_WIDTH = 480
STREAM_WIDTH = 1280
JPEG_QUALITY = 70


def load_analyzer(force_fake: bool):
    if not force_fake:
        try:
            from ai.analyze import analyze_frame
            print("[main] using REAL analyzer (ai/analyze.py)")
            return analyze_frame, False
        except Exception as e:  # noqa: BLE001
            print(f"[main] real analyzer unavailable ({e!r})")
    print("[main] WARNING: using FAKE analyzer, nothing real is detected")
    from app.fake_analyze import analyze_frame
    return analyze_frame, True


class State:
    panic = False


def setup_hotkeys(worker: AnalyzerWorker, state: State) -> bool:
    def toggle_pause():
        if worker.paused.is_set():
            worker.paused.clear()
            print("[keys] AI resumed")
        else:
            worker.paused.set()
            print("[keys] AI PAUSED: new content stays covered")

    def toggle_panic():
        state.panic = not state.panic
        print("[keys] PANIC on" if state.panic else "[keys] panic off")

    try:
        import keyboard
        keyboard.add_hotkey("f8", toggle_pause)
        keyboard.add_hotkey("f9", toggle_panic)
        print("[keys] global hotkeys: F8 pause AI, F9 panic")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[keys] global hotkeys unavailable ({e!r}); use p / b in the preview window")
        state.toggle_pause, state.toggle_panic = toggle_pause, toggle_panic
        return False


def encode_jpeg(img):
    h, w = img.shape[:2]
    if w > STREAM_WIDTH:
        img = cv2.resize(img, (STREAM_WIDTH, int(h * STREAM_WIDTH / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return buf.tobytes() if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="use the fake analyzer")
    ap.add_argument("--image", help="use a static image instead of the screen")
    ap.add_argument("--monitor", type=int, default=1, help="mss monitor number (1 = main display)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    make_dpi_aware()
    source = ImageSource(args.image) if args.image else ScreenCapture(args.monitor)
    analyze_fn, is_fake = load_analyzer(args.fake)

    guard = FailClosedGuard()
    worker = AnalyzerWorker(analyze_fn, guard)
    worker.start()
    hub = FrameHub()
    start_server(hub, port=args.port, fps=args.fps)
    state = State()
    global_keys = setup_hotkeys(worker, state)

    preview = not args.no_preview
    sw, sh = source.size
    ph = int(PREVIEW_WIDTH * sh / sw)
    placed = False
    if preview:
        # NORMAL = resizable; the image scales with the window.
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)

    period = 1 / args.fps
    last_log = time.time()
    try:
        while True:
            t0 = time.perf_counter()
            frame = source.grab()
            if preview and not args.image:
                blank_window_area(frame, WINDOW, source.origin)

            safe, n_unchecked = guard.compose(frame)
            if n_unchecked:
                worker.offer(frame)

            if state.panic:
                out = panic_frame(safe.shape)
            else:
                out = safe
                if is_fake:
                    draw_status(out, "ScreenGuard: FAKE AI (testing only)", warn=True)
                elif worker.paused.is_set():
                    draw_status(out, "ScreenGuard active - AI paused, new content covered", warn=True)
                else:
                    draw_status(out, "ScreenGuard active")

            jpeg = encode_jpeg(out)
            if jpeg:
                hub.publish(jpeg)

            if preview:
                cv2.imshow(WINDOW, out)
                if not placed:  # size and position once, after the window exists
                    ox, oy = source.origin
                    cv2.resizeWindow(WINDOW, PREVIEW_WIDTH, ph)
                    cv2.moveWindow(WINDOW, ox + sw - PREVIEW_WIDTH - 30, oy + sh - ph - 90)
                    placed = True
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if not global_keys and key == ord("p"):
                    state.toggle_pause()
                if not global_keys and key == ord("b"):
                    state.toggle_panic()

            if time.time() - last_log > 5:
                a = guard.last_analysis_s
                print(f"[main] unchecked areas: {n_unchecked}, last analysis: "
                      f"{'-' if a is None else f'{a:.2f}s'}, analyzer errors: {worker.errors}")
                last_log = time.time()

            elapsed = time.perf_counter() - t0
            if elapsed < period:
                time.sleep(period - elapsed)
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()
        if preview:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()