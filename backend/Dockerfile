# StudyPilot backend image for a Hugging Face Docker Space.
# Build from the backend folder with: docker build -t studypilot-api backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    EMBEDDING_CACHE_DIR=/app/models

# Hugging Face runs Spaces as user 1000, so the app files belong to that user.
# WORKDIR creates /app as root and COPY --chown only changes the copied files,
# so /app itself is handed over too. The app creates studybuddy.db, static/
# and models/ inside it at runtime and would fail to start otherwise.
RUN useradd --create-home --uid 1000 app
WORKDIR /app
RUN chown app:app /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=app:app . .
USER app

# Download the fastembed model while the image builds, so the first upload
# does not wait for an 80 MB download.
RUN python -c "import embeddings; embeddings.embed_texts(['warm up'])"

EXPOSE 7860

# One worker keeps a single copy of the embedding model and a single SQLite
# writer, and threads handle concurrent requests. The long timeout covers
# document processing, which waits on the language model.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 300 main:app"]
