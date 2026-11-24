"""Tests for the CORS, upload size and upload type settings."""

import pytest

import web_config
from web_config import UploadRejected, allowed_origins, classify_upload, max_upload_bytes


def test_origins_default_to_the_local_frontend():
    assert allowed_origins({}) == ["http://localhost:3000"]
    assert allowed_origins({"FRONTEND_ORIGIN": "  "}) == ["http://localhost:3000"]


def test_origins_are_split_on_commas_and_trimmed():
    env = {"FRONTEND_ORIGIN": "https://study-pilot.vercel.app/, http://localhost:3000 ,,"}
    assert allowed_origins(env) == ["https://study-pilot.vercel.app", "http://localhost:3000"]


def test_upload_limit_defaults_to_ten_megabytes():
    assert max_upload_bytes({}) == 10 * 1024 * 1024


def test_upload_limit_reads_fractional_megabytes():
    assert max_upload_bytes({"MAX_UPLOAD_MB": "0.5"}) == 512 * 1024


@pytest.mark.parametrize("raw", ["ten", "0", "-3"])
def test_bad_upload_limits_are_refused(raw):
    with pytest.raises(ValueError, match="MAX_UPLOAD_MB"):
        max_upload_bytes({"MAX_UPLOAD_MB": raw})


def test_pdf_with_a_pdf_header_is_accepted():
    assert classify_upload("Notes.PDF", b"%PDF-1.7\n...") == "pdf"


@pytest.mark.parametrize("name", ["notes.txt", "notes.md", "README.markdown"])
def test_utf8_text_and_markdown_are_accepted(name):
    assert classify_upload(name, "# Café notes\n".encode("utf-8")) == "text"


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("slides.pptx", b"PK\x03\x04", "Only"),
        ("noextension", b"hello", "Only"),
        ("fake.pdf", b"MZ\x90\x00 not a pdf", "not a PDF"),
        ("binary.txt", b"abc\x00def", "binary"),
        ("latin.md", "café".encode("latin-1"), "UTF-8"),
    ],
)
def test_mismatched_or_unknown_files_are_rejected(name, data, message):
    with pytest.raises(UploadRejected, match=message):
        classify_upload(name, data)


def test_module_documents_its_environment_variables():
    assert "FRONTEND_ORIGIN" in web_config.__doc__
    assert "MAX_UPLOAD_MB" in web_config.__doc__
