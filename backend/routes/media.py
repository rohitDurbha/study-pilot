"""Text to speech and the static audio files it writes."""

import asyncio
import logging
import os
import tempfile

from flask import Blueprint, jsonify, send_from_directory

from routes.common import json_body

media_bp = Blueprint("media", __name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
TTS_MAX_CHARS = 8000
DEFAULT_VOICE = "en-US-JennyNeural"


def synthesize_speech(text: str, voice: str, directory: str) -> str:
    """Write the spoken text to an mp3 file in directory and return its path."""
    import edge_tts

    async def generate():
        communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="-2Hz", volume="-10%")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir=directory)
        tmp.close()
        await communicate.save(tmp.name)
        return tmp.name

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(generate())
    finally:
        loop.close()


@media_bp.route("/api/tts", methods=["POST"])
def text_to_speech():
    """Generate natural-sounding speech from text using Edge TTS."""
    data = json_body()
    text = data.get("text", "")
    voice = data.get("voice", DEFAULT_VOICE)
    if not text or not isinstance(text, str):
        return jsonify({"error": "No text provided"}), 400
    text = text[:TTS_MAX_CHARS]

    try:
        os.makedirs(STATIC_DIR, exist_ok=True)
        filepath = synthesize_speech(text, voice, STATIC_DIR)
        return jsonify({"url": f"/static/{os.path.basename(filepath)}"})
    except Exception as e:
        logging.exception("Error generating TTS")
        return jsonify({"error": str(e)}), 500


@media_bp.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)
