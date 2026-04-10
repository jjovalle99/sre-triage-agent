FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Download eShop at pinned commit (tarball — no git overhead)
ARG ESHOP_SHA=b81ad9557090cc37233b9d1a0a729db7b44b6f14
RUN mkdir -p /app/eshop && \
    curl -sL https://github.com/dotnet/eShop/archive/${ESHOP_SHA}.tar.gz \
    | tar -xz --strip-components=1 -C /app/eshop

COPY scripts/generate-eshop-map.sh /app/scripts/
RUN bash /app/scripts/generate-eshop-map.sh /app/eshop /app/eshop-map.md

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ ./app/

RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
