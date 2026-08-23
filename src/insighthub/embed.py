"""Embeddings, with a pluggable backend and an on-disk cache.

Chapter 3 §3.4.

Backends:
  local  - sentence-transformers/all-MiniLM-L6-v2, runs on your machine, free.
           The default. ~90MB download on first use.
  hash   - a deterministic hashing "embedder" with NO semantics. It exists so the
           test suite and CI can run without a model download. It will make your
           retrieval look terrible, which is the point: if you accidentally leave
           it on, you will notice immediately.

Why not a hosted embedding API? You can use one, and in production you often
should (better quality, no local GPU, one less dependency). Set
INSIGHTHUB_EMBED_BACKEND and write a backend here. The reason the default is
local is pedagogical: Chapter 3 wants you to see cosine similarity work on
vectors you can print, not to treat retrieval as a service you call.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import numpy as np

from .config import INDEX_DIR

BACKEND = os.getenv("INSIGHTHUB_EMBED_BACKEND", "local")
LOCAL_MODEL = os.getenv("INSIGHTHUB_EMBED_MODEL",
                        "sentence-transformers/all-MiniLM-L6-v2")
HASH_DIM = 384

_model = None
_cache: dict[str, np.ndarray] = {}
_CACHE_PATH = INDEX_DIR / f"embed_cache_{BACKEND}.npz"


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(LOCAL_MODEL)
    return _model


_TOKEN = re.compile(r"[a-z0-9']+")


def _hash_embed(texts: list[str]) -> np.ndarray:
    """Deterministic bag-of-hashed-ngrams. No semantics whatsoever."""
    out = np.zeros((len(texts), HASH_DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        toks = _TOKEN.findall(t.lower())
        grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for g in grams:
            h = int(hashlib.blake2b(g.encode(), digest_size=8).hexdigest(), 16)
            out[i, h % HASH_DIM] += 1.0
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.clip(norms, 1e-9, None)


def _load_cache() -> None:
    if _cache or not _CACHE_PATH.exists():
        return
    with np.load(_CACHE_PATH, allow_pickle=True) as z:
        keys, vals = z["keys"], z["vals"]
    for k, v in zip(keys, vals):
        _cache[str(k)] = v


def _save_cache() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    keys = np.array(list(_cache), dtype=object)
    vals = np.stack(list(_cache.values())) if _cache else np.zeros((0, HASH_DIM))
    np.savez_compressed(_CACHE_PATH, keys=keys, vals=vals)


def _key(text: str) -> str:
    return hashlib.blake2b(text.encode(), digest_size=16).hexdigest()


def embed_texts(texts: list[str], *, use_cache: bool = True,
                batch_size: int = 64) -> np.ndarray:
    """Embed a list of strings. Returns L2-normalised float32 (n, d).

    Normalised vectors mean cosine similarity is just a dot product, which keeps
    the search code in index.py to one line you can actually read.
    """
    if use_cache:
        _load_cache()
    keys = [_key(t) for t in texts]
    missing = [(i, t) for i, (k, t) in enumerate(zip(keys, texts))
               if not use_cache or k not in _cache]

    if missing:
        new_texts = [t for _, t in missing]
        if BACKEND == "hash":
            vecs = _hash_embed(new_texts)
        else:
            vecs = _load_model().encode(
                new_texts, batch_size=batch_size, show_progress_bar=len(new_texts) > 200,
                normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
        for (i, _), v in zip(missing, vecs):
            _cache[keys[i]] = v
        if use_cache:
            _save_cache()

    return np.stack([_cache[k] for k in keys]).astype(np.float32)


def embed_one(text: str) -> np.ndarray:
    return embed_texts([text])[0]


def dim() -> int:
    return HASH_DIM if BACKEND == "hash" else embed_one("probe").shape[0]


def backend_warning() -> str | None:
    if BACKEND == "hash":
        return ("INSIGHTHUB_EMBED_BACKEND=hash — retrieval quality will be poor by "
                "design. Unset it to use the real local model.")
    return None
