import sys
import asyncio
import platform

# --- WINDOWS PLAYWRIGHT FIX ---
# This prevents "NotImplementedError" when using Playwright with FastAPI on Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
import uvicorn
import time

import config  # This imports config.py and runs the logger setup
from config import logger, MY_SECRET
from agent import solve_quiz_task

app = FastAPI()

# --- Pydantic Model for Request Body ---
class QuizTask(BaseModel):
    email: str
    secret: str
    url: str

# --- API Endpoint ---
@app.post("/solve")
async def start_quiz_solver(task: QuizTask, background_tasks: BackgroundTasks, request: Request):
    """
    This is the main API endpoint.
    It verifies the secret, returns 200 OK immediately,
    and starts the agent in the background.
    """
    
    
    # Log the incoming request
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Received quiz task from {client_ip} for URL: {task.url}")

    # 1. Verify Invalid JSON (FastAPI does this automatically)
    
    # 2. Verify Secret
    if task.secret != MY_SECRET:
        logger.warning(f"Invalid secret from {client_ip}. Access denied.")
        raise HTTPException(status_code=403, detail="Invalid secret")

    deadline = time.time() + 170
    # 3. Add to BackgroundTasks and Respond 200 OK
    logger.info("Secret verified. Accepting task and starting agent in background.")
    background_tasks.add_task(
        solve_quiz_task,
        email=task.email,
        secret=task.secret,
        url=task.url,
        deadline=deadline
    )
    
    # Return 200 immediately
    return {"status": "Task accepted. Processing in background."}

# --- Root Endpoint (for testing) ---
@app.get("/")
def read_root():
    return {"message": "LLM Analysis Quiz Agent is running."}

# --- Main entry point to run the server ---
if __name__ == "__main__":
    logger.info("Starting FastAPI server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
