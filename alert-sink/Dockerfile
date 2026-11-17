FROM python:3.13-slim
WORKDIR /app
COPY sink.py .
RUN useradd --create-home appuser
USER appuser
EXPOSE 9000
CMD ["python", "-u", "sink.py"]
