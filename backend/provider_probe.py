"""Small live diagnostic. Never prints credentials or raw provider errors."""
import json
import argparse
from app.core.config import settings
from google import genai
from google.genai import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation-model', default=settings.GEMINI_MODEL)
    args = parser.parse_args()
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=15000, retry_options=types.HttpRetryOptions(attempts=1)),
    )
    for model in (settings.EMBEDDING_MODEL, args.generation_model):
        try:
            info = client.models.get(model=model)
            print(json.dumps({"check": "model_access", "model": model, "ok": True, "actions": info.supported_actions}), flush=True)
        except Exception as exc:
            print(json.dumps({"check": "model_access", "model": model, "ok": False, "error_type": type(exc).__name__, "code": getattr(exc, "code", None)}), flush=True)
    try:
        result = client.models.embed_content(model=settings.EMBEDDING_MODEL, contents=["A Java interface defines a contract."], config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768))
        print(json.dumps({"check": "embedding_call", "ok": True, "dimensions": len(result.embeddings[0].values)}), flush=True)
    except Exception as exc:
        print(json.dumps({"check": "embedding_call", "ok": False, "error_type": type(exc).__name__, "code": getattr(exc, "code", None)}), flush=True)
    try:
        result = client.models.generate_content(model=args.generation_model, contents="Reply with exactly OK.", config={"max_output_tokens": 128})
        print(json.dumps({"check": "generation_call", "ok": bool(result.text), "reply": result.text}), flush=True)
    except Exception as exc:
        print(json.dumps({"check": "generation_call", "ok": False, "error_type": type(exc).__name__, "code": getattr(exc, "code", None)}), flush=True)
    client.close()


if __name__ == "__main__":
    main()
