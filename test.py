import requests
import json

# --- 1. CONFIGURE YOUR DETAILS ---
# !! IMPORTANT: Replace these with the *exact* values from your .env file !!
TEST_PAYLOAD = {
    "email": "23f2000790@ds.study.iitm.ac.in",
    "secret": "vivek-tds-p1-15-key-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
}
# -----------------------------------

# Your local server's endpoint
ENDPOINT_URL = "http://localhost:8000/solve"

def run_test():
    """
    Sends the test POST request to the local server.
    """
    print(f"Sending test request to: {ENDPOINT_URL}")
    print("Payload:")
    print(json.dumps(TEST_PAYLOAD, indent=2))
    
    # Check if user updated the placeholders
    if "your_email" in TEST_PAYLOAD["email"] or "your_actual_secret" in TEST_PAYLOAD["secret"]:
        print("\n" + "="*50)
        print("!! WARNING !!")
        print("Please update the 'email' and 'secret' fields in this test.py script before running.")
        print("="*50 + "\n")
        return

    try:
        response = requests.post(ENDPOINT_URL, json=TEST_PAYLOAD, timeout=10)
        
        # Raise an exception for bad status codes (like 403 Forbidden)
        response.raise_for_status()
        
        print("\n--- Success! ---")
        print("Server accepted the task. Response:")
        print(response.json())
        print("------------------")
        print("\nCheck your *other* PowerShell window (where the server is running) to see the agent's log.")

    except requests.exceptions.HTTPError as http_err:
        print("\n--- HTTP Error ---")
        print(f"Status Code: {http_err.response.status_code}")
        print("Response Body:")
        try:
            # Try to print JSON error detail (like "Invalid secret")
            print(http_err.response.json())
        except json.JSONDecodeError:
            print(http_err.response.text)
        print("------------------")
        if http_err.response.status_code == 403:
            print(">> Hint: Does the 'secret' in test.py match your .env file exactly?")

    except requests.exceptions.ConnectionError:
        print("\n--- Connection Error ---")
        print("Could not connect to the server.")
        print(f">> Hint: Is your server (main.py) running in the other terminal at {ENDPOINT_URL}?")
        print("------------------------")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    run_test()