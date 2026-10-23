"""Validated, bounded embedding calls with explicit retrieval task types."""
import hashlib
import json
import logging
import math
import time
from typing import List, Optional

import numpy as np
from app.core.config import settings

logger = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_metadata(raw):
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def provider_failure(exc):
    """Whitelist operational error fields; never return keys, URLs or prompt text."""
    result = {"error_type": type(exc).__name__, "code": getattr(exc, "code", None), "status": getattr(exc, "status", None)}
    raw = getattr(exc, "details", {}) or {}
    if isinstance(raw, dict):
        error = raw.get("error", raw)
        for detail in error.get("details", []):
            if not isinstance(detail, dict):
                continue
            if detail.get("@type", "").endswith("RetryInfo"):
                result["retry_delay"] = detail.get("retryDelay")
            if detail.get("@type", "").endswith("QuotaFailure"):
                result["quota"] = [{k: violation[k] for k in ("quotaMetric", "quotaId", "quotaValue") if k in violation} for violation in detail.get("violations", [])]
    return result


class EmbeddingService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if not self.is_configured():
            return None
        if self._client is None:
            from google import genai
            from google.genai import types
            self._client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=settings.PROVIDER_TIMEOUT_MS,
                    retry_options=types.HttpRetryOptions(attempts=1)),
            )
        return self._client

    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here")

    @staticmethod
    def valid_vector(vector, dimensions=None):
        return (isinstance(vector, list) and len(vector) == (dimensions or settings.EMBEDDING_DIMENSIONS)
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vector)
            and any(v != 0 for v in vector))

    def compatible_vector(self, chunk):
        """Reject an unknown model, task, dimension or changed source content."""
        provenance = read_metadata(chunk.metadata_json).get("embedding", {})
        if not isinstance(provenance, dict) or provenance != self.provenance(chunk.content):
            return None
        try:
            vector = json.loads(chunk.embedding_json or "null")
        except (TypeError, ValueError):
            return None
        return vector if self.valid_vector(vector) else None

    @staticmethod
    def provenance(text):
        return {"version": 1, "model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIMENSIONS, "task_type": "RETRIEVAL_DOCUMENT",
            "content_sha256": content_hash(text)}

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        return self.generate_embeddings_batch([text], task_type="RETRIEVAL_QUERY")[0]

    def generate_embeddings_batch(self, texts: List[str], batch_size=None, task_type="RETRIEVAL_DOCUMENT") -> List[List[float]]:
        if not texts:
            return []
        client = self._get_client()
        if client is None:
            raise ValueError("Gemini API key is not configured")
        from google.genai import types
        size = batch_size or settings.EMBEDDING_BATCH_SIZE
        if not 1 <= size <= 100:
            raise ValueError("Embedding batch size must be between 1 and 100")
        results = []
        for start in range(0, len(texts), size):
            batch = texts[start:start + size]
            for attempt in range(settings.EMBEDDING_MAX_ATTEMPTS):
                try:
                    response = client.models.embed_content(model=settings.EMBEDDING_MODEL, contents=batch,
                        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=settings.EMBEDDING_DIMENSIONS))
                    vectors = [list(emb.values) for emb in (response.embeddings or [])]
                    if len(vectors) != len(batch) or not all(self.valid_vector(v) for v in vectors):
                        raise ValueError("Embedding response count or vector dimensions are invalid")
                    results.extend(vectors)
                    break
                except Exception as exc:
                    code = getattr(exc, "code", None)
                    import httpx
                    retryable = code in {408, 429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))
                    retry_delay = provider_failure(exc).get("retry_delay", "0s")
                    try:
                        wait_seconds = float(str(retry_delay).removesuffix("s"))
                    except (TypeError, ValueError):
                        wait_seconds = 0
                    # A minute/day quota cannot recover during our short retry
                    # budget. Return it immediately for paced/manual resumption.
                    if code == 429 and wait_seconds > 4:
                        raise
                    if not retryable or attempt + 1 == settings.EMBEDDING_MAX_ATTEMPTS:
                        raise
                    logger.warning("Retrying embedding request (%s, code=%s)", type(exc).__name__, code)
                    time.sleep(min(2 ** attempt, 4))
        return results

    @staticmethod
    def cosine_similarity(v1, v2) -> float:
        a, b = np.asarray(v1, dtype=np.float32), np.asarray(v2, dtype=np.float32)
        if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            return 0.0
        norms = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / norms) if norms else 0.0


embedding_service = EmbeddingService()
