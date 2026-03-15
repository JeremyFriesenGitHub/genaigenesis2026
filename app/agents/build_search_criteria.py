"""
Extract structured search criteria from a conversation/transcript using Railtracks.
"""
import asyncio
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

logging.getLogger("LiteLLM").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = ROOT / "templates" / "build_search_criteria"
LOCAL_SITE_PACKAGES = ROOT / ".p"

if LOCAL_SITE_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_SITE_PACKAGES))


def _render_prompt(name: str, **context) -> str:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    template = env.get_template(f"{name}.jinja")
    return template.render(**context).strip()


def _get_llm():
    """Use railtracks OpenAI-compatible provider for the hackathon endpoint."""
    from dotenv import load_dotenv
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "") or "not-set"
    import railtracks as rt
    provider = getattr(rt.llm, "OpenAICompatibleProvider", None) or getattr(rt.llm, "OpenAICompatibleLLM", None)
    if provider is None:
        raise RuntimeError("railtracks has no OpenAICompatibleProvider or OpenAICompatibleLLM")
    return provider(
        GPT_OSS_MODEL,
        api_base=GPT_OSS_BASE_URL.rstrip("/"),
        api_key=api_key,
    )


def _default_criteria() -> dict:
    return {
        "location": {
            "query": "",
            "city": None,
            "state_province": None,
            "postal_code": None,
            "neighborhood": None,
        },
        "intent": "rent",
        "price": {"min": None, "max": None},
        "bedrooms": {"min": None, "max": None},
        "bathrooms": {"min": None, "max": None},
        "property_type": [],
        "size": {
            "sqft_min": None,
            "sqft_max": None,
            "lot_sqft_min": None,
            "lot_sqft_max": None,
        },
        "year_built": {"min": None, "max": None},
        "features": {"required": [], "nice_to_have": []},
        "keywords": [],
        "sort": {"field": "relevant", "direction": "desc"},
        "page": 1,
        "page_size": 20,
    }


def _parse_response_json(text: str) -> dict:
    text = (text or "").strip()
    if "```" in text:
        start = text.find("```")
        if "json" in text[: start + 10]:
            start = text.find("\n", start) + 1
        end = text.find("```", start)
        text = text[start:end] if end > start else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _default_criteria()


ENDPOINT_TIMEOUT_S = 10


def _hit_endpoint(base_url: str, model: str, api_key: str,
                   system_prompt: str, user_prompt: str,
                   timeout: int = ENDPOINT_TIMEOUT_S) -> dict:
    """Single attempt against one base_url. Raises on failure/timeout."""
    import time
    payload = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    logging.info("Endpoint %s responded in %.2fs", base_url[:60], elapsed)
    text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_response_json(text)


def _call_openai_compatible(system_prompt: str, user_prompt: str) -> dict:
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_BASE_URL_FALLBACK, GPT_OSS_MODEL
    api_key = os.getenv("OPENAI_API_KEY", "")
    endpoints = [u for u in [GPT_OSS_BASE_URL, GPT_OSS_BASE_URL_FALLBACK] if u]
    last_err = None
    for i, base_url in enumerate(endpoints):
        label = "primary" if i == 0 else "fallback"
        try:
            logging.info("Trying %s endpoint: %s", label, base_url[:60])
            return _hit_endpoint(base_url, GPT_OSS_MODEL, api_key,
                                  system_prompt, user_prompt)
        except Exception as e:
            last_err = e
            logging.warning("%s endpoint failed (%s), trying next...", label, e)
    raise RuntimeError(f"All HF endpoints failed. Last error: {last_err}")


def extract_search_criteria(transcript: str) -> dict:
    """
    Run the build-search-criteria agent on a transcript (Railtracks + GPT-OSS).
    Returns a structured dict with location, intent, price, bedrooms, bathrooms,
    property_type, size, year_built, features, keywords, sort, and pagination.
    """
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL
    if not GPT_OSS_BASE_URL or not GPT_OSS_MODEL:
        raise ValueError(
            "Set GPT_OSS_BASE_URL and GPT_OSS_MODEL in .env (see .env.example)."
        )
    os.environ.setdefault("OPENAI_BASE_URL", GPT_OSS_BASE_URL.rstrip("/"))
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ.setdefault("OPENAI_API_KEY", "not-set")
    system_prompt = _render_prompt("system_prompt")
    user_prompt = _render_prompt("user_prompt", transcript=transcript)
    try:
        import railtracks as rt
        if hasattr(rt, "llm") and hasattr(rt, "agent_node") and hasattr(rt, "call"):
            llm = _get_llm()
            agent = rt.agent_node(
                name="Build Search Criteria",
                llm=llm,
                system_message=system_prompt,
            )
            result = asyncio.run(rt.call(agent, user_prompt))
            criteria = _parse_response_json(getattr(result, "text", ""))
            print("(railtracks)", end=" ")
            return criteria
    except Exception:
        pass
    print("(http fallback)", end=" ")
    return _call_openai_compatible(system_prompt, user_prompt)
