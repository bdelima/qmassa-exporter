#!/usr/bin/env python3
"""
qmassa-exporter: reads qmassa's continuous JSON output (through a named pipe,
so nothing accumulates on disk) and serves it as a Prometheus /metrics
endpoint. Bridges qmassa (real per-engine GPU usage via DRM fdinfo, works on
xe) into Prometheus without needing the qmmd daemon (which requires a newer
Rust than most distros currently package).
"""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

QMASSA_BIN = "/usr/local/bin/qmassa"
STREAM_FILE = "/tmp/qmassa_stream.json"
PORT = int(os.environ.get("EXPORTER_PORT", "9820"))
INTERVAL_MS = os.environ.get("QMASSA_INTERVAL_MS", "1000")
APP_VERSION = os.environ.get("APP_VERSION", "unknown")

latest = {"eng_usage": {}, "clients": []}
lock = threading.Lock()


def start_qmassa():
    # -n -1 (default) runs indefinitely, writing one JSON line per sample to
    # the -t path until the process is killed. Each line is a full snapshot
    # of qmassa's state (a rolling window of ~40 samples per stat), and we
    # only ever use the newest line. Pointing -t at a regular file made it
    # grow without bound (GBs/day) since qmassa never trims it, so STREAM_FILE
    # is a named pipe instead: qmassa opens it for writing (O_TRUNC is
    # ignored for FIFOs) and nothing is stored on disk.
    # Remove whatever is at the path first (a stale FIFO, or a regular file
    # left in the container's writable layer by an older version).
    if os.path.lexists(STREAM_FILE):
        os.remove(STREAM_FILE)
    os.mkfifo(STREAM_FILE, 0o600)
    subprocess.Popen(
        [QMASSA_BIN, "-x", "-m", INTERVAL_MS, "-t", STREAM_FILE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def tail_thread():
    while not os.path.exists(STREAM_FILE):
        time.sleep(1)

    # Opening a FIFO for reading blocks until qmassa opens the write end.
    with open(STREAM_FILE, "r") as f:
        # First two lines are a version string and the run's config echo,
        # not a data sample — skip them once.
        f.readline()
        f.readline()

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                continue

            # qmassa's trace stream isn't guaranteed to be one flat JSON
            # object per line (a stray/partial-write line can decode to a
            # bare scalar, e.g. a float). Guard the type before treating it
            # as a dict, and never let a single malformed sample kill this
            # thread -- once this loop exits, /metrics silently freezes on
            # stale data forever with no visible error.
            if not isinstance(sample, dict):
                continue
            devs_state = sample.get("devs_state")
            if not devs_state:
                continue

            try:
                dev = devs_state[0]
                eng_usage = dev.get("dev_stats", {}).get("eng_usage", {})
                clients = dev.get("clis_stats", [])

                new_eng_usage = {
                    k: (v[-1] if v else 0.0) for k, v in eng_usage.items()
                }
                new_clients = [
                    {
                        "pid": c["pid"],
                        "comm": c["comm"],
                        "cpu": (c["cpu_usage"][-1] if c["cpu_usage"] else 0.0),
                    }
                    for c in clients
                    if c.get("is_active")
                ]
            except (KeyError, IndexError, TypeError, AttributeError):
                # Malformed/unexpected shape for this one sample -- skip it,
                # keep serving the last good values, keep tailing.
                continue

            with lock:
                latest["eng_usage"] = new_eng_usage
                latest["clients"] = new_clients


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        with lock:
            eng = dict(latest["eng_usage"])
            clients = list(latest["clients"])

        lines = [
            "# HELP qmassa_exporter_build_info Exporter build metadata (always 1, version in the label)",
            "# TYPE qmassa_exporter_build_info gauge",
            f'qmassa_exporter_build_info{{version="{APP_VERSION}"}} 1',
            "# HELP qmassa_gpu_engine_busy_percent GPU engine busy percentage (DRM fdinfo, via qmassa)",
            "# TYPE qmassa_gpu_engine_busy_percent gauge",
        ]
        for engine, pct in eng.items():
            lines.append(f'qmassa_gpu_engine_busy_percent{{engine="{engine}"}} {pct}')

        lines.append("# HELP qmassa_gpu_client_cpu_percent Per-process CPU percent for active GPU clients")
        lines.append("# TYPE qmassa_gpu_client_cpu_percent gauge")
        for c in clients:
            comm = c["comm"].replace('"', "")
            lines.append(
                f'qmassa_gpu_client_cpu_percent{{pid="{c["pid"]}",comm="{comm}"}} {c["cpu"]}'
            )

        body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence default per-request access logging


if __name__ == "__main__":
    start_qmassa()
    threading.Thread(target=tail_thread, daemon=True).start()
    HTTPServer(("0.0.0.0", PORT), MetricsHandler).serve_forever()
