FROM python:3.12-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app

# 開発用: ソースは compose でマウントする
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

# ステージング・本番用
FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY . .
EXPOSE 8000
# 1 つの処理が固まっても他のリクエストを受けられるよう、スレッドでも並行に処理する
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "60", "--bind", "0.0.0.0:8000", "app:create_app()"]
