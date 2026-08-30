FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-pip \
        python3-venv \
        docker.io \
        docker-compose-v2 \
    && rm -rf /var/lib/apt/lists/*
