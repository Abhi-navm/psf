FROM python:3.11-slim

WORKDIR /app

# System deps (ffmpeg for video metadata, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first (saves ~1.5GB vs CUDA version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "setuptools<82" && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/uploads/videos data/uploads/temp \
             data/uploads/golden_pitch_decks logs

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]