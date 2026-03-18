#!/usr/bin/env bash
# Switch PersonaPlex on EC2 to brianmatzelle/personaplex-7b-v1-bnb-4bit (pre-quantized).
# Run this ON THE EC2 HOST from the personaplex app dir (e.g. /home/ubuntu/personaplex).
#
# Prereqs:
# - /home/ubuntu/model_bnb_4bit.pt exists (download from HF or copy).
# - .env has HF_TOKEN (for nvidia/personaplex-7b-v1 voices + mimi).
# - Docker and docker compose available.
# - Enough free disk (Docker build needs ~10GB+). If "no space left": docker system prune -a, rm -rf /tmp/tmp.*, or expand the volume.
#
# What this does:
# - Fetches brianmatzelle's modified moshi/ (supports --moshi-weight pre-quantized .pt).
# - Replaces local moshi/ with it and adds --moshi-weight /app/model_bnb_4bit.pt to the server command.
# - Rebuilds the image and restarts the container. Voices/mimi/tokenizer still come from nvidia repo.

set -e
PERSONAPLEX_DIR="${1:-/home/ubuntu/personaplex}"
BNB_MODEL="${2:-/home/ubuntu/model_bnb_4bit.pt}"

if [[ ! -d "$PERSONAPLEX_DIR" ]]; then
  echo "Usage: $0 [personaplex_dir] [model_bnb_4bit.pt path]"
  echo "Default: personaplex_dir=$PERSONAPLEX_DIR, model=$BNB_MODEL"
  exit 1
fi

if [[ ! -f "$BNB_MODEL" ]]; then
  echo "Error: Pre-quantized model not found at $BNB_MODEL"
  echo "Download with: huggingface-cli download brianmatzelle/personaplex-7b-v1-bnb-4bit model_bnb_4bit.pt --local-dir /home/ubuntu"
  exit 1
fi

cd "$PERSONAPLEX_DIR"
echo "Working in $PERSONAPLEX_DIR"

# Fetch brianmatzelle's moshi (replace existing)
MOSHI_TMP=$(mktemp -d)
trap "rm -rf $MOSHI_TMP" EXIT
echo "Fetching brianmatzelle moshi package (skip LFS - we use existing model_bnb_4bit.pt)..."
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://huggingface.co/brianmatzelle/personaplex-7b-v1-bnb-4bit "$MOSHI_TMP/repo"
rm -rf "$MOSHI_TMP/repo/.git"
if [[ -d moshi ]]; then
  mv moshi "moshi.bak.$(date +%Y%m%d%H%M%S)"
fi
mv "$MOSHI_TMP/repo/moshi" .

# Update docker-compose to use pre-quantized weight
COMPOSE="docker-compose.yaml"
if [[ ! -f "$COMPOSE" ]]; then
  echo "Error: $COMPOSE not found"
  exit 1
fi

# Ensure command includes --moshi-weight and --quantize-4bit (hf-repo stays default nvidia for voices)
if grep -q '"--moshi-weight"' "$COMPOSE"; then
  echo "docker-compose already has --moshi-weight"
else
  cp "$COMPOSE" "$COMPOSE.bak"
  # Add --moshi-weight /app/model_bnb_4bit.pt before "--quantize-4bit"
  sed -i 's|"--quantize-4bit"|"--moshi-weight", "/app/model_bnb_4bit.pt", "--quantize-4bit"|' "$COMPOSE" || true
  if ! grep -q '"--moshi-weight"' "$COMPOSE"; then
    echo "Could not auto-update $COMPOSE. Add to command: --moshi-weight /app/model_bnb_4bit.pt"
    exit 1
  fi
fi

# Use BuildKit cache mount for uv so cache lives in Docker storage (on nvme if data-root was moved)
if grep -q 'RUN uv sync' Dockerfile && ! grep -q 'UV_CACHE_DIR=/build_cache' Dockerfile; then
  cp Dockerfile Dockerfile.bak
  sed -i 's|^RUN uv sync|RUN --mount=type=cache,target=/build_cache UV_CACHE_DIR=/build_cache TMPDIR=/build_cache uv sync|' Dockerfile
fi

echo "Rebuilding Docker image (BuildKit, cache on nvme if available)..."
DOCKER_BUILDKIT=1 docker compose build --no-cache

echo "Restarting container..."
docker compose down
docker compose up -d

echo "Done. Container will take a few minutes to load the pre-quantized model. Check: docker logs -f \$(docker compose ps -q personaplex)"
