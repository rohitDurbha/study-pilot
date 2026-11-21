# StudyPilot Roadmap

StudyPilot is a port of [StudyBuddy.ai](https://github.com/PuneethRegonda/studybuddy.ai) that aims to run entirely on free tiers. Work moves one step at a time, and each step is ticked when it lands on main.

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
- [ ] 4. Split the 1,100-line main.py into Flask blueprints, add robust JSON parsing, upload type checks and size limits, and lock CORS to the frontend origin.
  - [ ] a. Start a routes package. Move the shared model helpers and the content cache into routes/common.py, and move the upload and the flashcard, quiz, mind map and mini game routes into a generation blueprint that main.py registers, with route tests for the moved endpoints.
  - [ ] b. Move the document, section and study session routes into their own blueprints.
  - [ ] c. Move the agent, text to speech, static audio, eval and RAG routes into blueprints, so main.py only builds the app and registers them.
  - [ ] d. Make JSON handling robust. Return a clear 400 when a request body is missing or not JSON, and let extract_json recover the JSON from model replies that wrap it in prose or leave a trailing comma.
  - [ ] e. Check uploads by type and size. Accept only PDF, plain text and Markdown files whose content matches the extension, cap the request size with MAX_CONTENT_LENGTH from an environment variable, and answer oversized uploads with a JSON 413.
  - [ ] f. Lock CORS to the frontend origin read from FRONTEND_ORIGIN (comma separated for several), defaulting to http://localhost:3000, and document it in the env example and README.
- [ ] 5. Move focus detection fully into the browser with the MediaPipe package already in package.json, and delete focus_server.py, which returns random values.
- [ ] 6. Upgrade Next.js 15.3.1 to a patched release because of later security advisories.
- [ ] 7. Host for free. Frontend on Vercel, backend on Hugging Face Spaces or Render, and persistent data in Turso or Supabase free tiers because free containers lose local SQLite files.
- [ ] 8. Tests, CI and a README with setup steps.

## Needs Rohit

- Create free Groq and Gemini API keys and add them as GROQ_API_KEY and GEMINI_API_KEY in backend/.env. Every backend module now goes through backend/llm.py, which tries Groq first and falls back to Gemini, so no feature that generates content will work until at least one key is set. Afterwards run `python3 smoke_llm.py` inside backend/ to confirm that both keys and the default model names work.
- Vercel and Hugging Face accounts for item 7.
- Optional. Host the original demo clip somewhere public and set NEXT_PUBLIC_DEMO_VIDEO_URL if you want the video component to show it.
