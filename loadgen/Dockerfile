FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir httpx==0.28.1
COPY loadgen.py .
# Run as a non-root user with a numeric id (works on any host).
RUN useradd --uid 10001 --create-home appuser
USER 10001
CMD ["python", "loadgen.py"]
