"use strict";
// Backend API base URL.
// - Leave empty ("") when this frontend is served by the FastAPI app itself (local dev,
//   `python run.py`) — API calls are then same-origin, exactly as before.
// - Set to your deployed backend's URL when this frontend is hosted separately (e.g. this
//   folder deployed as a static site on Vercel, backend deployed on Render):
//     window.API_BASE = "https://your-backend.onrender.com";
window.API_BASE = "";
