FROM python:3.12.11-slim-bookworm
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.8.4 && uv sync --frozen --no-dev
COPY platform platform
COPY plugins plugins
COPY shared shared
COPY frontend/dist frontend/dist
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["/app/.venv/bin/python","-c","import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)"]
ENTRYPOINT ["/app/.venv/bin/ai-agent-api"]
