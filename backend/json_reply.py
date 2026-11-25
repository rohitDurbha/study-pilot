"""Read JSON out of model replies and request bodies.

Models are asked for bare JSON but often wrap it in Markdown fences, put a
sentence before or after it, or leave a trailing comma before a closing
bracket. extract_json copes with all of those. The request helpers turn a
missing or malformed body into a clear 400 instead of a 500.
"""

import json
import re

from flask import request
from werkzeug.exceptions import BadRequest

_FENCE_OPEN = re.compile(r"^```(?:json|JSON)?\s*\n?", flags=re.MULTILINE)
_FENCE_CLOSE = re.compile(r"\n?```\s*$", flags=re.MULTILINE)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


class NoJSONFound(ValueError):
    """Raised when a model reply holds no JSON object or array."""


def _strip_fences(text: str) -> str:
    cleaned = _FENCE_OPEN.sub("", text)
    cleaned = _FENCE_CLOSE.sub("", cleaned)
    return cleaned.strip()


def _drop_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA.sub(r"\1", text)


def extract_json(text: str):
    """Return the JSON object or array in a model reply.

    Tries the whole reply first, then the largest object or array that can be
    decoded from anywhere inside it, each time with and without trailing commas.
    """
    if text is None:
        raise NoJSONFound("The model reply was empty")

    cleaned = _strip_fences(text)
    variants = [cleaned]
    without_commas = _drop_trailing_commas(cleaned)
    if without_commas != cleaned:
        variants.append(without_commas)

    for candidate in variants:
        try:
            return json.loads(candidate)
        except ValueError:
            pass

    decoder = json.JSONDecoder()
    best = None
    best_length = 0
    for candidate in variants:
        for match in re.finditer(r"[{\[]", candidate):
            try:
                value, end = decoder.raw_decode(candidate, match.start())
            except ValueError:
                continue
            length = end - match.start()
            if length > best_length:
                best, best_length = value, length
    if best_length:
        return best

    raise NoJSONFound("No JSON object or array was found in the model reply")


class InvalidJSONBody(BadRequest):
    """A 400 for a request whose body is missing, not JSON or not an object."""


def json_body() -> dict:
    """Return the request body as a dict, or raise InvalidJSONBody."""
    data = request.get_json(silent=True)
    if data is None:
        raise InvalidJSONBody("The request body must be JSON with a Content-Type of application/json.")
    if not isinstance(data, dict):
        raise InvalidJSONBody("The request body must be a JSON object.")
    return data
