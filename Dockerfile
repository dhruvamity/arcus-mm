# Arcus paper trading bot: records public Arcus market data and scores the frozen strategies.
# No API keys, no orders (mainnet order lock on). All state lives in /app/data (mount a volume).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    ARCUS_ENVIRONMENT=mainnet ARCUS_MAINNET_ORDER_LOCK=true ARCUS_PAPER_TRADING_MODE=true \
    ARCUS_DISK_ALARM_GB=5

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs

VOLUME /app/data
# healthy while the bot has written its status file in the last 5 minutes
HEALTHCHECK --interval=2m --timeout=10s --start-period=3m CMD python -c "import json,sys,datetime as d;s=json.load(open('/app/data/paper/status.json'));t=d.datetime.fromisoformat(s['updated_utc']);sys.exit(0 if s['recorder_alive'] and (d.datetime.now(d.timezone.utc)-t).total_seconds()<300 else 1)"

ENTRYPOINT ["python", "scripts/paper_bot.py"]
CMD ["run"]
