"""Send one short prompt to each configured language model provider.

Run it from the backend folder after putting a key in .env. It checks every
provider on its own, so a broken Gemini key is reported even when Groq answers
first in normal use.

    python3 smoke_llm.py
    python3 smoke_llm.py --provider gemini
    python3 smoke_llm.py --json-mode

Each provider prints one line with its model, how long the reply took, the
token counts and the start of the reply. A provider without an API key is
listed as skipped. The exit code is 0 when every provider with a key answered,
1 when at least one of them failed and 2 when no key is set at all.

Real requests are sent, so each run uses a few hundred tokens of your free
quota per provider.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time

from dotenv import load_dotenv

import llm

DEFAULT_PROMPT = "Reply with the single word pong."
JSON_PROMPT = 'Reply with a JSON object of the form {"reply": "pong"} and nothing else.'

# Reasoning models on Groq spend part of the budget thinking, so leave room.
MAX_TOKENS = 256


@dataclasses.dataclass
class Result:
    provider: str
    model: str
    status: str  # "ok", "failed" or "skipped"
    detail: str = ""
    seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    def line(self) -> str:
        if self.status == "ok":
            timing = f"{self.seconds:.1f}s, {self.input_tokens} in / {self.output_tokens} out"
            return f"ok       {self.provider:<7} {self.model}  ({timing})  {self.detail}"
        return f"{self.status:<8} {self.provider:<7} {self.model}  {self.detail}"


def _preview(text: str, limit: int = 60) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def check_provider(provider, config, *, prompt, json_mode=False, session=None, clock=time.monotonic):
    """Send prompt to one provider only and describe what happened."""
    model = config.model(provider)
    if not config.api_key(provider):
        key = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
        return Result(provider, model, "skipped", f"{key} is not set")

    single = dataclasses.replace(config, providers=(provider,))
    started = clock()
    try:
        reply = llm.generate(
            prompt,
            max_tokens=MAX_TOKENS,
            json_mode=json_mode,
            config=single,
            session=session,
        )
    except llm.LLMError as exc:
        reason = str(exc).replace("Every provider failed. ", "")
        return Result(provider, model, "failed", reason, seconds=clock() - started)
    elapsed = clock() - started

    if json_mode:
        try:
            json.loads(reply.text)
        except ValueError:
            return Result(
                provider, model, "failed", f"reply is not valid JSON: {_preview(reply.text)}", elapsed
            )

    return Result(
        provider,
        model,
        "ok",
        _preview(reply.text),
        seconds=elapsed,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
    )


def run(providers, config, *, prompt, json_mode=False, session=None, out=sys.stdout):
    """Check each provider in turn, print one line per provider and return the exit code."""
    results = [
        check_provider(p, config, prompt=prompt, json_mode=json_mode, session=session)
        for p in providers
    ]
    for result in results:
        print(result.line(), file=out)

    tried = [r for r in results if r.status != "skipped"]
    if not tried:
        print("No provider has an API key. Set GROQ_API_KEY or GEMINI_API_KEY in .env.", file=out)
        return 2
    if any(r.status == "failed" for r in tried):
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--provider",
        choices=sorted(llm.KNOWN_PROVIDERS),
        action="append",
        help="check only this provider, can be repeated (default is every provider in LLM_PROVIDERS)",
    )
    parser.add_argument("--prompt", help="send this prompt instead of the default ping")
    parser.add_argument(
        "--json-mode", action="store_true", help="ask for a JSON reply and check that it parses"
    )
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        config = llm.load_config()
    except llm.LLMError as exc:
        print(exc, file=sys.stderr)
        return 2

    prompt = args.prompt or (JSON_PROMPT if args.json_mode else DEFAULT_PROMPT)
    providers = tuple(args.provider) if args.provider else config.providers
    return run(providers, config, prompt=prompt, json_mode=args.json_mode)


if __name__ == "__main__":
    sys.exit(main())
