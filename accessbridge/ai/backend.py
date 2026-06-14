import os
import subprocess
import shutil
from typing import Tuple

from accessbridge.core.utils import logger


def _ollama_available() -> bool:
    return shutil.which("ollama") is not None


def _call_ollama(prompt_text: str, model: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "generate", model, prompt_text],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"[Ollama Error]: {result.stderr.strip()}"
    except Exception as ex:
        return f"[Ollama Invocation Failure]: {str(ex)}"


def _openai_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _get_gemini_response(prompt_text: str) -> Tuple[str, str, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "", "🟡 Missing Gemini API key", "Missing key"

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Use REST API directly (no google-generativeai SDK required).
    # https://ai.google.dev/gemini-api/docs
    try:
        import requests

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 256,
            },
        }

        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code != 200:
            return "", "🔴 Gemini API Error", f"HTTP {resp.status_code}: {resp.text[:500]}"

        data = resp.json()
        # Expected structure: candidates[0].content.parts[0].text
        text = ""
        try:
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        except Exception:
            text = ""

        return str(text).strip(), "🟢 AI Ready", ""
    except Exception as ex:
        return "", "🔴 Gemini API Error", str(ex)


def _get_openai_response(prompt_text: str) -> Tuple[str, str, str]:
    try:
        from openai import OpenAI
    except Exception as ex:
        return "", "🔴 OpenAI package unavailable", str(ex)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "", "🟡 Missing OpenAI API key", "Missing key"

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=120,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip(), "🟢 AI Ready", ""
    except Exception as ex:
        return "", "🔴 API Error", str(ex)


def get_ai_response(prompt_text: str, deployment: str = None) -> Tuple[str, str, str]:
    if not prompt_text.strip():
        return "", "🟡 No prompt provided", ""

    # Foundry provider (optional)
    try:
        from accessbridge.ai.foundry import get_foundry_response
    except Exception:
        get_foundry_response = None  # type: ignore

    # NOTE: Provider selection order.
    if _openai_available():
        return _get_openai_response(prompt_text)

    if _gemini_available():
        return _get_gemini_response(prompt_text)

    if get_foundry_response is not None:
        try:
            return get_foundry_response(prompt_text)
        except Exception as ex:
            logger.debug("Foundry provider failure: %s", ex)

    if _ollama_available():
        answer = _call_ollama(prompt_text, os.getenv("OLLAMA_MODEL", "llama2"))
        return answer, "🟢 AI Ready", ""

    return (
        "[Offline AI Fallback]: Unable to generate an answer without a connected AI backend.",
        "🟡 Offline AI Mode",
        "No backend available",
    )

