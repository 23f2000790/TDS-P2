import os
import requests
import json
import base64
import io
import re
import pandas as pd
import matplotlib.pyplot as plt
from contextlib import redirect_stdout
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pdfplumber
import subprocess
import sys

from config import logger

# Define a limit for log output
TRUNCATE_LIMIT = 2000
# Increased network timeout for more patience
NETWORK_TIMEOUT = 30  # 30 seconds

# --- Tool 1: Web Scraper ---
def scrape_website(url: str) -> str:
    """
    Fetches a URL, executes JavaScript, and returns the full HTML content.
    """
    logger.info(f"Tool: scrape_website - URL: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=NETWORK_TIMEOUT * 1000) 
            page.wait_for_timeout(1000) 
            content = page.content()
            browser.close()
            
            soup = BeautifulSoup(content, 'lxml')
            return f"Full HTML content from {url}:\n{str(soup)}"
            
    except Exception as e:
        logger.error(f"Tool: scrape_website - Error: {e}")
        return f"Error scraping {url}: {e}"

# --- Tool 2: File Downloader & Reader (Preview) ---
def download_and_read_file(url: str) -> str:
    """
    Downloads a file.
    - If text/CSV/JS: Saves to disk, returns path and a preview.
    - If PDF: Extracts text, returns a preview.
    - If media: Ignores.
    """
    logger.info(f"Tool: download_and_read_file - URL: {url}")
    try:
        response = requests.get(url, timeout=NETWORK_TIMEOUT)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        
        filename = 'temp_downloaded_file' # Generic default
        
        if 'javascript' in content_type:
            filename = 'temp_utils.js'
        elif 'csv' in content_type:
            filename = 'temp_data.csv'
        elif 'json' in content_type:
            filename = 'temp_data.json'
        elif 'text/plain' in content_type:
            filename = 'temp_log.txt'
        
        text_content = None

        if 'text/plain' in content_type or 'javascript' in content_type or 'json' in content_type or 'csv' in content_type:
            text_content = response.text
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            lines = text_content.splitlines()
            preview = "\n".join(lines[:5])
            
            return f"File saved as '{filename}'. Here is a preview (first 5 lines):\n{preview}"
            
        elif 'application/pdf' in content_type:
            with io.BytesIO(response.content) as f:
                with pdfplumber.open(f) as pdf:
                    text_content = "".join(page.extract_text() for page in pdf.pages if page.extract_text())
            
            if not text_content:
                return "PDF file was downloaded, but no text could be extracted."
            
            preview = text_content[:1500]
            return f"PDF text extracted. Content preview:\n{preview}..."

        elif 'audio/' in content_type or 'video/' in content_type:
            return "File is non-text media (audio/video). It is likely a distraction and should be ignored."
        
        else:
            filename = url.split('/')[-1]
            if not filename:
                filename = "temp_binary_file"
            with open(filename, 'wb') as f:
                f.write(response.content)
            return f"Binary file saved as '{filename}'. Use 'run_python_code' to analyze it if necessary."

    except Exception as e:
        logger.error(f"Tool: download_and_read_file - Error: {e}")
        return f"Error downloading file {url}: {e}"

# --- Tool 3: Read Full File ---
def read_file(filename: str) -> str:
    """
    Reads the *full* text content of a file that is already on disk.
    """
    logger.info(f"Tool: read_file - Filename: {filename}")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if len(content) > TRUNCATE_LIMIT * 5: # Give a large buffer (10k chars)
            logger.warning(f"File {filename} is very large, truncating for observation.")
            return f"Full file content (truncated):\n{content[:TRUNCATE_LIMIT * 5]}\n...[TRUNCATED]"
        else:
            return f"Full file content of {filename}:\n{content}"
            
    except Exception as e:
        logger.error(f"Tool: read_file - Error: {e}")
        return f"Error reading file {filename}: {e}"

# --- Tool 4: Agent Memory ---
def write_to_file(filename: str, content: str, mode: str = 'w') -> str:
    """
    Writes or appends text content to a local file, acting as the agent's memory.
    Default mode is 'w' (overwrite). Use 'a' to append.
    """
    logger.info(f"Tool: write_to_file - Filename: {filename}, Mode: {mode}")
    try:
        with open(filename, mode, encoding='utf-8') as f:
            f.write(content)
        return f"Content successfully written to {filename}."
    except Exception as e:
        logger.error(f"Tool: write_to_file - Error: {e}")
        return f"Error writing to file {filename}: {e}"

# --- Tool 5: Hybrid Logic Executor (Upgraded) ---
def run_python_code(code_string: str = None, filename: str = None) -> str:
    """
    Executes a string of Python code OR a Python file in a restricted environment.
    - If 'code_string' is provided, it's executed directly (less safe for complex strings).
    - If 'filename' is provided, that file is executed as a separate process (safer).
    """
    if filename:
        # --- NEW: File Execution Logic ---
        logger.info(f"Tool: run_python_code - Executing file: {filename}")
        try:
            # We use subprocess to run the file, ensuring it uses the same python
            result = subprocess.run(
                [sys.executable, filename],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
                encoding='utf-8' # Ensure consistent encoding
            )
            output = result.stdout + result.stderr

            if not output:
                return f"File '{filename}' executed successfully with no print output."
            
            if len(output) > TRUNCATE_LIMIT:
                logger.info(f"File output is large, truncating to {TRUNCATE_LIMIT} chars.")
                return f"File executed. Output (truncated):\n{output[:TRUNCATE_LIMIT]}\n...[TRUNCATED]"
            else:
                return f"File executed. Output:\n{output}"

        except subprocess.CalledProcessError as e:
            error_msg = f"Error executing file {filename}: {e.stderr}"
            logger.error(f"Tool: run_python_code - {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"Error executing file {filename}: {e}"
            logger.error(f"Tool: run_python_code - {error_msg}")
            return error_msg

    elif code_string:
        # --- EXISTING: Code String Logic ---
        logger.info(f"Tool: run_python_code - Original code: {code_string}")
        
        cleaned_code = code_string.replace('\\n', '\n')
        buffer = io.StringIO()
        
        allowed_globals = {
            "pd": pd,
            "plt": plt,
            "io": io,
            "base64": base64,
            "json": json,
            "re": re, 
            "open": open, 
            "print": lambda *args: buffer.write(" ".join(map(str, args)) + "\n"),
        }
        
        try:
            with redirect_stdout(buffer):
                exec(cleaned_code, allowed_globals)
            
            output = buffer.getvalue()
            
            if 'plt.savefig' in cleaned_code:
                output += "\n[Plot saved to file by code.]"

            if not output:
                 return "Code executed successfully with no print output."
            
            if len(output) > TRUNCATE_LIMIT:
                logger.info(f"Code output is large, truncating to {TRUNCATE_LIMIT} chars for observation.")
                return f"Code executed. Output (truncated):\n{output[:TRUNCATE_LIMIT]}\n...[TRUNCATED]"
            else:
                return f"Code executed. Output:\n{output}"
            
        except Exception as e:
            logger.error(f"Tool: run_python_code - Error: {e}")
            return f"Error executing code: {str(e)}"
            
    else:
        return "Error: 'run_python_code' called with no 'code_string' or 'filename'."


# --- Tool 6: Final Answer Submitter (NEW robust signature) ---
def submit_answer(submit_url: str, answer_payload: dict, email: str, secret: str, task_url: str) -> str:
    """
    Submits the final answer. The 'answer_payload' is a dict from the LLM.
    """
    logger.info(f"Tool: submit_answer - URL: {submit_url}")
    try:
        final_payload = {
            "email": email,
            "secret": secret,
            "url": task_url,
            **answer_payload 
        }
        
        response = requests.post(submit_url, json=final_payload, timeout=NETWORK_TIMEOUT)
        response.raise_for_status()
        
        logger.info(f"Submission successful. Response: {response.text}")
        return f"Submission response: {response.text}"
        
    except Exception as e:
        logger.error(f"Tool: submit_answer - Request Error: {e}")
        return f"Error submitting answer to {submit_url}: {e}"