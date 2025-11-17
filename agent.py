import json
import re
import requests
from urllib.parse import urljoin
import time

from config import logger, AI_PIPE_TOKEN, AI_PIPE_URL
import tools

SYSTEM_PROMPT = """
You are an expert-level autonomous data analyst agent.
Your goal is to solve a multi-step data quiz by creating and executing a plan.

You operate in a strict "Reason-Act" loop.
At each step, I will provide you with an "Observation".
You MUST respond with a single, valid JSON block.

**CRITICAL: JSON-ONLY RESPONSE**
You MUST NOT write any text or explanations before or after the JSON block.
Your entire response must be ONLY the JSON object.

**CRITICAL: RESPONSE STRUCTURE**
Your JSON response MUST contain three keys:
1.  `"analysis"`: Your step-by-step analysis of the 'Observation'. What does it mean? What are the clues (files, links, hidden text)? What are the red herrings?
2.  `"plan"`: Your high-level, multi-step plan to solve the *entire* task from this point forward.
3.  `"action"`: The *single* tool call that executes the *first step* of your plan.

**YOUR CORE HEURISTICS (How to Think):**

1.  **YOUR JOB AT SUBMISSION:** The `submit_answer` tool is "smart." It automatically adds the correct `email`, `secret`, and `url`. Your job is to provide *only* the answer. Your `answer_payload` MUST *only* contain the `{"answer": ...}` key.

2.  **CLUES ARE NOT ANSWERS :** An "action" (like a link or file) is **almost always the correct path.** Your `plan` MUST be to process the "data" to find the *next "action"*.

3.  **TEST BEFORE SERVING CODES :** For any question, if you are using `run_python_code`, you must test/decode/validate the logic before submission.

4.  **LOGIC FILES REQUIRE FULL CONTENT.** For *logic files* (`.js`, `.txt`), you must use the `download_and_read_file` tool. Immediately following this, you must use `read_file(filename='...')` to see the full content before planning further. **Do not plan based on the preview alone.**

5.  **JAVASCRIPT IS THE TRUTH:** The logic found in a `.js` file is *always* the "truth" for calculations. It is more important than any static text.

6.  **HTML IS THE GOAL :** The *HTML page* contains the *goal* of the data task (e.g., "find the **sum** of values"). **If no goal is explicitly stated, you must assume the goal is to SUM.**

7.  **PYTHON MUST BE JSON-SAFE :** When using `run_python_code` with `code_string`, your code *must* be a single-line JSON string, using `\n` for newlines.

8.  **USE YOUR MEMORY:** Use `write_to_file` to save key facts (like `GOAL=sum` or `CUTOFF=123`) for later Python steps.

9.  **JS vs. HTML MISMATCH (Retry Logic):** If the static HTML value contradicts the logic in a `.js` file, follow the logic in this order:
    * **First Attempt:** Follow **Heuristic #5 (JAVASCRIPT IS THE TRUTH)**.
    * **If Submission Fails:** Immediately retry the problem using the **static HTML value** instead.

10. **EFFICIENCY: ONE-SHOT CALCULATION.** Your goal is to be efficient. For final data tasks (like Q2 or Q3), your calculation **must be done in a single `run_python_code` action** whenever possible.

11. **AVOID JSON ERRORS (File Execution):** To run complex code, use a 2-step plan:
    * **Step 1:** Use `write_to_file` to save your complex Python script (e.g., `script.py`).
    * **Step 2:** Use `run_python_code(filename='script.py')` to execute it.
    * This **avoids all "unterminated f-string literal" errors.**

12. **FILE NAMING IS FIXED.** When you use `download_and_read_file` for a `.csv` or `.json`, the file name is **always** saved as **`temp_data.csv`** (or `.json`). Your subsequent Python code **MUST** read from this fixed filename.

13. **`submit_answer` REQUIRES BOTH PARAMETERS.** The `submit_answer` tool *always* needs both `submit_url` and `answer_payload`. Your action *must* include both, e.g., `{"tool": "submit_answer", "parameters": {"submit_url": "...", "answer_payload": {...}}}`.

14. **FILE NAME PRE-FLIGHT CHECK.** Before any action reading `temp_data.csv`, confirm the file name is *correct* (`temp_data.csv`). **Do not use names from old tasks** (`temp_log.txt`).

15. **VISUALIZATION BOILERPLATE.** When creating a chart for Base64 submission (using `matplotlib.pyplot`), you **MUST** include `import matplotlib; matplotlib.use('Agg')` or `plt.switch_backend('Agg')` at the beginning of your script to ensure compatibility with the non-GUI execution environment. **DO NOT** use `plt.show()`.

16. **NEW: VISUALIZATION MUST USE FILE EXECUTION.** Due to the complexity of charting and encoding, all visualization tasks (Q4) **MUST** be executed using the **`write_to_file` $\rightarrow$ `run_python_code(filename='...')` pipeline** (Heuristic #11). The script **MUST** include the boilerplate (Heuristic #15).

**Available Tools:**
1.  `scrape_website(url: str)`
2.  `download_and_read_file(url: str)`
3.  `read_file(filename: str)`
4.  `write_to_file(filename: str, content: str, mode: str = 'w')`
5.  `run_python_code(code_string: str = None, filename: str = None)`
6.  `submit_answer(submit_url: str, answer_payload: dict)`
"""

def solve_quiz_task(email: str, secret: str, url: str, deadline: float = None):
    # (function implementation remains the same)
    """
    The main autonomous agent loop.
    Implements the "Scrape-First" optimization, deadline checking,
    and re-submission logic.
    """
    logger.info(f"--- Starting New Task --- Email: {email}, URL: {url}")
    
    history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    max_steps = 15

    logger.info(f"--- Step 1 / {max_steps} --- (Performing initial scrape)")
    try:
        observation = tools.scrape_website(url) 
    except Exception as e:
        logger.error(f"Initial scrape failed: {e}")
        observation = f"Error: The initial scrape of {url} failed. {e}"


    for step in range(1, max_steps): 
        
        if deadline and time.time() > deadline:
            logger.warning(f"Task for {url} exceeded 3-minute (170s) deadline. Terminating.")
            break 

        time_left_str = f"{round(deadline - time.time(), 1)}s" if deadline else "N/A"
        logger.info(f"--- Step {step+1} / {max_steps} --- (Time left: {time_left_str})")
        
        history.append({"role": "user", "content": f"Observation:\n{observation}\n\nProvide your JSON response:"})
        
        try:
            logger.info("Agent is reasoning (calling AI Pipe endpoint)...")
            
            headers = {
                "Authorization": f"Bearer {AI_PIPE_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "google/gemini-2.5-flash",
                "messages": history,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(AI_PIPE_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            response_data = response.json()
            response_text = response_data['choices'][0]['message']['content']
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if not json_match:
                logger.error(f"LLM did not return valid JSON. Response text: {response_text}")
                raise ValueError("LLM did not return valid JSON.")

            json_str = json_match.group(0)
            llm_response = json.loads(json_str)
            
            analysis = llm_response.get("analysis", "No analysis provided.")
            plan = llm_response.get("plan", "No plan provided.")
            action_obj = llm_response.get("action") 
            
            logger.info(f"Agent Analysis: {analysis}")
            logger.info(f"Agent Plan: {plan}")
            logger.info(f"Agent Action: {action_obj}") 

            history.append({"role": "model", "content": json_str})
            
        except Exception as e:
            logger.error(f"Failed to get/parse LLM response: {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                logger.error(f"Raw response text: {response.text}")
            observation = f"Error: Your last response was not valid or API call failed. Please try again. Error: {e}"
            continue 

        try:
            if not isinstance(action_obj, dict):
                raise ValueError(f"Action must be a dict, but got {type(action_obj)}")

            tool_name = action_obj.get("tool") or action_obj.get("type")

            if not tool_name:
                raise ValueError("Action object must contain a 'tool' or 'type' key.")

            if "parameters" in action_obj:
                args = action_obj.get("parameters", {})
            elif "args" in action_obj:
                args = action_obj.get("args", {})
            elif "kwargs" in action_obj:
                args = action_obj.get("kwargs", {})
            else:
                args = action_obj
            
            if tool_name in ["scrape_website", "download_and_read_file"]:
                call_url = args.get('url')
                if call_url and not call_url.startswith('http'):
                    call_url = urljoin(url, call_url) 
                    args['url'] = call_url 
            
            elif tool_name == "submit_answer":
                submit_url = args.get('submit_url')
                if submit_url and not submit_url.startswith('http'):
                    submit_url = urljoin(url, submit_url)
                    args['submit_url'] = submit_url


            if tool_name == "scrape_website":
                observation = tools.scrape_website(url=args['url'])
            
            elif tool_name == "download_and_read_file":
                observation = tools.download_and_read_file(url=args['url'])
            
            elif tool_name == "read_file":
                observation = tools.read_file(filename=args['filename'])

            elif tool_name == "write_to_file":
                mode = args.get('mode', 'w')
                observation = tools.write_to_file(filename=args['filename'], content=args['content'], mode=mode)

            elif tool_name == "run_python_code":
                observation = tools.run_python_code(
                    code_string=args.get('code_string'),
                    filename=args.get('filename')
                )
            
            elif tool_name == "submit_answer":
                current_task_url = url
                
                observation = tools.submit_answer(
                    submit_url=args['submit_url'],
                    answer_payload=args['answer_payload'],
                    email=email,
                    secret=secret,
                    task_url=current_task_url
                )
                
                logger.info("Submission complete. Analyzing response...")
                try:
                    json_response_part = observation.split("Submission response:", 1)[-1].strip()
                    submit_response_json = json.loads(json_response_part)
                    
                    is_correct = submit_response_json.get("correct", False)
                    new_url = submit_response_json.get("url")
                    reason = submit_response_json.get("reason", "No reason provided.")

                    if is_correct:
                        logger.info("Answer was CORRECT.")
                        if new_url:
                            logger.info(f"New URL found! Starting next task: {new_url}")
                            new_deadline = time.time() + 170
                            solve_quiz_task(email, secret, new_url, deadline=new_deadline)
                        else:
                            logger.info("No new URL found. Quiz is complete.")
                        
                        break 

                    else:
                        logger.warning(f"Answer was INCORRECT. Reason: {reason}")
                        
                        if new_url:
                            logger.warning(f"Skipping to new URL provided: {new_url}")
                            new_deadline = time.time() + 170
                            solve_quiz_task(email, secret, new_url, deadline=new_deadline)
                            break
                        else:
                            logger.warning("No new URL provided. Will attempt to re-submit.")
                            continue 

                except Exception as e:
                    logger.error(f"Could not parse 'submit_answer' response: {e}")
                    logger.error(f"Raw observation was: {observation}")
                    logger.error("Assuming fatal error, cannot continue this task.")
                    break

            else:
                observation = f"Error: Unknown tool '{tool_name}'. Please use one of the available tools."
        
        except Exception as e:
            logger.error(f"Error executing action '{action_obj}': {e}")
            observation = f"Error: Failed to execute action. {e}"

    logger.info(f"--- Task Finished --- URL: {url}")