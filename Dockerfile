FROM python:3.13-slim

WORKDIR /app
COPY app ./app
COPY samples ./samples
COPY VERSION ./VERSION

ENV PYTHONUNBUFFERED=1
ENV APAFIN_PORT=8080
EXPOSE 8080

CMD ["python", "-m", "app.server"]
