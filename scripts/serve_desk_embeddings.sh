#!/usr/bin/env bash
set -euo pipefail
: "${DESK_ENCODER_DIR:=.fivewhys/models/minilm-e8f8c21}"
export DESK_ENCODER_DIR
mkdir -p "$DESK_ENCODER_DIR"
revision=e8f8c211226b894fcb81acc59f3b34ba3efd5f42
origin="https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/$revision"

fetch() {
    local name=$1 path=$2 digest=$3
    local target="$DESK_ENCODER_DIR/$name"
    if ! echo "$digest  $target" | sha256sum --check --status; then
        local tmp
        tmp=$(mktemp "$DESK_ENCODER_DIR/.download.XXXXXX")
        if ! curl --fail --location --retry 2 "$origin/$path" --output "$tmp" ||
           ! echo "$digest  $tmp" | sha256sum --check --status; then
            rm -f "$tmp"
            return 1
        fi
        mv "$tmp" "$target"
    fi
}
fetch encoder.onnx onnx/model_quint8_avx2.onnx 98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f
fetch tokenizer.json tokenizer.json 2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8
exec python -m uvicorn fivewhys.desk.embedding_service:app --host 127.0.0.1 --port "${DESK_ENCODER_PORT:-18082}"
