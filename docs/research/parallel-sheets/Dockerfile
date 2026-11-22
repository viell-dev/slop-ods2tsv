FROM rust:1.99.1-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 time patch \
    && rm -rf /var/lib/apt/lists/*
