# StudyPilot Roadmap

StudyPilot is a port of [StudyBuddy.ai](https://github.com/PuneethRegonda/studybuddy.ai) that aims to run entirely on free tiers. Work moves one step at a time, and each step is ticked when it lands on main.

- [ ] 1. Import the code from PuneethRegonda/studybuddy.ai without the Word reports, plans, contribution notes, generator scripts and tsbuildinfo. Keep the MIT LICENSE and credit the original team in the README.
  - [x] a. Import the application source (frontend and backend) together with the original MIT LICENSE, leaving out reports, plans, contribution notes, generator scripts, build output and tsbuildinfo.
  - [x] b. Write a README that credits the original team (Mahesh Cheekuri, Puneeth Regonda, Siri Chandana Uppula and Sunil Vurandur), explains the layout and lists the local setup steps from the upstream SETUP_AND_RUN.md.
  - [ ] c. Check that the backend modules import cleanly in a fresh virtualenv, add npm scripts for typecheck, and handle the missing demo video. The upstream public/brainRot.mp4 (39 MB) was left out of the import, so the video tab in app/ui/main-display/content/video-content.tsx should load it from a configurable URL or hide itself when none is set.
- [ ] 2. Replace the paid Anthropic calls (six files) with one provider module. Groq free tier is the default and Gemini free tier is the fallback, with model names in one config.
- [ ] 3. Swap sentence-transformers and ChromaDB, which pull in PyTorch, for fastembed and a lightweight store so the backend fits in free hosting.
- [ ] 4. Split the 1,100-line main.py into Flask blueprints, add robust JSON parsing, upload type checks and size limits, and lock CORS to the frontend origin.
- [ ] 5. Move focus detection fully into the browser with the MediaPipe package already in package.json, and delete focus_server.py, which returns random values.
- [ ] 6. Upgrade Next.js 15.3.1 to a patched release because of later security advisories.
- [ ] 7. Host for free. Frontend on Vercel, backend on Hugging Face Spaces or Render, and persistent data in Turso or Supabase free tiers because free containers lose local SQLite files.
- [ ] 8. Tests, CI and a README with setup steps.

## Needs Rohit

- Create free Groq and Gemini API keys and add them as GROQ_API_KEY and GEMINI_API_KEY before item 2 can be tried end to end.
- Vercel and Hugging Face accounts for item 7.
