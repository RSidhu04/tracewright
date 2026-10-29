FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements-tested.txt README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements-tested.txt && pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 tracewright
COPY scripts ./scripts
RUN mkdir /data && chown tracewright:tracewright /data
USER tracewright
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"
CMD ["uvicorn", "tracewright.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
