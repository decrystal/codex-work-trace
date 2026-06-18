FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CSGS_DB=/data/csgs.sqlite3 \
    CSGS_HOST=0.0.0.0 \
    CSGS_PORT=8765

WORKDIR /app

RUN useradd --system --create-home --home-dir /home/csgs --shell /usr/sbin/nologin csgs

COPY pyproject.toml README.md ./
COPY csgs ./csgs

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[mcp]" \
    && mkdir -p /data \
    && chown -R csgs:csgs /data /app

USER csgs

EXPOSE 8765
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json, urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3))['status'] == 'ok'"

CMD ["csgs", "--db", "/data/csgs.sqlite3", "serve", "--host", "0.0.0.0", "--port", "8765", "--transport", "streamable-http"]
