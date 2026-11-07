"""Runs the Holesail CLI as a subprocess (share or connect) and reads its output."""
import re
import shutil
import subprocess
import sys
import threading

KEY_RE = re.compile(r"hs://[A-Za-z0-9]+")
RAW_KEY_RE = re.compile(r"\b[0-9a-z]{52,}\b")  # bare key with no hs:// prefix
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def holesail_path():
    found = shutil.which("holesail")  # on Windows this finds holesail.cmd
    if found:
        return found
    # terminals opened before Node was installed don't have npm's folder on PATH
    if sys.platform == "win32":
        import os
        for base in (os.environ.get("APPDATA"), os.path.expanduser(r"~\AppData\Roaming")):
            if base:
                cand = os.path.join(base, "npm", "holesail.cmd")
                if os.path.exists(cand):
                    return cand
    return None


def _env_with_node(exe):
    """Environment with Node's and npm's folders on PATH, for terminals that were
    opened before Node was installed."""
    import os
    env = os.environ.copy()
    extra = [os.path.dirname(exe)]
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("LOCALAPPDATA") and os.path.join(os.environ["LOCALAPPDATA"], "Programs")):
            if base:
                nodedir = os.path.join(base, "nodejs")
                if os.path.exists(os.path.join(nodedir, "node.exe")):
                    extra.append(nodedir)
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


class Tunnel:
    def __init__(self):
        self.proc = None
        self.key = None
        self.lines = []
        self.error = None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def _spawn(self, args):
        exe = holesail_path()
        if not exe:
            self.error = "Holesail isn't installed. Run: npm i -g holesail"
            return False
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self.proc = subprocess.Popen(
                [exe, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=flags, env=_env_with_node(exe))
        except OSError as e:
            self.error = f"Couldn't start Holesail: {e}"
            return False
        threading.Thread(target=self._read, daemon=True).start()
        return True

    def _read(self):
        for raw in self.proc.stdout:
            line = ANSI_RE.sub("", raw).rstrip()
            if not line:
                continue
            self.lines.append(line)
            print("[holesail]", line)
            if self.key is None:
                m = KEY_RE.search(line) or RAW_KEY_RE.search(line)
                if m:
                    self.key = m.group(0)
        self.lines.append("(Holesail exited)")

    def status(self) -> str:
        """Short human-readable progress line for the UI while there's no key yet."""
        if self.error:
            return self.error
        if self.key:
            return ""
        last = self.lines[-1] if self.lines else ""
        if self.proc is None:
            return ""
        if not self.running:
            return f"Holesail stopped. Last output: {last}"[:160]
        return f"Starting Holesail… {last}"[:160]

    def share(self, port: int) -> bool:
        """Expose a local port. The key appears in self.key once Holesail prints it."""
        self.stop()
        self.key, self.lines, self.error = None, [], None
        return self._spawn(["--live", str(port)])

    def connect(self, key: str, local_port: int) -> bool:
        self.stop()
        self.key, self.lines, self.error = key, [], None
        return self._spawn(["--connect", key, "--port", str(local_port)])

    def stop(self):
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None