"""
Engine-side sandbox client: runs game_engine/sim/runner.py in a subprocess
(on a background thread) so the pygame window never freezes.
"""
import json
import os
import subprocess
import sys
import threading

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(ENGINE_DIR)
RUNNER = os.path.join(ENGINE_DIR, "sim", "runner.py")
RESULT_MARK = "@@RESULT@@"
HARD_TIMEOUT = 8.0


def run_job(job, timeout=HARD_TIMEOUT):
    """Run a job synchronously. Always returns a result dict (never raises)."""
    try:
        proc = subprocess.run([sys.executable, RUNNER], input=json.dumps(job), capture_output=True,
                              text=True, timeout=timeout, cwd=PROJECT_DIR)
    except subprocess.TimeoutExpired:
        return {"ok": False, "timeout": True, "days": [{
            "error": (f"Your spell took longer than {timeout:.0f} seconds and was stopped. "
                      f"Is there a loop that never ends?"),
            "error_kind": "Timeout", "path": [], "events": [], "log": [], "battles": [],
            "terraforms": []}], "log": [], "facts": {}, "trials": []}
    out = proc.stdout or ""
    idx = out.rfind(RESULT_MARK)
    if idx < 0:
        return {"ok": False, "fatal": "The sandbox crashed.\n" + (proc.stderr or out)[-1500:],
                "days": [], "log": [], "facts": {}, "trials": []}
    try:
        return json.loads(out[idx + len(RESULT_MARK):].strip().splitlines()[0])
    except (ValueError, IndexError) as e:
        return {"ok": False, "fatal": f"Bad sandbox output: {e}", "days": [], "log": [],
                "facts": {}, "trials": []}


class AsyncRunner:
    """Runs one job at a time in the background; poll() returns finished results."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._result = None
        self._tag = None

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, job, tag):
        if self.busy:
            return False

        def work():
            res = run_job(job)
            with self._lock:
                self._result = (tag, res)
        self._tag = tag
        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()
        return True

    def poll(self):
        with self._lock:
            r, self._result = self._result, None
        return r
