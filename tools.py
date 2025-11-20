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

# --- Configuration ---
TRUNCATE_LIMIT = 2000
NETWORK_TIMEOUT = 30

# --- Tool 1: Web Scraper (Playwright) ---
def scrape_website(url: str) -> str:
    """
    Fetches a URL, executes JavaScript via Playwright, and returns the full HTML content.
    Essential for getting dynamic content (like secret codes) that 'requests' misses.
    """
    logger.info(f"Tool: scrape_website - URL: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=NETWORK_TIMEOUT * 1000) 
            
            # Wait a moment for dynamic content (like the 'Loading...' text) to settle
            try:
                page.wait_for_load_state('networkidle', timeout=2000)
            except:
                pass # Continue even if network isn't perfectly idle
            
            content = page.content()
            browser.close()
            
            soup = BeautifulSoup(content, 'lxml')
            return f"Full HTML content from {url}:\n{str(soup)}"
            
    except Exception as e:
        logger.error(f"Tool: scrape_website - Error: {e}")
        return f"Error scraping {url}: {e}"

# --- Tool 2: Smart File Downloader ---
def download_and_read_file(url: str) -> str:
    """
    Downloads a file and saves it with a FIXED filename to prevent agent confusion.
    - JS/Logic -> temp_utils.js
    - CSV/Text/Log -> temp_data.csv
    """
    logger.info(f"Tool: download_and_read_file - URL: {url}")
    try:
        response = requests.get(url, timeout=NETWORK_TIMEOUT)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        
        # --- CRITICAL FIX: Consolidated File Naming ---
        # This prevents the "FileNotFound: temp_log.txt" loop.
        # We force all data files (CSV, TXT, LOG) to 'temp_data.csv'.
        filename = 'temp_downloaded_file' # Fallback
        
        if 'javascript' in content_type or url.lower().endswith('.js'):
            filename = 'temp_utils.js'
        elif 'json' in content_type or url.lower().endswith('.json'):
            filename = 'temp_data.json'
        elif ('csv' in content_type or 'text' in content_type or 
              url.lower().endswith(('.csv', '.txt', '.log'))):
            filename = 'temp_data.csv'
        # -----------------------------------------------
        
        # Handle Text-based files
        if any(x in content_type for x in ['text', 'javascript', 'json', 'csv']):
            text_content = response.text
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            preview = "\n".join(text_content.splitlines()[:10])
            return f"File saved as '{filename}'. Preview:\n{preview}"
            
        # Handle PDF
        elif 'application/pdf' in content_type:
            with io.BytesIO(response.content) as f:
                with pdfplumber.open(f) as pdf:
                    text_content = "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())
            
            if not text_content:
                return "PDF downloaded, but no text extraction possible."
            
            return f"PDF text extracted. Content preview:\n{text_content[:1500]}..."

        # Handle Binary (Images/Audio) - Ignore
        elif 'audio' in content_type or 'video' in content_type:
            return "File is media (audio/video). Ignored."
        
        else:
            return f"File type {content_type} not supported for direct reading."

    except Exception as e:
        logger.error(f"Tool: download_and_read_file - Error: {e}")
        return f"Error downloading {url}: {e}"

# --- Tool 3: File Reader ---
def read_file(filename: str) -> str:
    """Reads full content of a local file."""
    logger.info(f"Tool: read_file - Filename: {filename}")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if len(content) > TRUNCATE_LIMIT * 5:
            logger.warning(f"File {filename} is large. Truncating output.")
            return f"Content (Truncated):\n{content[:TRUNCATE_LIMIT * 5]}...[TRUNCATED]"
        return f"Content of {filename}:\n{content}"
    except Exception as e:
        return f"Error reading {filename}: {e}"

# --- Tool 4: File Writer ---
def write_to_file(filename: str, content: str, mode: str = 'w') -> str:
    """Writes text to a local file. Essential for creating Python scripts."""
    logger.info(f"Tool: write_to_file - Filename: {filename}")
    try:
        with open(filename, mode, encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filename}."
    except Exception as e:
        return f"Error writing to {filename}: {e}"

# --- Tool 5: Code Executor (Dual Mode) ---
def run_python_code(code_string: str = None, filename: str = None) -> str:
    """
    Executes Python code.
    - Mode A (File): Runs a .py file via subprocess (Safe, supports imports).
    - Mode B (String): Runs a string via exec() (Fast, limits imports).
    """
    # Mode A: File Execution (Preferred for Q3/Q4)
    if filename:
        logger.info(f"Tool: run_python_code - Executing File: {filename}")
        try:
            result = subprocess.run(
                [sys.executable, filename],
                capture_output=True,
                text=True,
                timeout=15,
                encoding='utf-8'
            )
            output = result.stdout + result.stderr
            if not output: return "Script executed successfully (No Output)."
            return f"Output:\n{output}"
        except Exception as e:
            return f"Error executing file: {e}"

    # Mode B: String Execution (Legacy/Simple tasks)
    elif code_string:
        logger.info(f"Tool: run_python_code - Executing String")
        buffer = io.StringIO()
        allowed_globals = {
            "pd": pd, "plt": plt, "io": io, "base64": base64, 
            "json": json, "re": re, "open": open,
            "print": lambda *args: buffer.write(" ".join(map(str, args)) + "\n")
        }
        try:
            with redirect_stdout(buffer):
                exec(code_string, allowed_globals)
            return f"Output:\n{buffer.getvalue()}"
        except Exception as e:
            return f"Error executing string: {e}"
    
    return "Error: No code or filename provided."

# --- Tool 6: Answer Submitter ---
def submit_answer(submit_url: str, answer_payload: dict, email: str, secret: str, task_url: str) -> str:
    """Submits the final JSON payload to the quiz server."""
    logger.info(f"Tool: submit_answer - URL: {submit_url}")
    try:
        final_payload = {
            "email": email,
            "secret": secret,
            "url": task_url,
            **answer_payload
        }
        response = requests.post(submit_url, json=final_payload, timeout=NETWORK_TIMEOUT)
        return f"Submission response: {response.text}"
    except Exception as e:
        return f"Error submitting answer: {e}"