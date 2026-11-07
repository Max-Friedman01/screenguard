"""ScreenGuard desktop app.

    python -m app.gui            # real analyzer (falls back to fake if ai/ fails to load)
    python -m app.gui --fake     # fake analyzer, for testing

Present: start sharing, get a share key to send to viewers.
Watch:   paste a share key, the stream opens in your browser.
"""
import argparse
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import customtkinter as ctk  # noqa: E402
from PIL import Image  # noqa: E402

from app.capture import make_dpi_aware  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.tunnel import Tunnel  # noqa: E402

STREAM_PORT = 8080
VIEW_PORT = 8989
PREVIEW_W = 392

GREEN = "#2e9e5b"
GREEN_HOVER = "#268550"
RED = "#c94a4a"
RED_HOVER = "#a83d3d"
MUTED = "#9aa0a6"
CARD = "#23262b"


class App(ctk.CTk):
    def __init__(self, fake: bool):
        super().__init__()
        self.title("ScreenGuard")
        self.geometry("440x700")
        self.resizable(False, False)
        self.engine = Engine(fake=fake, port=STREAM_PORT)
        self.share_tunnel = Tunnel()
        self.watch_tunnel = Tunnel()
        self._starting = False
        self._preview_img = None

        # header
        ctk.CTkLabel(self, text="ScreenGuard", font=ctk.CTkFont(size=26, weight="bold")).pack(
            pady=(22, 0), padx=24, anchor="w")
        ctk.CTkLabel(self, text="Private screen sharing. The AI runs on this laptop.",
                     text_color=MUTED).pack(padx=24, anchor="w")

        self.mode = ctk.CTkSegmentedButton(self, values=["Present", "Watch"], command=self._switch,
                                           height=34)
        self.mode.set("Present")
        self.mode.pack(fill="x", padx=24, pady=(16, 10))

        self.present = ctk.CTkFrame(self, fg_color="transparent")
        self.watch = ctk.CTkFrame(self, fg_color="transparent")
        self._build_present()
        self._build_watch()
        self.present.pack(fill="both", expand=True, padx=24)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._tick)

    # ---------------- Present ----------------
    def _build_present(self):
        f = self.present
        self.status = ctk.CTkLabel(f, text="●  Not sharing", text_color=MUTED,
                                   font=ctk.CTkFont(size=15, weight="bold"))
        self.status.pack(anchor="w", pady=(4, 8))

        self.start_btn = ctk.CTkButton(f, text="Start presenting", height=46, fg_color=GREEN,
                                       hover_color=GREEN_HOVER, font=ctk.CTkFont(size=16, weight="bold"),
                                       command=self._toggle_present)
        self.start_btn.pack(fill="x")

        key_card = ctk.CTkFrame(f, fg_color=CARD, corner_radius=10)
        key_card.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(key_card, text="Share key — send this to your viewers",
                     text_color=MUTED).pack(anchor="w", padx=12, pady=(10, 4))
        row = ctk.CTkFrame(key_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 12))
        self.key_entry = ctk.CTkEntry(row, placeholder_text="Appears when you start presenting")
        self.key_entry.pack(side="left", fill="x", expand=True)
        self.copy_btn = ctk.CTkButton(row, text="Copy", width=70, command=self._copy_key, state="disabled")
        self.copy_btn.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(f, text="What your viewers see", text_color=MUTED).pack(anchor="w", pady=(14, 4))
        blank = Image.new("RGB", (PREVIEW_W, 220), CARD)
        self._blank_preview = ctk.CTkImage(light_image=blank, dark_image=blank, size=(PREVIEW_W, 220))
        self.preview = ctk.CTkLabel(f, text="Preview appears here", image=self._blank_preview,
                                    compound="center", text_color=MUTED)
        self.preview.pack()

        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", pady=(12, 0))
        self.pause_btn = ctk.CTkButton(row2, text="Pause AI  (F8)", fg_color=CARD, state="disabled",
                                       command=self.engine.toggle_pause)
        self.pause_btn.pack(side="left", fill="x", expand=True)
        self.hide_btn = ctk.CTkButton(row2, text="Hide screen  (F9)", fg_color=CARD, state="disabled",
                                      command=self.engine.toggle_panic)
        self.hide_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.info = ctk.CTkLabel(f, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self.info.pack(anchor="w", pady=(10, 0))

    def _toggle_present(self):
        if self.engine.running or self._starting:
            self._stop_present()
        else:
            self._starting = True
            self.start_btn.configure(text="Starting…", state="disabled")
            threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self):
        # runs off the UI thread: loading the AI can take a few seconds
        try:
            self.engine.start()
            self.share_tunnel.share(STREAM_PORT)
        except Exception as e:  # noqa: BLE001
            self.share_tunnel.error = f"Couldn't start: {e}"
        self._starting = False

    def _stop_present(self):
        self.share_tunnel.stop()
        self.engine.stop()
        self.key_entry.configure(state="normal")
        self.key_entry.delete(0, "end")
        self.copy_btn.configure(state="disabled")

    def _copy_key(self):
        if self.share_tunnel.key:
            self.clipboard_clear()
            self.clipboard_append(self.share_tunnel.key)
            self.copy_btn.configure(text="Copied")
            self.after(1500, lambda: self.copy_btn.configure(text="Copy"))

    # ---------------- Watch ----------------
    def _build_watch(self):
        f = self.watch
        ctk.CTkLabel(f, text="Watch someone's screen", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", pady=(4, 8))
        ctk.CTkLabel(f, text="Paste the share key they sent you:", text_color=MUTED).pack(anchor="w")
        self.watch_entry = ctk.CTkEntry(f, placeholder_text="hs://…", height=38)
        self.watch_entry.pack(fill="x", pady=(6, 10))
        self.connect_btn = ctk.CTkButton(f, text="Connect", height=46, fg_color=GREEN, hover_color=GREEN_HOVER,
                                         font=ctk.CTkFont(size=16, weight="bold"), command=self._toggle_watch)
        self.connect_btn.pack(fill="x")
        self.watch_status = ctk.CTkLabel(f, text="", text_color=MUTED, wraplength=380, justify="left")
        self.watch_status.pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(f, text="The stream comes straight from the presenter's laptop over an encrypted\n"
                             "peer-to-peer tunnel. No server in between, and personal details are\n"
                             "hidden on their laptop before anything is sent.",
                     text_color=MUTED, justify="left", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(24, 0))

    def _toggle_watch(self):
        if self.watch_tunnel.running:
            self.watch_tunnel.stop()
            self.connect_btn.configure(text="Connect", fg_color=GREEN, hover_color=GREEN_HOVER)
            self.watch_status.configure(text="Disconnected.")
            return
        key = self.watch_entry.get().strip()
        if not key.startswith("hs://"):
            self.watch_status.configure(text="That doesn't look like a share key (it should start with hs://).")
            return
        if not self.watch_tunnel.connect(key, VIEW_PORT):
            self.watch_status.configure(text=self.watch_tunnel.error)
            return
        self.connect_btn.configure(text="Disconnect", fg_color=RED, hover_color=RED_HOVER)
        self.watch_status.configure(text="Connecting… the stream will open in your browser.")
        self.after(3000, self._open_viewer)

    def _open_viewer(self):
        if self.watch_tunnel.running:
            webbrowser.open(f"http://127.0.0.1:{VIEW_PORT}/")
            self.watch_status.configure(
                text=f"Connected. Viewing at http://127.0.0.1:{VIEW_PORT}  (refresh if it's blank).")
        else:
            out = "\n".join(self.watch_tunnel.lines[-3:])
            self.watch_status.configure(text=f"Couldn't connect.\n{out}")
            self.connect_btn.configure(text="Connect", fg_color=GREEN, hover_color=GREEN_HOVER)

    # ---------------- shared ----------------
    def _switch(self, value):
        self.present.pack_forget()
        self.watch.pack_forget()
        (self.present if value == "Present" else self.watch).pack(fill="both", expand=True, padx=24)

    def _tick(self):
        e = self.engine
        # tell the engine where this window is so it's blacked out of the capture
        if self.state() == "iconic":
            e.exclude_rects = []
        else:
            e.exclude_rects = [(self.winfo_rootx(), self.winfo_rooty(), self.winfo_width(), self.winfo_height())]

        # only reconfigure widgets when something changed (avoids flicker)
        sig = (e.running, self._starting, e.paused, e.panic, e.is_fake)
        if sig != getattr(self, "_last_sig", None):
            self._last_sig = sig
            self._apply_state(e)

        if e.running:
            key = self.share_tunnel.key
            if key and self.key_entry.get() != key:
                self.key_entry.configure(state="normal")
                self.key_entry.delete(0, "end")
                self.key_entry.insert(0, key)
                self.key_entry.configure(state="readonly")
                self.copy_btn.configure(state="normal")
            elif not key and self.share_tunnel.error:
                self.info.configure(text=self.share_tunnel.error)

            frame = e.preview
            if frame is not None:
                h, w = frame.shape[:2]
                ph = int(PREVIEW_W * h / w)
                small = cv2.cvtColor(cv2.resize(frame, (PREVIEW_W, ph), interpolation=cv2.INTER_AREA),
                                     cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(small)
                self._preview_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(PREVIEW_W, ph))
                self.preview.configure(image=self._preview_img, text="")

            a = e.last_analysis_s
            ai = "fake AI" if e.is_fake else "QVAC, on this laptop"
            if not (self.share_tunnel.error and not self.share_tunnel.key):
                self.info.configure(text=f"AI: {ai}  ·  last check {'-' if a is None else f'{a:.1f}s'}"
                                         f"  ·  {e.n_unchecked} area(s) being checked")
        elif not self._starting:
            err = self.share_tunnel.error or ""
            if self.info.cget("text") != err:
                self.info.configure(text=err)

        self.after(150, self._tick)

    def _apply_state(self, e):
        if e.running:
            self.start_btn.configure(text="Stop presenting", state="normal", fg_color=RED, hover_color=RED_HOVER)
            self.pause_btn.configure(state="normal", text="Resume AI  (F8)" if e.paused else "Pause AI  (F8)")
            self.hide_btn.configure(state="normal", text="Show screen  (F9)" if e.panic else "Hide screen  (F9)")
            if e.panic:
                self.status.configure(text="●  Screen hidden from viewers", text_color="#e0a030")
            elif e.paused:
                self.status.configure(text="●  AI paused — new content stays covered", text_color="#e0a030")
            elif e.is_fake:
                self.status.configure(text="●  Sharing (FAKE AI — testing only)", text_color=RED)
            else:
                self.status.configure(text="●  Sharing — protected", text_color=GREEN)
        elif self._starting:
            self.start_btn.configure(text="Starting…", state="disabled")
            self.status.configure(text="●  Loading the AI…", text_color=MUTED)
        else:
            self.start_btn.configure(text="Start presenting", state="normal", fg_color=GREEN, hover_color=GREEN_HOVER)
            self.status.configure(text="●  Not sharing", text_color=MUTED)
            self.pause_btn.configure(state="disabled", text="Pause AI  (F8)")
            self.hide_btn.configure(state="disabled", text="Hide screen  (F9)")
            self._preview_img = self._blank_preview
            self.preview.configure(image=self._blank_preview, text="Preview appears here")

    def _on_close(self):
        self.watch_tunnel.stop()
        self.share_tunnel.stop()
        if self.engine.running:
            self.engine.stop()
        self.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="use the fake analyzer")
    args = ap.parse_args()
    make_dpi_aware()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    App(fake=args.fake).mainloop()


if __name__ == "__main__":
    main()
