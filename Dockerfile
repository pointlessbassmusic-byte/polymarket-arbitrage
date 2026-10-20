# Trading desk: funding carry + bounce-short, paper by default.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt requirements-live.txt ./
RUN pip install --no-cache-dir httpx pyyaml fastapi uvicorn \
 && pip install --no-cache-dir -r requirements-live.txt

COPY cryptobot ./cryptobot
COPY cryptobot_config.yaml ./

# Books persist here; mount a volume so restarts and upgrades lose nothing.
VOLUME ["/data"]
EXPOSE 8080

# Binding 0.0.0.0 inside the container is fine: compose publishes the port
# on 127.0.0.1 only, and the dashboard pins the Host header and needs a token.
CMD ["python", "-m", "cryptobot.desk", "--host", "0.0.0.0", "--port", "8080", \
     "--state-dir", "/data", "--config", "/app/cryptobot_config.yaml"]
