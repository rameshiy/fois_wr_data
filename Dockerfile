FROM python:3.10.14-slim

WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/

# Create virtual environment and install dependencies
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt || { echo "Failed to install requirements"; exit 1; }

# Copy the rest of the application
COPY . /app

# Set proper permissions
RUN chown -R nobody:nogroup /app && \
    chmod -R 755 /app

# Use virtual environment's Python
ENV PATH="/app/venv/bin:$PATH"

# Run as non-root user for security
USER nobody

# Healthcheck to verify application
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "app.py"]
