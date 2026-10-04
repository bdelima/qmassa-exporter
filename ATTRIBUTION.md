# Attribution

This repository's own code is licensed under the MIT License (see `LICENSE`). It uses or builds on the third-party projects below, each under its own license and copyright; nothing here relicenses them.

## qmassa

- **Project:** [ulissesf/qmassa](https://github.com/ulissesf/qmassa), an Intel GPU / DRM usage monitor
- **License:** Apache-2.0
- **How it's used:** installed from crates.io at image build time (`cargo install --locked qmassa@<version>`; the pinned version is in the `Dockerfile`) and shipped as a binary inside the image. This exporter only reads qmassa's JSON trace output and re-serves it as Prometheus metrics.

## Base images and system packages

- The `rust` image (build stage only) and the `python` slim image (runtime), plus the Debian packages the Dockerfile installs. Each carries its own licenses (for Debian packages, see `/usr/share/doc/*/copyright` inside the image).

## Trademarks

Intel and the names of Intel products and drivers belong to their owners. This is an unofficial project, not affiliated with or endorsed by Intel or the qmassa authors.
