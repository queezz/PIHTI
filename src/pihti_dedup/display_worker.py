"""Isolated, bounded STEP display preparation; never attaches to Inventor."""

from __future__ import annotations

import atexit
import json
import subprocess
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class DisplayPending(Exception):
    pass


def _stop(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # A Windows venv executable can be a launcher with an interpreter child.
        # Killing only the launcher leaves that tessellator and its pipes alive.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.kill()


class DisplayJobs:
    def __init__(self, root, mirror_root):
        self.root, self.mirror_root = root, mirror_root
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="step-display")
        self.lock = threading.Lock()
        self.jobs = OrderedDict()
        self.process = None
        self.closed = False
        atexit.register(self.close)

    def prepare(self, key, source):
        with self.lock:
            if self.closed:
                raise ValueError("STEP display worker stopped")
            job = self.jobs.get(key)
            if job is None:
                if sum(not job.done() for job in self.jobs.values()) >= 2:
                    raise DisplayPending()
                job = self.pool.submit(self._run, source)
                self.jobs[key] = job
                for old in list(self.jobs):
                    if len(self.jobs) <= 32:
                        break
                    if self.jobs[old].done():
                        del self.jobs[old]
        if not job.done():
            raise DisplayPending()
        error = job.result()
        if error:
            raise ValueError(error)

    def _run(self, source):
        from pihti_dedup import mesh_cache

        command = [
            sys.executable,
            "-m",
            "pihti_dedup.display_worker",
            str(self.root),
            str(self.mirror_root),
            source,
            str(mesh_cache.MAX_TRIANGLES),
        ]
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        with self.lock:
            if self.closed:
                return "STEP display worker stopped"
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags
            )
            self.process = process
        try:
            _, errors = process.communicate(timeout=120)
            if process.returncode:
                try:
                    return json.loads(errors.decode().splitlines()[-1])["error"]
                except (ValueError, KeyError, IndexError):
                    return "STEP display preparation failed"
            return None
        except subprocess.TimeoutExpired:
            _stop(process)
            process.communicate()
            return "STEP display preparation timed out; use the still preview"
        finally:
            with self.lock:
                self.process = None

    def close(self):
        with self.lock:
            self.closed = True
            if self.process is not None:
                _stop(self.process)
        self.pool.shutdown(wait=False, cancel_futures=True)


def main():
    from flask import Flask

    from pihti_dedup import mesh_cache
    from pihti_dedup.simulation_web import register
    from pihti_dedup.step_mirror import StepMirror

    root, mirror, source, cap = sys.argv[1:]
    mesh_cache.MAX_TRIANGLES = int(cap)
    app = Flask(__name__)
    register(app, Path(root), StepMirror(root, root=mirror), lambda request: None)
    response = app.test_client().get("/simulation/model", query_string={"source": source})
    if response.status_code != 200:
        print(
            json.dumps(response.get_json() or {"error": "STEP display preparation failed"}),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
