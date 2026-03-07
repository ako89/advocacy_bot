FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies before copying source so this layer is cached
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Run as non-root
RUN useradd -m botuser && mkdir -p /app/data && chown -R botuser /app
USER botuser

CMD ["/app/.venv/bin/python", "-m", "advocacy_bot.bot"]
