FROM ghcr.io/astral-sh/uv:0.8.15 AS uv
FROM python:3.13-slim-bookworm
COPY --from=uv /uv /bin/uv
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY apps/api apps/api
COPY tools/worker_smoke.py tools/worker_smoke.py
RUN uv sync --locked --no-dev --no-editable \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /srv/.data/private && chown -R app:app /srv/.data
ENV PATH="/srv/.venv/bin:$PATH"
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
