FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

# Non-root user
RUN useradd -m -u 1000 -s /bin/bash omnius

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . /app/omnius/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER omnius
EXPOSE 8000

CMD ["uvicorn", "omnius.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
