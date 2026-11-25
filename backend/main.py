import logging

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from routes.agent import agent_bp
from routes.documents import documents_bp
from routes.evaluation import evaluation_bp
from routes.generation import generation_bp
from routes.media import media_bp
from routes.sessions import sessions_bp
from web_config import allowed_origins, max_upload_bytes

# Setup
logging.basicConfig(level=logging.DEBUG)
load_dotenv()

# The media blueprint serves /static (the text to speech audio), so Flask's own
# static route is turned off to keep the two from competing for the same path.
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = max_upload_bytes()
CORS(app, resources={r"/*": {"origins": allowed_origins()}})


@app.route("/health", methods=["GET"])
def health():
    """Report that the server is up and which model providers have a key, without calling them."""
    import llm

    try:
        providers = list(llm.load_config().active_providers)
    except llm.LLMError:
        providers = []
    return jsonify({"status": "ok", "llm_providers": providers})


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    limit_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
    return jsonify({"error": f"The upload is larger than the {limit_mb:g} MB limit."}), 413


@app.errorhandler(BadRequest)
def bad_request(error):
    """Answer a malformed request with JSON the frontend can show, not an HTML page."""
    return jsonify({"error": error.description or "Bad request"}), 400


for blueprint in (generation_bp, documents_bp, sessions_bp, agent_bp, media_bp, evaluation_bp):
    app.register_blueprint(blueprint)


if __name__ == "__main__":
    app.run(debug=True, port=5005)
