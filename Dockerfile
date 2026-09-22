# Build stage — compile qmassa (pinned to 1.3.2: newer releases need a
# rustc version this base image's default toolchain doesn't have)
FROM rust:1.85-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    libudev-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install --locked qmassa@1.3.2

# Runtime stage
FROM python:3.13-slim-bookworm
COPY --from=builder /usr/local/cargo/bin/qmassa /usr/local/bin/qmassa
COPY qmassa_exporter.py /app/qmassa_exporter.py
EXPOSE 9820
ENTRYPOINT ["python3", "/app/qmassa_exporter.py"]
