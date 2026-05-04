FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Many hosts (incl. AWS Elastic Beanstalk Docker) set PORT; local default 8080.
EXPOSE 8080
CMD ["/bin/sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]
