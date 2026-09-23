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

ARG VERSION=unknown
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/bdelima/qmassa-exporter" \
      org.opencontainers.image.url="https://github.com/bdelima/qmassa-exporter" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
ENV APP_VERSION="${VERSION}"

EXPOSE 9820
ENTRYPOINT ["python3", "/app/qmassa_exporter.py"]
