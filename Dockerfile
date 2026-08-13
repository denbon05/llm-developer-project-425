# Application services (ticketing; email-gateway arrives in Phase 4).
# PYTHON_VERSION comes from .python-version via compose/Make build-arg.
# Dependencies via uv --frozen.
ARG PYTHON_VERSION
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

# Rebuild/sync for dependency changes.
CMD ["uv", "run", "ticketing"]
