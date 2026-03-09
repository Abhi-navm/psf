#!/bin/bash
set -e

echo "=========================================="
echo "Starting Sales Pitch Analyzer on RunPod"
echo "=========================================="

# Create necessary directories
mkdir -p /app/backend/data/uploads/videos
mkdir -p /app/backend/data/uploads/temp
mkdir -p /app/backend/data/uploads/golden_pitch_decks
mkdir -p /app/backend/data/uploads/analyses
mkdir -p /app/backend/logs
mkdir -p /root/.ollama

# Set environment variables
export ENVIRONMENT=${ENVIRONMENT:-production}
export DEBUG=${DEBUG:-false}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-redis://localhost:6379/0}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}
export DATABASE_URL=${DATABASE_URL:-sqlite+aiosqlite:///./data/sales_analyzer.db}
export OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
export NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
export WHISPER_MODEL=${WHISPER_MODEL:-large-v3}
export WHISPER_DEVICE=${WHISPER_DEVICE:-cuda}
export EMBEDDING_DEVICE=${EMBEDDING_DEVICE:-cuda}
export DEEPFACE_DEVICE=${DEEPFACE_DEVICE:-cuda}

# TensorFlow GPU configuration (for DeepFace)
export TF_FORCE_GPU_ALLOW_GROWTH=true
export TF_CPP_MIN_LOG_LEVEL=2
export CUDA_VISIBLE_DEVICES=0

# Prevent HuggingFace HTTP calls (models are pre-cached in image)
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Start Redis in background
echo "Starting Redis..."
redis-server --daemonize yes --maxmemory 1gb --maxmemory-policy allkeys-lru

# Wait for Redis
until redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 1
done
echo "Redis is ready!"

# Start Ollama in background
echo "Starting Ollama..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
sleep 5
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    echo "Waiting for Ollama..."
    sleep 2
done
echo "Ollama is ready!"

# Pull the LLM model if not present
echo "Checking for Llama model..."
if ! ollama list | grep -q "llama3:8b"; then
    echo "Pulling llama3:8b model (this may take a while)..."
    ollama pull llama3:8b
fi
echo "LLM model ready!"

# Start supervisord to manage all processes
echo "Starting application services..."
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf &

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 10
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    echo "Waiting for backend..."
    sleep 2
done
echo "Backend is ready!"

# Pre-warm ML models for faster first request
echo "Pre-warming ML models..."
curl -X POST http://localhost:8000/warm || true
echo "Model warming initiated!"

# Keep container running
wait
