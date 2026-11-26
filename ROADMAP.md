# StudyPilot Roadmap

StudyPilot is a port of [StudyBuddy.ai](https://github.com/PuneethRegonda/studybuddy.ai) that aims to run entirely on free tiers. Each session finishes a whole item when it can, and items stay split into steps so progress is easy to follow. The Live link section comes before everything else, because bugs are easier to find and fix while a link is up.


## Live link

Live link: not deployed yet. The backend goes to a Hugging Face Docker Space and the frontend goes to Vercel, both deployed from GitHub Actions with repository secrets, so nothing is deployed by hand.

- [ ] Put StudyPilot on a free live link.
  - [x] a. Add a workflow that runs `backend/smoke_llm.py` with the `GROQ_API_KEY` and `GEMINI_API_KEY` repository secrets, so a key or model name that stops working shows up as a failed run.
  - [x] b. Upgrade Next.js 15.3.1 to a patched release before the site is public. This was item 6. Now on 15.5.29, the maintained 15.x line, which npm audit no longer flags.
  - [x] c. Lock CORS to `FRONTEND_ORIGIN` and add the upload type and size checks, which were steps e and f of item 4, because a public backend needs both.
  - [ ] d. Add a backend Dockerfile for a Hugging Face Docker Space that downloads the fastembed model at build time and serves the app with gunicorn on port 7860. Add a workflow that pushes it with `HF_TOKEN` and copies the provider keys into the Space secrets. The Dockerfile, `deploy_space.py` and the Deploy backend workflow are in place and tested, and the runs so far stopped only because the `HF_TOKEN` secret is missing. A CI job now builds the same image, starts it as user 1000 the way Spaces do and runs the live check against it, which caught that the app could not create its SQLite file in a root-owned /app. Tick this once a deploy run goes green.
  - [ ] e. Deploy the frontend to Vercel from a workflow with `VERCEL_TOKEN`, pointed at the Space. The Deploy frontend workflow builds with `NEXT_PUBLIC_BACKEND_URL` set to the Space, checks the pages, writes the site into `FRONTEND_ORIGIN` on the Space and repeats the browser's CORS preflight. It waits on the `VERCEL_TOKEN` and `HF_TOKEN` secrets. Tick this once a run goes green.
  - [ ] f. Add a check after each deploy that loads the site and calls the backend, then put both live links at the top of the README and of this section. The first live version keeps SQLite inside the container, so uploads reset when the Space restarts, and durable storage in Turso stays in item 7.

## Bugs found on the live site

Every session opens the live link first, adds anything broken here, and fixes these before the numbered items.

- None logged yet, because the site is not live.

## Items

- [x] 1. Import the code from PuneethRegonda/studybuddy.ai without the Word reports, plans, contribution notes, generator scripts and tsbuildinfo. Keep the MIT LICENSE and credit the original team in the README.
  - [x] a. Import the application source (frontend and backend) together with the original MIT LICENSE, leaving out reports, plans, contribution notes, generator scripts, build output and tsbuildinfo.
  - [x] b. Write a README that credits the original team (Mahesh Cheekuri, Puneeth Regonda, Siri Chandana Uppula and Sunil Vurandur), explains the layout and lists the local setup steps from the upstream SETUP_AND_RUN.md.
  - [x] c. Check that the backend modules import cleanly in a fresh virtualenv, add npm scripts for typecheck, and handle the missing demo video. The upstream public/brainRot.mp4 (39 MB) was left out of the import, so the video tab in app/ui/main-display/content/video-content.tsx should load it from a configurable URL or hide itself when none is set.
- [x] 2. Replace the paid Anthropic calls (six files) with one provider module. Groq free tier is the default and Gemini free tier is the fallback, with model names in one config.
  - [x] a. Add backend/llm.py, one provider module that sends chat and PDF prompts to Groq first and falls back to Gemini, with the model names and timeouts in one config read from environment variables. Talk to both through their plain HTTP APIs so no extra SDK is needed, and cover it with pytest tests that mock the network.
  - [x] b. Move main.py and study_agent.py onto the new module, including the chat history, system prompts and token usage that study_agent.py reports.
  - [x] c. Move document_processor.py, knowledge_graph.py and eval_harness.py onto the module, then drop the anthropic package from requirements.txt and ANTHROPIC_API_KEY from the env example and check_imports.py.
  - [x] d. Add a small live smoke script that sends one prompt to each configured provider, and document the provider settings in the README.
- [x] 3. Swap sentence-transformers and ChromaDB, which pull in PyTorch, for fastembed and a lightweight store so the backend fits in free hosting.
  - [x] a. Put embeddings behind a small module that uses fastembed with the same all-MiniLM-L6-v2 model (ONNX, no PyTorch), with the model name read from an environment variable and pytest tests that use a fake embedder.
  - [x] b. Replace ChromaDB in rag_pipeline.py with a lightweight store that keeps chunk vectors in the existing SQLite database and ranks them by cosine similarity with numpy, keeping the embed_and_store, retrieve_chunks and delete_collection signatures that main.py, study_agent.py and eval_harness.py call.
  - [x] c. Drop chromadb and sentence-transformers from requirements.txt, remove the allow-missing advice from check_imports.py and the README, and add a script that reindexes documents uploaded before the switch.
- [x] 4. Split the 1,100-line main.py into Flask blueprints, add robust JSON parsing, upload type checks and size limits, and lock CORS to the frontend origin.
  - [x] a. Start a routes package. Move the shared model helpers and the content cache into routes/common.py, and move the upload and the flashcard, quiz, mind map and mini game routes into a generation blueprint that main.py registers, with route tests for the moved endpoints.
  - [x] b. Move the document, section and study session routes into their own blueprints.
  - [x] c. Move the agent, text to speech, static audio, eval and RAG routes into blueprints, so main.py only builds the app and registers them.
  - [x] d. Make JSON handling robust. Return a clear 400 when a request body is missing or not JSON, and let extract_json recover the JSON from model replies that wrap it in prose or leave a trailing comma. The parser lives in json_reply.py and the document processor and knowledge graph now use it too.
  - [x] e. Done in step c of the Live link section. Check uploads by type and size. Accept only PDF, plain text and Markdown files whose content matches the extension, cap the request size with MAX_CONTENT_LENGTH from an environment variable, and answer oversized uploads with a JSON 413.
  - [x] f. Done in step c of the Live link section. Lock CORS to the frontend origin read from FRONTEND_ORIGIN (comma separated for several), defaulting to http://localhost:3000, and document it in the env example and README.
- [x] 5. Move focus detection fully into the browser with the MediaPipe package already in package.json, and delete focus_server.py, which returns random values. The browser engine in app/lib/focus-detection already did the work, so focus_server.py is gone, the WASM runtime is pinned to the installed 0.10.35 package instead of @latest, the GPU delegate falls back to the CPU, and CI checks that the versions stay in step.
- [x] 6. Done in step b of the Live link section. Upgrade Next.js 15.3.1 to a patched release because of later security advisories.
- [ ] 7. Host for free. Frontend on Vercel, backend on Hugging Face Spaces or Render, and persistent data in Turso or Supabase free tiers because free containers lose local SQLite files.
- [ ] 8. Tests, CI and a README with setup steps.

## Needs Rohit

- Create free Groq and Gemini API keys and add them as GROQ_API_KEY and GEMINI_API_KEY in backend/.env. Every backend module now goes through backend/llm.py, which tries Groq first and falls back to Gemini, so no feature that generates content will work until at least one key is set. Afterwards run `python3 smoke_llm.py` inside backend/ to confirm that both keys and the default model names work.
- Done. `GROQ_API_KEY` and `GEMINI_API_KEY` are saved as repository secrets.
- Add `HF_TOKEN` (a Hugging Face token with write access) and `VERCEL_TOKEN` as repository secrets in this repository. The same tokens already saved in safe-stride work here too. The Deploy backend runs on 2026-11-24, 2026-11-25 and 2026-11-26 stopped with "these repository secrets are missing: HF_TOKEN", and both deploy workflows are ready to go as soon as the secrets exist. Afterwards rerun Deploy backend first and then Deploy frontend from the Actions tab, or just push.
- Check the Gemini free tier limits for `gemini-3.5-flash-lite` in Google AI Studio under Rate limits, because Google only shows them there. The code assumes conservative limits until you confirm.
- A free Turso account for durable storage in item 7, which can wait until the site is live.
- Optional. Host the original demo clip somewhere public and set NEXT_PUBLIC_DEMO_VIDEO_URL if you want the video component to show it.
