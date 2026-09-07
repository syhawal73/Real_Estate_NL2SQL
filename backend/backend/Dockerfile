FROM python:3.12-slim

WORKDIR /app

# pip resilience for slow / flaky connections
ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=20 \
    PYTHONUNBUFFERED=1

# Install exact pinned dependencies straight from the lock-derived requirements.
# No Poetry in the image — smaller, faster, and one less large download to fail on.
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-deps -r requirements.txt

# Application code (bind-mounted over this in dev; baked in for standalone runs)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
