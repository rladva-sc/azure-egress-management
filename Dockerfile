FROM python:3.10-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config.json.template ./config.json

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Create necessary directories
RUN mkdir -p /app/data/raw /app/data/processed /app/data/reports /app/logs

# Create a non-root user to run the app
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Set up entrypoint and default command
ENTRYPOINT ["python", "-m"]
CMD ["src.dashboard.app"]

# Default ports
EXPOSE 8050
