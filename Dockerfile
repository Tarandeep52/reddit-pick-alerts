FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alerts ./alerts
COPY main.py ./

# Mount a volume at /data holding config.yaml and state.json.
# Pass secrets with --env-file .env  (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
VOLUME ["/data"]
CMD ["python", "main.py", "--config", "/data/config.yaml"]
