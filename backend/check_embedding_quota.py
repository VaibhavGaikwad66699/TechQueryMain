"""One tiny embedding call; prints only structured quota/retry metadata on failure."""
import json
from app.core.config import settings
from google import genai
from google.genai import types


def main():
    client = genai.Client(api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=10000, retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        response = client.models.embed_content(model=settings.EMBEDDING_MODEL,
            contents='A Java interface defines a contract.',
            config=types.EmbedContentConfig(task_type='RETRIEVAL_QUERY', output_dimensionality=settings.EMBEDDING_DIMENSIONS))
        print(json.dumps({'ok': True, 'dimensions': len(response.embeddings[0].values)}))
    except Exception as exc:
        raw = getattr(exc, 'details', {}) or {}
        error = raw.get('error', raw) if isinstance(raw, dict) else {}
        details = error.get('details', [])
        result = {'ok': False, 'code': getattr(exc, 'code', None), 'status': getattr(exc, 'status', None), 'retry': [], 'quota': []}
        for detail in details:
            if not isinstance(detail, dict):
                continue
            if detail.get('@type', '').endswith('RetryInfo'):
                result['retry'].append({'retryDelay': detail.get('retryDelay')})
            if detail.get('@type', '').endswith('QuotaFailure'):
                for violation in detail.get('violations', []):
                    result['quota'].append({k: violation[k] for k in ('quotaMetric', 'quotaId', 'quotaValue') if k in violation})
        print(json.dumps(result))
    finally:
        client.close()


if __name__ == '__main__':
    main()
