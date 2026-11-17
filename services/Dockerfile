# One Dockerfile is shared by all three services.
# The build arg SERVICE picks which folder gets copied in.
FROM python:3.15-slim

ARG SERVICE
WORKDIR /app

# Install dependencies first so Docker can cache this layer.
# Changing your code will not force a re-install of every package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ${SERVICE}/ .

# Run as a non-root user: a small security habit worth showing on a resume.
RUN useradd --uid 10001 --create-home appuser
USER 10001

EXPOSE 8000
# `opentelemetry-instrument` wraps the normal start command. Before the app
# starts, it finds the installed instrumentation packages (FastAPI, httpx,
# logging) and patches them, then reads OTEL_* environment variables to know
# where to send data. The app code needs no tracing setup of its own.
CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
