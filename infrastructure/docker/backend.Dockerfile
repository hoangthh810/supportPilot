FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY infrastructure ./infrastructure

RUN pip install --no-cache-dir .

CMD ["uvicorn", "backend.apps.support_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
