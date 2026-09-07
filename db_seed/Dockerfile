FROM python:3.12-slim

WORKDIR /seed

# Install dependencies
RUN pip install --no-cache-dir --default-timeout=120 --retries 10 psycopg2-binary

# Copy seed script and CSV data
COPY seed.py city_centers.csv properties.csv ./

CMD ["python", "seed.py"]
