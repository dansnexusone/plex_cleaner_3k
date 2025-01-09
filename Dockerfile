# Stage 1: Build environment
FROM python:3.12-slim AS build-env

WORKDIR /app

COPY requirements.txt .

RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Stage 2: Final image
FROM python:3.12-slim

WORKDIR /app

COPY --from=build-env /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build-env /usr/local/bin/ /usr/local/bin/

COPY *.py /app/
COPY models/ /app/models/
COPY services/ /app/services/

ENV PYTHONPATH=/app

ENTRYPOINT ["python", "/app/main.py"]
