#!/usr/bin/env bash
# Download the pinned Apache-2.0 Qwen weights and MIT llama.cpp Linux x86-64 CPU release.
set -euo pipefail
cache=${FIVEWHYS_MODEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/fivewhys/llama-b7757}
mkdir -p "$cache"
cd "$cache"

fetch_verified() {
    local file=$1 url=$2 checksum=$3 tmp
    if [[ -f "$file" ]] && echo "$checksum  $file" | sha256sum --check --status; then
        return
    fi
    tmp=$(mktemp "$file.download.XXXXXXXX")
    if ! curl --fail --location --retry 2 --output "$tmp" "$url" || ! echo "$checksum  $tmp" | sha256sum --check; then
        rm -f "$tmp"
        return 1
    fi
    mv "$tmp" "$file"
}

weights=qwen2.5-1.5b-instruct-q4_k_m.gguf
fetch_verified "$weights" \
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/$weights" \
    6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
fetch_verified llama.tar.gz \
    https://github.com/ggml-org/llama.cpp/releases/download/b7757/llama-b7757-bin-ubuntu-x64.tar.gz \
    e9f35bcb45d00ea44df60891f0d67c1c726b428ef056015fe67f7aaf0c04499c
tar -xzf llama.tar.gz
exec ./llama-b7757/llama-server -m "$weights" -a qwen2.5-1.5b-instruct \
    --host 127.0.0.1 --port "${FIVEWHYS_MODEL_PORT:-18081}" -t 3 -c 2048 -np 1
