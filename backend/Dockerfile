FROM python:3.12-slim
ARG PYTHON_EXTRAS=""
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml ./
COPY backend ./backend
COPY evaluation ./evaluation
RUN if [ -n "$PYTHON_EXTRAS" ]; then pip install --no-cache-dir ".[${PYTHON_EXTRAS}]"; else pip install --no-cache-dir .; fi
RUN mkdir -p /app/artifacts /app/data/local && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20", "--no-server-header"]
