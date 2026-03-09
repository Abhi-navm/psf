# RunPod Deployment Guide

This guide explains how to deploy the Sales Pitch Analyzer on RunPod GPU cloud.

## Prerequisites

- RunPod account with GPU credits
- Docker Hub account (or other container registry)
- Git installed locally

## Architecture

The deployment runs all services in a single container:
- **Nginx** - Reverse proxy (port 80)
- **FastAPI Backend** - API server (port 8000)
- **Celery Worker** - Background task processing
- **Redis** - Task queue broker
- **Ollama** - LLM inference (llama3:8b)
- **Next.js Frontend** - Web UI (port 3000)

## Option 1: Deploy Pre-built Image

### Step 1: Build and Push Docker Image

```bash
# From project root directory
docker build -f Dockerfile.runpod -t yourusername/sales-pitch-analyzer:latest .

# Push to Docker Hub
docker login
docker push yourusername/sales-pitch-analyzer:latest
```

### Step 2: Create RunPod Pod

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click "Deploy" or "+ GPU Pod"
3. Select a GPU (recommended: RTX 3090/4090 or A10G for best performance)
4. Configure the pod:

| Setting | Value |
|---------|-------|
| Container Image | `yourusername/sales-pitch-analyzer:latest` |
| Volume Disk | 50 GB (for models and data) |
| Volume Mount Path | `/app/backend/data` |
| Expose HTTP Ports | `80, 8000` |
| Expose TCP Ports | `11434` (optional, for external Ollama) |

5. Add environment variables:
```
ENVIRONMENT=production
NEXT_PUBLIC_API_URL=https://your-pod-id-80.proxy.runpod.net
```

6. Click "Deploy"

### Step 3: Access Your Application

Once deployed, your application will be available at:
- Web UI: `https://your-pod-id-80.proxy.runpod.net`
- API: `https://your-pod-id-80.proxy.runpod.net/api/v1/`

## Option 2: Deploy with RunPod Template

### Create Custom Template

1. Go to RunPod Console → Templates
2. Click "New Template"
3. Fill in:

```yaml
Name: Sales Pitch Analyzer
Container Image: yourusername/sales-pitch-analyzer:latest
Docker Command: /app/start.sh
Volume Mount Path: /app/backend/data
Expose HTTP Ports: 80,8000
Environment Variables:
  ENVIRONMENT: production
```

4. Save and deploy from template

## GPU Recommendations

| GPU | VRAM | Performance | Cost (approx) |
|-----|------|-------------|---------------|
| RTX 3090 | 24GB | Good | $0.30/hr |
| RTX 4090 | 24GB | Excellent | $0.50/hr |
| A10G | 24GB | Good | $0.35/hr |
| A100 | 40/80GB | Best | $1.00+/hr |

Minimum recommended: 16GB VRAM for running Whisper + DeepFace + Ollama

## Volume Persistence

Mount a volume to `/app/backend/data` to persist:
- Uploaded videos
- Analysis results
- SQLite database
- Model caches

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | production | App environment |
| `DEBUG` | false | Enable debug mode |
| `NEXT_PUBLIC_API_URL` | http://localhost:8000 | API URL for frontend |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama API URL |
| `DATABASE_URL` | sqlite... | Database connection |
| `WHISPER_MODEL` | large-v3 | Whisper model (tiny/base/small/medium/large-v3) |
| `WHISPER_DEVICE` | cuda | Device for Whisper (cuda/cpu) |
| `EMBEDDING_DEVICE` | cuda | Device for sentence embeddings (cuda/cpu) |
| `DEEPFACE_DEVICE` | cuda | Device for DeepFace (cuda/cpu) |
| `FRAME_EXTRACTION_FPS` | 0.3 | Frames per second to extract (lower = faster) |
| `WEBHOOK_ENABLED` | false | Enable webhook notifications |
| `WEBHOOK_URL` | - | URL to call when analysis completes |

## GPU Configuration

All ML models are configured to use GPU by default:

| Component | Environment Variable | GPU Library |
|-----------|---------------------|-------------|
| Whisper | `WHISPER_DEVICE=cuda` | CTranslate2 + CUDA |
| Sentence Transformer | `EMBEDDING_DEVICE=cuda` | PyTorch CUDA |
| DeepFace | `DEEPFACE_DEVICE=cuda` | TensorFlow + CUDA |
| Ollama | (automatic) | Built-in CUDA |

### TensorFlow GPU Settings (automatic)
```bash
TF_FORCE_GPU_ALLOW_GROWTH=true  # Prevent TF from allocating all VRAM
TF_CPP_MIN_LOG_LEVEL=2          # Reduce TF logging
CUDA_VISIBLE_DEVICES=0          # Use first GPU
```

## Performance Optimizations

The application includes several optimizations for faster processing:

### 1. Faster-Whisper
Uses CTranslate2-based faster-whisper instead of OpenAI whisper:
- 2-4x faster transcription
- Lower memory usage
- VAD (Voice Activity Detection) to skip silence

### 2. Reduced Frame Sampling
Default: 0.3 fps (1 frame every 3.3 seconds)
- For 20-min video: ~360 frames instead of 1200 at 1fps
- Configure via `FRAME_EXTRACTION_FPS` environment variable

### 3. Model Pre-warming
Models are automatically pre-loaded on startup to eliminate cold start:
```bash
# Manual warm (if needed)
curl -X POST http://localhost:8000/warm

# Check warming status
curl http://localhost:8000/warm/status
```

### 4. Expected Processing Times (20-min video)

| GPU | Est. Time |
|-----|-----------|
| H100 | ~5-8 min |
| A100 80GB | ~8-12 min |
| A100 40GB | ~10-15 min |
| RTX 4090 | ~12-18 min |
| A10G | ~18-25 min |

## Webhook Integration

Get notified when analysis completes without polling:

### Configuration
```bash
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-server.com/webhook
WEBHOOK_TIMEOUT=30
```

### Webhook Payload
```json
{
  "event": "analysis_complete",
  "analysis_id": "uuid-here",
  "status": "completed",
  "overall_score": 75.5,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

For failures:
```json
{
  "event": "analysis_failed",
  "analysis_id": "uuid-here",
  "status": "failed",
  "error": "Error message",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Monitoring

### Check Logs
```bash
# SSH into pod via RunPod console, then:
tail -f /app/backend/logs/backend.out.log
tail -f /app/backend/logs/celery.out.log
tail -f /var/log/supervisor/supervisord.log
```

### Check Services
```bash
supervisorctl status
```

### Health Check
```bash
curl http://localhost:80/health
curl http://localhost:8000/health
```

## Troubleshooting

### Services not starting
```bash
# Check supervisor status
supervisorctl status

# Restart a service
supervisorctl restart backend
supervisorctl restart celery-worker

# View logs
cat /app/backend/logs/backend.err.log
```

### Ollama model not loading
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Manually pull model
ollama pull llama3:8b
```

### Out of GPU memory
- Reduce Celery concurrency in supervisord.conf
- Use a smaller model variant
- Upgrade to a larger GPU

### Frontend can't connect to API
- Check `NEXT_PUBLIC_API_URL` is set correctly
- Use the RunPod proxy URL format: `https://pod-id-port.proxy.runpod.net`

## Scaling

For production workloads:
1. Use RunPod Serverless for the inference pipeline
2. Deploy Redis externally (e.g., Redis Cloud)
3. Use PostgreSQL instead of SQLite
4. Put frontend behind a CDN

## Cost Optimization

- Use Spot instances for non-critical workloads
- Stop pods when not in use
- Use scheduled start/stop for predictable usage patterns
- Monitor GPU utilization and right-size

## Security Notes

- Change default ports if needed
- Use RunPod's built-in authentication
- Don't expose unnecessary ports
- Regularly update the container image

---

## Option 3: RunPod Serverless (Pay-Per-Second)

Serverless workers spin up only when a request arrives — you pay per second of compute, not per hour. Ideal for sporadic usage.

### How It Works

1. You push a Docker image with a `handler.py` that uses the `runpod` SDK
2. RunPod manages a pool of GPU workers (0 when idle → scale up on request)
3. You call the endpoint via REST API → RunPod routes to a warm/cold worker → result returned
4. Billing: GPU-seconds actually used + a small idle-worker charge if you keep workers warm

### Step 1: Build & Push Serverless Image

```bash
# From project root
docker build -f Dockerfile.serverless -t mortal7510/sales-pitch-analyzer:serverless .

docker push mortal7510/sales-pitch-analyzer:serverless
```

### Step 2: Create Serverless Endpoint on RunPod

1. Go to [RunPod Console → Serverless](https://www.runpod.io/console/serverless)
2. Click **"+ New Endpoint"**
3. Configure:

| Setting | Value |
|---------|-------|
| Endpoint Name | `sales-pitch-analyzer` |
| Container Image | `mortal7510/sales-pitch-analyzer:serverless` |
| GPU Type | A100 40GB (or A10G for budget) |
| Min Workers | 0 (scale to zero when idle) |
| Max Workers | 3 (cap concurrent requests) |
| Idle Timeout | 5 seconds |
| Execution Timeout | 600 seconds (10 min for long videos) |
| Container Disk | 20 GB |
| Volume Mount | `/app/backend/models` (optional, for model cache) |

4. Add environment variables:
```
WHISPER_DEVICE=cuda
WHISPER_MODEL=large-v3
EMBEDDING_DEVICE=cuda
DEEPFACE_DEVICE=cuda
```

5. Click **Deploy**

### Step 3: Call the Endpoint

RunPod provides you an **Endpoint ID** and an **API Key**.

#### Submit a Job (async)
```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "video_url": "https://example.com/my-pitch.mp4",
      "is_audio_only": false,
      "golden_reference": null,
      "frame_fps": 0.3
    }
  }'
```

Response:
```json
{
  "id": "job-abc123",
  "status": "IN_QUEUE"
}
```

#### Check Job Status
```bash
curl "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/status/job-abc123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

#### Synchronous Call (waits for result)
```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "video_url": "https://example.com/my-pitch.mp4"
    }
  }'
```

### Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video_url` | string | One of these | Public URL to the video file |
| `video_base64` | string | required | Base64-encoded video bytes |
| `is_audio_only` | bool | No | Skip facial/pose analysis (default: false) |
| `golden_reference` | dict | No | Golden pitch deck data for comparison |
| `frame_fps` | float | No | Frame extraction rate (default: 0.3) |

### Output Schema

```json
{
  "report": {
    "overall_score": 75.5,
    "voice_score": 80.0,
    "facial_score": 70.0,
    "pose_score": 65.0,
    "content_score": 85.0,
    "executive_summary": "...",
    "strengths": [...],
    "improvements": [...],
    "timestamped_issues": [...],
    "recommendations": [...]
  },
  "transcription": {
    "text": "Full transcript...",
    "segments": [...],
    "language": "en"
  },
  "timings": {
    "download": 2.1,
    "extraction": 3.5,
    "transcription": 8.2,
    "voice": 15.1,
    "facial": 4.3,
    "pose": 3.8,
    "content": 5.0,
    "report": 0.5,
    "total": 28.3
  }
}
```

### Golden Reference Comparison (Serverless)

To compare against a golden pitch deck in serverless mode, pass the reference data directly in the request:

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "video_url": "https://example.com/my-pitch.mp4",
      "golden_reference": {
        "id": "golden-1",
        "name": "Q1 Sales Pitch",
        "is_processed": true,
        "keywords": ["revenue", "growth", "roi"],
        "key_phrases": ["increase revenue", "proven results"],
        "voice_metrics": { ... },
        "pose_metrics": { ... },
        "facial_metrics": { ... },
        "content_metrics": { ... },
        "transcript": "The golden pitch transcript..."
      }
    }
  }'
```

### Cost Comparison: Pods vs Serverless

| Scenario | Pod (A100 40GB) | Serverless (A100 40GB) |
|----------|-----------------|------------------------|
| Always-on 24/7 | ~$24/day | N/A |
| 10 analyses/day (~5 min each) | ~$24/day | ~$0.80/day |
| 50 analyses/day (~5 min each) | ~$24/day | ~$4.00/day |
| 200 analyses/day | ~$24/day | ~$16/day |

> **Note:** Serverless has cold-start overhead (30-60s) when workers scale from 0. Set Min Workers = 1 to keep one worker warm (small idle charge) for faster response times.

### Architecture: Pod vs Serverless

**Pod (Option 1/2):** Full stack in one container — frontend, backend API, Celery, Redis, Ollama, Nginx. Good for development and demo.

**Serverless (Option 3):** GPU inference only — handler receives video URL, runs the ML pipeline, returns results. No frontend/DB/Celery. Integrate into your own backend via REST API.
