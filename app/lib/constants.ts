// Address of the Flask backend. The deployed site is built with
// NEXT_PUBLIC_BACKEND_URL pointing at the Hugging Face Space, and local
// development falls back to the dev server started by backend/main.py.
export const BACKEND_API_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || 'http://127.0.0.1:5005'
).replace(/\/+$/, '');
export const SUGGESTION_COOLDOWN = 10000;
export const FOCUS_HISTORY_SIZE = 2;
export const LOW_FOCUS_THRESHOLD = 25;
