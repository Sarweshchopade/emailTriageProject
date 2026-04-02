FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY environment ./environment
COPY scripts ./scripts
COPY data ./data
COPY tests ./tests
COPY openenv.yaml .
COPY README.md .

RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "scripts/evaluate.py", "--provider", "heuristic"]
