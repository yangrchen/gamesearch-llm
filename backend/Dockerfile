FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

COPY . /app

WORKDIR /app

RUN uv sync --frozen

CMD ["uv", "run", "gamesearch-backend"]
