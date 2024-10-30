from imapclient import IMAPClient
from mailparser import parse_from_bytes  # Fixed import statement
from dotenv import load_dotenv
import os

# Load environment variables from a .env file (if using one)
load_dotenv()

# Access environment variables
print("MJ Account:", os.getenv("MAILJET_API_KEY"))
print("Password:", os.getenv("MAILJET_API_SECRET"))