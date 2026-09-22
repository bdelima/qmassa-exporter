# qmassa-exporter

A small Python bridge that tails [`qmassa`](https://github.com/ulissesf/qmassa)'s continuous JSON trace output and serves it as a Prometheus `/metrics` endpoint.

## Why this exists

`qmassa` reads real per-engine GPU utilization via DRM fdinfo, and — unlike `intel_gpu_top` — works on Intel's `xe` driver (Panther Lake and newer), not just `i915`. `qmassa` ships its own metrics daemon (`qmmd`), but that requires a newer Rust toolchain than most current distros package. This exporter avoids that dependency entirely: it runs `qmassa` itself in continuous JSON-trace mode, tails the output, and re-serves the latest sample as standard Prometheus text format — so it only needs Python.

## Metrics exposed

- `qmassa_gpu_engine_busy_percent{engine="..."}` — per-engine GPU busy percentage (e.g. `render`, `video`, `video-enhance`), straight from DRM fdinfo.
- `qmassa_gpu_client_cpu_percent{pid="...",comm="..."}` — per-process CPU percent for each active GPU client qmassa is tracking.

**Note:** like all fdinfo-based GPU accounting on the `xe` driver, these numbers have known reporting-accuracy issues relative to `i915` on some engines (see [Ubuntu/Launchpad #2119526](https://bugs.launchpad.net/ubuntu/+source/linux/+bug/2119526)) — trust relative/before-after comparisons on the same host more than absolute cross-driver comparisons.

## Running it

```bash
docker run -d \
  --name qmassa-exporter \
  --restart unless-stopped \
  --pid host \
  --privileged \
  --device /dev/dri:/dev/dri \
  -p 9820:9820 \
  bdelima/qmassa-exporter:latest
```

`--pid host` is required if you want to see GPU clients running in *other* containers (e.g. Frigate's ffmpeg processes) — qmassa needs the host PID namespace to resolve them. `--privileged` is usually needed for fdinfo access to other containers' processes; try dropping it first and only add it back if you hit permission errors.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `EXPORTER_PORT` | `9820` | Port the `/metrics` HTTP server listens on |
| `QMASSA_INTERVAL_MS` | `1000` | Sampling interval passed to `qmassa -m` |

### docker-compose

See [`docker-compose.example.yml`](docker-compose.example.yml) for a minimal Prometheus-scrapeable setup.

## Building locally

```bash
docker build -t qmassa-exporter .
```

## Versioning / releases

This repo publishes to Docker Hub as [`bdelima/qmassa-exporter`](https://hub.docker.com/r/bdelima/qmassa-exporter) (multi-arch: `linux/amd64`, `linux/arm64`) automatically whenever the `VERSION` file is bumped on a push to `main` — see `.github/workflows/docker-publish.yml`.
