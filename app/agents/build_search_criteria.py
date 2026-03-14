"""
Extract structured search criteria from a conversation/transcript using Railtracks.
"""
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

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
    from dotenv import load_dotenv
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL
    load_dotenv(ROOT / ".env")
    import railtracks as rt
    api_key = os.getenv("OPENAI_API_KEY", "")
    if hasattr(rt.llm, "OpenAICompatibleLLM"):
        return rt.llm.OpenAICompatibleLLM(
            model=GPT_OSS_MODEL,
            base_url=GPT_OSS_BASE_URL,
            api_key=api_key,
        )
    model_name = GPT_OSS_MODEL if GPT_OSS_MODEL.startswith("openai/") else f"openai/{GPT_OSS_MODEL}"
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = GPT_OSS_BASE_URL
    return rt.llm.OpenAILLM(model_name)


def _default_criteria() -> dict:
    return {
        "location": "",
        "intent": "rent",
        "price_max": "",
        "beds_min": "",
        "baths_min": "",
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


def _call_openai_compatible(system_prompt: str, user_prompt: str) -> dict:
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL
    api_key = os.getenv("OPENAI_API_KEY", "")
    payload = json.dumps(
        {
            "model": GPT_OSS_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=f"{GPT_OSS_BASE_URL.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_response_json(text)


def extract_search_criteria(transcript: str) -> dict:
    """
    Run the build-search-criteria agent on a transcript (Railtracks + GPT-OSS).
    Returns a dict with location, intent, price_max, beds_min, baths_min.
    """
    from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL
    if not GPT_OSS_BASE_URL or not GPT_OSS_MODEL:
        raise ValueError(
            "Set GPT_OSS_BASE_URL and GPT_OSS_MODEL in .env (see .env.example)."
        )
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
            return _parse_response_json(getattr(result, "text", ""))
    except Exception:
        pass
    return _call_openai_compatible(system_prompt, user_prompt)
