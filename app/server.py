"""MJPEG stream of the MASKED screen on localhost:8080.

This module only ever sees JPEG bytes handed to FrameHub.publish(), which the
main loop calls with the composed, masked frame. It has no access to the raw
capture, and there are deliberately no /raw, /capture or debug endpoints.
"""
import asyncio
import threading

from aiohttp import web

BOUNDARY = "screenguardframe"

VIEWER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>ScreenGuard viewer</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html,body{margin:0;height:100%;background:#111;color:#ccc;font-family:Segoe UI,Arial,sans-serif}
header{padding:8px 14px;font-size:14px;background:#1c1c1c}
main{height:calc(100% - 36px);display:flex;align-items:center;justify-content:center}
img{max-width:100%;max-height:100%}
</style></head>
<body><header>ScreenGuard &middot; masked screen, received peer-to-peer</header>
<main><img src="/stream" alt="Shared screen"></main></body></html>"""


class FrameHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = None
        self._seq = 0

    def publish(self, jpeg_bytes: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg_bytes
            self._seq += 1

    def latest(self):
        with self._lock:
            return self._seq, self._jpeg


def _make_app(hub: FrameHub, fps: float) -> web.Application:
    async def index(_request):
        return web.Response(text=VIEWER_HTML, content_type="text/html")

    async def stream(request):
        resp = web.StreamResponse(headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            "Cache-Control": "no-cache, no-store",
        })
        await resp.prepare(request)
        last = -1
        try:
            while True:
                seq, jpeg = hub.latest()
                if jpeg is not None and seq != last:
                    last = seq
                    await resp.write(
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(jpeg)}\r\n\r\n".encode() + jpeg + b"\r\n")
                await asyncio.sleep(1 / fps)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return resp

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/stream", stream)
    return app


def start_server(hub: FrameHub, host: str = "127.0.0.1", port: int = 8080, fps: float = 10):
    """Start the server in a background thread. Binds to localhost only:
    Holesail is what carries it to the viewer."""
    ready = threading.Event()

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(_make_app(hub, fps))
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, host, port).start())
        ready.set()
        loop.run_forever()

    threading.Thread(target=run, daemon=True, name="mjpeg").start()
    ready.wait(5)
    print(f"[server] masked stream at http://{host}:{port}/")
