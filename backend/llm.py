"""One place for every language model call the backend makes.

Requests go to the providers in LLM_PROVIDERS order, which defaults to Groq
first and Gemini second. Both are reached through their plain HTTP APIs, so
the only dependency is requests (plus pypdf for reading PDFs on the Groq
path). A provider without an API key is skipped, and when a call fails or
comes back empty the next provider is tried.

Every setting lives in LLMConfig and is read from environment variables.

    GROQ_API_KEY            key from console.groq.com (free tier)
    GEMINI_API_KEY          key from aistudio.google.com (free tier)
    LLM_PROVIDERS           comma separated order, default "groq,gemini"
    GROQ_MODEL              default "openai/gpt-oss-120b"
    GEMINI_MODEL            default "gemini-flash-latest"
    GROQ_REASONING_EFFORT   low, medium or high for reasoning models, default "low"
    LLM_TIMEOUT_SECONDS     per request timeout, default 60
    LLM_PDF_TEXT_LIMIT      most characters of PDF text sent to Groq, default 60000

Groq cannot read PDF files, so for a PDF prompt the text is extracted first.
When the text is empty (a scanned PDF) or longer than LLM_PDF_TEXT_LIMIT,
Groq is skipped and Gemini, which reads PDFs natively, takes the request.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import requests

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

DEFAULT_PROVIDERS = ("groq", "gemini")
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_PDF_TEXT_LIMIT = 60_000

KNOWN_PROVIDERS = {"groq", "gemini"}


class LLMError(RuntimeError):
    """Raised when no configured provider could answer a request."""


class ProviderSkipped(Exception):
    """A provider chose not to handle a request, for example a scanned PDF on Groq."""


@dataclass(frozen=True)
class LLMConfig:
    providers: tuple[str, ...] = DEFAULT_PROVIDERS
    groq_api_key: str = ""
    gemini_api_key: str = ""
    groq_model: str = DEFAULT_GROQ_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    groq_reasoning_effort: str = DEFAULT_REASONING_EFFORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    pdf_text_limit: int = DEFAULT_PDF_TEXT_LIMIT

    def api_key(self, provider: str) -> str:
        return self.groq_api_key if provider == "groq" else self.gemini_api_key

    def model(self, provider: str) -> str:
        return self.groq_model if provider == "groq" else self.gemini_model

    @property
    def active_providers(self) -> tuple[str, ...]:
        """Providers in order that have an API key set."""
        return tuple(p for p in self.providers if self.api_key(p))


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict, repr=False)


def _number(env: Mapping[str, str], name: str, default, cast):
    value = (env.get(name) or "").strip()
    if not value:
        return default
    try:
        return cast(value)
    except ValueError:
        logger.warning("Ignoring %s=%r, it is not a number", name, value)
        return default


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Build an LLMConfig from environment variables."""
    env = os.environ if env is None else env

    providers = tuple(
        p.strip().lower() for p in (env.get("LLM_PROVIDERS") or "").split(",") if p.strip()
    ) or DEFAULT_PROVIDERS
    unknown = [p for p in providers if p not in KNOWN_PROVIDERS]
    if unknown:
        raise LLMError(f"Unknown provider in LLM_PROVIDERS: {', '.join(unknown)}")

    return LLMConfig(
        providers=providers,
        groq_api_key=(env.get("GROQ_API_KEY") or "").strip(),
        gemini_api_key=(env.get("GEMINI_API_KEY") or "").strip(),
        groq_model=(env.get("GROQ_MODEL") or "").strip() or DEFAULT_GROQ_MODEL,
        gemini_model=(env.get("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL,
        groq_reasoning_effort=(env.get("GROQ_REASONING_EFFORT") or "").strip().lower()
        or DEFAULT_REASONING_EFFORT,
        timeout_seconds=_number(env, "LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, float),
        pdf_text_limit=_number(env, "LLM_PDF_TEXT_LIMIT", DEFAULT_PDF_TEXT_LIMIT, int),
    )


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract the text layer of a PDF, page by page."""
    from pypdf import PdfReader  # imported here so text only callers do not need it

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def _build_messages(prompt: str | None, messages: Sequence[Mapping[str, str]] | None):
    history = [{"role": m["role"], "content": m["content"]} for m in (messages or [])]
    if prompt is not None:
        history.append({"role": "user", "content": prompt})
    if not history:
        raise ValueError("generate() needs a prompt or at least one message")
    for m in history:
        if m["role"] not in ("user", "assistant"):
            raise ValueError(f"Unsupported message role {m['role']!r}")
    if history[-1]["role"] != "user":
        raise ValueError("The last message must come from the user")
    return history


def _call_groq(config, session, system, history, max_tokens, pdf_bytes, json_mode):
    if pdf_bytes is not None:
        try:
            text = pdf_to_text(pdf_bytes)
        except Exception as exc:  # noqa: BLE001 - pypdf raises many error types
            raise ProviderSkipped(f"the PDF text could not be read ({exc})") from exc
        if not text:
            raise ProviderSkipped("the PDF has no text layer")
        if len(text) > config.pdf_text_limit:
            raise ProviderSkipped(
                f"the PDF text has {len(text)} characters, over the {config.pdf_text_limit} limit"
            )
        history = list(history)
        last = history[-1]
        history[-1] = {
            "role": "user",
            "content": f"Document text:\n\"\"\"\n{text}\n\"\"\"\n\n{last['content']}",
        }

    chat = ([{"role": "system", "content": system}] if system else []) + history
    body = {"model": config.groq_model, "messages": chat, "max_completion_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if config.groq_model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = config.groq_reasoning_effort

    resp = session.post(
        GROQ_URL,
        json=body,
        headers={"Authorization": f"Bearer {config.groq_api_key}"},
        timeout=config.timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "").strip()
    if not text:
        raise LLMError(f"empty reply (finish_reason {choice.get('finish_reason')})")
    usage = data.get("usage") or {}
    return LLMResponse(
        text=text,
        provider="groq",
        model=config.groq_model,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        raw=data,
    )


def _call_gemini(config, session, system, history, max_tokens, pdf_bytes, json_mode):
    contents = []
    for i, m in enumerate(history):
        parts = []
        if pdf_bytes is not None and i == len(history) - 1:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                    }
                }
            )
        parts.append({"text": m["content"]})
        contents.append({"role": "model" if m["role"] == "assistant" else "user", "parts": parts})

    generation = {"maxOutputTokens": max_tokens}
    if json_mode:
        generation["responseMimeType"] = "application/json"
    body = {"contents": contents, "generationConfig": generation}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    resp = session.post(
        GEMINI_URL.format(model=config.gemini_model),
        json=body,
        headers={"x-goog-api-key": config.gemini_api_key},
        timeout=config.timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    candidate = (data.get("candidates") or [{}])[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise LLMError(f"empty reply (finishReason {candidate.get('finishReason')})")
    usage = data.get("usageMetadata") or {}
    return LLMResponse(
        text=text,
        provider="gemini",
        model=config.gemini_model,
        input_tokens=int(usage.get("promptTokenCount") or 0),
        output_tokens=int(usage.get("candidatesTokenCount") or 0),
        raw=data,
    )


_CALLERS = {"groq": _call_groq, "gemini": _call_gemini}


def _describe(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        detail = exc.response.text[:300].strip()
        return f"HTTP {exc.response.status_code} {detail}".strip()
    return str(exc) or exc.__class__.__name__


def generate(
    prompt: str | None = None,
    *,
    system: str | None = None,
    messages: Sequence[Mapping[str, str]] | None = None,
    max_tokens: int = 1024,
    pdf_bytes: bytes | None = None,
    json_mode: bool = False,
    config: LLMConfig | None = None,
    session: requests.Session | None = None,
) -> LLMResponse:
    """Send a prompt to the first provider that answers.

    prompt is appended to messages as the final user turn. messages holds
    earlier turns as dicts with role "user" or "assistant". pdf_bytes attaches
    a PDF to the final user turn. json_mode asks the provider for a JSON reply.
    """
    config = config or load_config()
    history = _build_messages(prompt, messages)
    providers = config.active_providers
    if not providers:
        raise LLMError(
            "No language model provider is configured. Set GROQ_API_KEY or GEMINI_API_KEY."
        )

    http = session or requests.Session()
    failures = []
    try:
        for provider in providers:
            try:
                return _CALLERS[provider](
                    config, http, system, history, max_tokens, pdf_bytes, json_mode
                )
            except ProviderSkipped as exc:
                logger.info("Skipping %s because %s", provider, exc)
                failures.append(f"{provider} skipped, {exc}")
            except (requests.RequestException, LLMError, ValueError) as exc:
                reason = _describe(exc)
                logger.warning("%s call failed, %s", provider, reason)
                failures.append(f"{provider} failed, {reason}")
    finally:
        if session is None:
            http.close()

    raise LLMError("Every provider failed. " + "; ".join(failures))


def generate_text(prompt: str, **kwargs) -> str:
    """Shortcut that returns only the reply text."""
    return generate(prompt, **kwargs).text
