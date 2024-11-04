#import base64
import tempfile
import json
import requests
from imapclient import IMAPClient
from mailparser import parse_from_bytes
from dotenv import load_dotenv
import os
import sys
from PyPDF2 import PdfReader
from docx import Document 
from mailjet_rest import Client
import time

# Load environment variables from .env file
load_dotenv()

# IMAP server and credentials
IMAP_SERVER = "mail.hover.com"
IMAP_PORT = 993 
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
PASSWORD = os.getenv("EMAIL_PASSWORD")

# Mailjet credentials from the .env file
MAILJET_API_KEY = os.getenv("MAILJET_API_KEY")
MAILJET_API_SECRET = os.getenv("MAILJET_API_SECRET")

POLL_INTERVAL = 300

# Ollama settings
OLLAMA_LOCAL_URL = "http://localhost:11434"
OLLAMA_DOCKER_HOST_URL = "http://host.docker.internal:11434"
MODEL_NAME = "OpenChat"
PROMPT_TEMPLATE = """
Analyze the following email content and determine if it is a job application for a cleaning job. Terms like ‘applying’, ‘resume’, ‘application’, ‘position,’ ‘job opportunity', 'cleaning job,'  and ‘seeking employment’ are highly indicative of a job submission email. If there is an attachment, note that this may be a resume, reinforcing that this is likely a job application.
If it is, check if the applicant is located in "Victoria",  if not Victoria then are they at least in "Canada" or "Out of Country". 
Respond only with a JSON object containing:
- jobApplication: (true/false)
- location: ("Victoria", "Canada" or "Out of Country" if jobApplication is true)
- first name (if jobApplication is true)

Email Content:
\"\"\"
{content}
\"\"\"
"""

# Function to test connection to Ollama
def test_ollama_connection(url):
    try:
        # Sending a minimal test request to check connection
        response = requests.post(f"{url}/api/generate", json={"model": MODEL_NAME})
        if response.status_code == 200 and response.json().get("done") == True:
            print(f"Successfully connected to Ollama at {url}")
            return url
    except requests.RequestException as e:
        print(f"Failed to connect to Ollama at {url}: {e}")
    return None

# Try connecting to Ollama on localhost first, then host.docker.internal
OLLAMA_URL = test_ollama_connection(OLLAMA_LOCAL_URL) or test_ollama_connection(OLLAMA_DOCKER_HOST_URL)

# If both connections fail, log and exit
if not OLLAMA_URL:
    print("Error: Could not connect to Ollama on localhost or host.docker.internal.")
    sys.exit(1)
else:
    print(f"Using Ollama URL: {OLLAMA_URL}")