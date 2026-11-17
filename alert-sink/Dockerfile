FROM python:3.13-slim
WORKDIR /app
COPY sink.py .
RUN useradd --uid 10001 --create-home appuser
USER 10001
EXPOSE 9000
CMD ["python", "-u", "sink.py"]
