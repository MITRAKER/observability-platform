# One Dockerfile is shared by all three services.
# The build arg SERVICE picks which folder gets copied in.
FROM python:3.13-slim

ARG SERVICE
WORKDIR /app

# Install dependencies first so Docker can cache this layer.
# Changing your code will not force a re-install of every package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ${SERVICE}/ .

# Run as a non-root user: a small security habit worth showing on a resume.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
