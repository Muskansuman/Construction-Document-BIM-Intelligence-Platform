"""Thin OpenAI-compatible client.

Works with OpenAI, or with Qwen2.5 served locally through Ollama / vLLM
(both expose /v1/chat/completions). Returns None when the LLM is disabled,
so every caller must have a deterministic fallback.
"""
from __future__ import annotations

import json
import logging

from app.core.config import get_settings

log = logging.getLogger(__name__)


def llm_enabled() -> bool:
    return get_settings().llm_provider.lower() != "none"


def chat(system: str, user: str, json_mode: bool = False) -> str | None:
    if not llm_enabled():
        return None
    from openai import OpenAI

    s = get_settings()
    client = OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    try:
        resp = client.chat.completions.create(
            model=s.llm_model,
            temperature=s.llm_temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,
        )
        return resp.choices[0].message.content
    except Exception as exc:  # never let the LLM break the pipeline
        log.warning("LLM call failed: %s", exc)
        return None


def chat_json(system: str, user: str) -> dict | None:
    raw = chat(system, user, json_mode=True)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned invalid JSON")
        return None
