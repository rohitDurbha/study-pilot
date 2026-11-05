# StudyPilot

StudyPilot is an attention-aware study assistant that turns an uploaded PDF or text file into short study sections, then adapts how each section is presented when your focus starts to slip. It can show the material as plain reading with narration, flashcards, quizzes, mind maps or a small matching game, and a study agent in the corner answers questions about the document with citations back to the source.

This repository is a port of [StudyBuddy.AI](https://github.com/PuneethRegonda/studybuddy.ai), and the goal of the port is to run the whole app on free tiers. The original project calls the paid Anthropic API and ships PyTorch for embeddings, so the work in [ROADMAP.md](ROADMAP.md) swaps those pieces for free providers and lighter libraries one step at a time.

## Credits

StudyBuddy.AI was designed and built by Mahesh Cheekuri, Puneeth Regonda, Siri Chandana Uppula and Sunil Vurandur as their MS Software Engineering capstone at San Jose State University in May 2026. All of the original application code comes from their repository, and StudyPilot keeps their work under the same MIT license.

## How it works

Focus tracking runs entirely in the browser with MediaPipe Face Mesh, so no camera frames ever leave your device. The browser combines eye aspect ratio, gaze direction, blink rate and head pose into a smoothed focus score, and a small predictor looks about thirty seconds ahead to catch a drop before it happens.

When the score falls, an adaptive state machine suggests switching to a different format, and it uses minimum dwell times and cooldowns so the content does not flicker between modes. Each section moves through the stages of not started, reading, read, tested and mastered, and quiz results feed a per-concept mastery view in the knowledge graph.

The Flask backend splits documents into sections, generates and caches the flashcards, quizzes and mind maps for each one, and stores sessions, focus events and chat history in SQLite. Routine agent decisions such as welcomes, section completion and prerequisite checks come from a deterministic engine, which keeps language model calls for content generation and free-form chat.

## Project layout

The Next.js frontend lives at the repository root and the Flask API lives in `backend/`.

```
app/
  dashboard/              dashboard page and view
  lib/
    focus-detection/      MediaPipe engine, signal processor, predictor, activity tracker
    adaptive-engine/      format state machine, types and React hook
    constants.ts          backend URL used by the browser
  services/               API clients for content, sessions and the agent
  ui/
    agent/                inline agent card and chat with citations
    main-display/         renderers for text, quiz, flashcards, mind map and game
    modal/                upload dialog
    sidebar/              sources, section progress and knowledge graph
    studio-panel/         camera feed, focus display and focus chart
    session/              end of session report
components/ui/            shared shadcn/ui components
backend/
  main.py                 every Flask route
  database.py             SQLAlchemy models stored in SQLite
  document_processor.py   turns PDFs and text into structured sections
  study_agent.py          chat agent with full context and RAG modes
  agent_engine.py         deterministic decisions for the study agent
  rag_pipeline.py         chunking, embeddings, vector store and retrieval
  eval_harness.py         compares RAG answers against full context answers
  knowledge_graph.py      concept extraction for the knowledge graph
  focus_server.py         placeholder focus service slated for removal
```

The upstream repository also holds Word reports, planning notes, contribution logs and the scripts that generated them. Those files are about the capstone write-up rather than the app, so they were left out of this port.

## License

StudyPilot is released under the MIT License that came with the original project, and the full text with the original copyright notice is in [LICENSE](LICENSE).
