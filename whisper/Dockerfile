FROM python:3.12-slim

RUN pip install --no-cache-dir faster-whisper flask

COPY server.py /app/server.py

WORKDIR /app
EXPOSE 9090

CMD ["python", "server.py"]
