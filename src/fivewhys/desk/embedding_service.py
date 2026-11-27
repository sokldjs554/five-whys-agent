"""Serve a pinned ONNX sentence encoder. Model files stay outside the repository."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI
from pydantic import BaseModel, Field
from tokenizers import Tokenizer


class Batch(BaseModel):
    texts: list[Annotated[str, Field(min_length=1, max_length=8192)]] = Field(min_length=1, max_length=32)


@asynccontextmanager
async def lifespan(app):
    root = Path(os.environ["DESK_ENCODER_DIR"])
    tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=128)
    tokenizer.enable_padding(pad_id=tokenizer.token_to_id("<pad>"), pad_token="<pad>")
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(str(root / "encoder.onnx"), sess_options=opts,
                                   providers=["CPUExecutionProvider"])
    app.state.encoder = (tokenizer, session)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/embeddings")
def encode(batch: Batch):
    tokenizer, session = app.state.encoder
    tokens = tokenizer.encode_batch(batch.texts)
    fields = {"attention_mask":"attention_mask", "input_ids":"ids", "token_type_ids":"type_ids"}
    inputs = {arg.name: np.array([getattr(row, fields[arg.name]) for row in tokens], dtype=np.int64)
              for arg in session.get_inputs()}
    hidden = session.run(None, inputs)[0]
    mask = inputs["attention_mask"][:, :, None]
    pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
    pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)
    return {"model":"paraphrase-multilingual-MiniLM-L12-v2", "vectors":pooled.tolist()}
