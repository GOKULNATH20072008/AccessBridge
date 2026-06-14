from typing import Callable, Dict, Tuple


# Provider signature: (prompt_text: str) -> (answer: str, status: str, error: str)
ProviderFn = Callable[[str], Tuple[str, str, str]]


def get_provider_map() -> Dict[str, ProviderFn]:
    # Import locally to avoid hard dependency failures.
    from accessbridge.ai.backend import _get_openai_response  # type: ignore
    from accessbridge.ai.backend import _get_gemini_response  # type: ignore
    from accessbridge.ai.foundry import get_foundry_response

    return {
        "OPENAI": _get_openai_response,
        "GEMINI": _get_gemini_response,
        "MICROSOFT_FOUNDry": get_foundry_response,
    }

