"""Requirement 11.1: single-command startup for the whole app (API + UI, one process)."""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=port, reload=False)
