"""Tests for reading JSON out of model replies."""

import pytest

from json_reply import NoJSONFound, extract_json


def test_plain_json_is_returned_as_is():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json("[1, 2]") == [1, 2]


def test_markdown_fences_are_stripped():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('```\n[{"front": "x"}]\n```') == [{"front": "x"}]


def test_json_wrapped_in_prose_is_found():
    reply = 'Sure! Here are your flashcards:\n[{"front": "Cell", "back": "Unit of life"}]\nGood luck studying.'
    assert extract_json(reply) == [{"front": "Cell", "back": "Unit of life"}]


def test_the_largest_json_value_wins_over_a_stray_bracket():
    reply = 'Note [1]: the quiz follows.\n{"questions": [{"q": "Why?", "a": "Because"}]}'
    assert extract_json(reply) == {"questions": [{"q": "Why?", "a": "Because"}]}


def test_trailing_commas_are_tolerated():
    assert extract_json('{"a": [1, 2,], "b": 3,}') == {"a": [1, 2], "b": 3}
    assert extract_json('Here you go\n```json\n[{"x": 1},]\n```') == [{"x": 1}]


def test_a_reply_without_json_raises_a_value_error():
    with pytest.raises(NoJSONFound):
        extract_json("Sorry, I cannot help with that.")
    with pytest.raises(ValueError):
        extract_json("")
    with pytest.raises(ValueError):
        extract_json(None)
