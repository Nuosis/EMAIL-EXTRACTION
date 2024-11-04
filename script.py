#Here is the workflow

#**Get all unread messages from my imap account

#**Extract subject, content and email attachments (encode to base 64)

#send to local LLM for analysis to confirm this is a job application 

#also use LLM to confirm they are likely in the Victoria area

#use HTML (to be written) to reply to those messages that are applications in the Victoria area via mail jet api

#Update these messages as read and move to resumes folder

#reply to email messages with HTML (TO be written) that are job applications but NOT for Victoria via MailJet api

#Update these messages as read and move to archive


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

email_template = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Select Home Cleaning</title></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f9f9f9;">
<table width="100%" border="0" cellspacing="0" cellpadding="0">
<tr><td align="center" style="padding:20px;">
<img src="https://server.claritybusinesssolutions.ca/shc/logo.png" alt="Select Home Cleaning" style="width:150px;height:auto;">
</td></tr>
<tr><td align="center">
<table border="0" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background-color:#ffffff;border-radius:8px;overflow:hidden;">
<tr><td style="padding:20px;text-align:center;background-color:rgb(0,100,55);color:#ffffff;">
<h1 style="margin:0;font-size:24px;">Welcome to Select Home Cleaning</h1>
<p style="margin:0;font-size:16px;">Click. Clean. Carry On!</p>
</td></tr>
<tr><td style="padding:30px;color:#333333;">
<p style="font-size:16px;line-height:1.6;">{{TEXT}}</p>
<p style="font-size:16px;line-height:1.6;">Warm regards,<br>The Select Home Cleaning Team</p>
</td></tr>
<tr><td align="center" style="padding:20px;background-color:rgb(0,100,55);">
<a href="https://www.selecthomecleaning.ca" style="color:#ffffff;text-decoration:none;font-size:16px;">Visit our website (Coming Soon!)</a>
</td></tr>
</table>
</td></tr>
<tr><td align="center" style="padding:20px;font-size:12px;color:#666666;">
© 2024 Select Home Cleaning. All rights reserved. | <a href="https://www.yourwebsite.com" style="color:#666666;text-decoration:none;">Privacy Policy</a>
</td></tr>
</table></body></html>
"""

victoria_based_message = """
Hello,

Thank you for reaching out to us at Select Home Cleaning! We're thrilled to hear from someone in the Victoria area, especially as we prepare to launch our brand-new residential cleaning service.

We’ll soon be opening up our application process, and we’d love for you to be a part of it! We've saved your email, and as soon as the application is live, you'll receive a direct link to apply and join our team.

Exciting times are ahead, and we can't wait to get started with amazing people like you!
"""

canada_based_message = """
Hello,

Thank you for your interest in joining Select Home Cleaning! We're excited to connect with talented cleaners from across Canada.

As we prepare to launch our residential cleaning service in beautiful Victoria, BC, we’re prioritizing applicants who are based in the Victoria area or are willing to relocate. If you're open to making Victoria your base, please reply to this email to let us know. This will help us include you in our launch notifications and application process!

We’re thrilled about the journey ahead and would love to consider you for our team if Victoria sounds like a fit!
"""

out_of_country_message = """
Hello,

Thank you for your interest in joining Select Home Cleaning! We truly appreciate hearing from skilled professionals around the world.

At this time, our hiring is focused locally within Canada, specifically in Victoria, BC, as we prepare to launch our residential cleaning service. While we are currently accepting international applications, we are awaiting approval from the Canadian Government. Your interest is helpful in this process and we encourage you to stay connected for future opportunities as we continue to grow.

If you received this message and are local, please reapply with more text so we can better identify you and your application

Thank you again, and we wish you all the best in your job search!
"""

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))  # Default to 5 mins if not set

# Initialize a set to keep track of checked message IDs
checked_message_ids = set()

# Initialize Mailjet client
mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')

# Email sending function using Mailjet
def send_email(recipient_email, subject, message):
    data = {
        'Messages': [
            {
                "From": {
                    "Email": "marcus@selectjanitorial.com",  # Replace with your sender email
                    "Name": "Select Home Cleaning"
                },
                "To": [
                    {
                        "Email": recipient_email,
                        "Name": "Applicant"
                    }
                ],
                "Subject": subject,
                "HTMLPart": email_template.replace("{{TEXT}}", message),
            }
        ]
    }
    
    # Send the email
    result = mailjet.send.create(data=data)
    if result.status_code == 200:
        print(f"Email sent to {recipient_email}")
    else:
        print(f"Failed to send email to {recipient_email}. Status: {result.status_code}, Error: {result.json()}")

def check_ollama_connection():
    try:
        response = requests.get(OLLAMA_URL)
        if response.status_code == 200:
            print("Successfully connected to Ollama.")
        else:
            print(f"Connection to Ollama failed with status code {response.status_code}.")
    except requests.RequestException as e:
        print("Error connecting to Ollama:", e)

def extract_text_from_pdf(content):
    """Extracts text from a PDF content in bytes, handling errors gracefully."""
    try:
        # Check if content is in bytes, if not already
        if isinstance(content, str):
            content = content.encode("utf-8")
        
        # Validate that content seems to be a PDF
        if not content.startswith(b"%PDF"):
            print("Warning: Content does not appear to be a valid PDF file.")
            return ""  # Exit early if it's likely not a PDF
        
        # Write content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name
            print(f"Temporary PDF path created: {temp_pdf_path}")  # Debug log

        # Attempt to read from the temporary file using PdfReader
        try:
            reader = PdfReader(temp_pdf_path)
            text = []
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
                else:
                    print(f"Warning: No text found on page {page_num}")  # Debug log
            extracted_text = "\n".join(text) if text else ""
            if not extracted_text:
                print("Warning: No text extracted from PDF.")
            return extracted_text
        except Exception as pdf_error:
            print("Error during PDF reading:", pdf_error)
            return ""
        finally:
            # Clean up temporary file
            os.remove(temp_pdf_path)
            print(f"Temporary PDF path deleted: {temp_pdf_path}")  # Debug log

    except Exception as general_error:
        print("General error handling PDF:", general_error)
        return ""

def extract_text_from_docx(content):
    """Extracts text from a DOCX content in bytes."""
    try:
        # Save the DOCX content to a temporary file
        with open("temp.docx", "wb") as f:
            f.write(content)
        
        doc = Document("temp.docx")
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        
        os.remove("temp.docx")  # Clean up temporary file
        return "\n".join(text)
    except Exception as e:
        print("Error extracting text from DOCX:", e)
        return ""

# Function to process the job application based on location
def process_job_application(client, msg_id, analysis, recipient_email):
    # Determine the message to send based on the applicant's location
    if "Victoria" in analysis.get("location", ""):
        message = victoria_based_message
        subject = "Join Our Team at Select Home Cleaning in Victoria!"
        send_email(recipient_email, subject, message)
        
        # Move message to resumes folder
        client.move([msg_id], "resumes")
        print(f"Message moved to 'resumes' folder for {recipient_email}.")

    elif "Canada" in analysis.get("location", ""):
        message = canada_based_message
        subject = "Opportunities with Select Home Cleaning"
        send_email(recipient_email, subject, message)
        
        # Archive the message
        client.move([msg_id], "Archive")
        print(f"Message archived for {recipient_email} (Canada-based).")

    else:
        message = out_of_country_message
        subject = "Thank You from Select Home Cleaning"
        send_email(recipient_email, subject, message)
        
        # Archive the message for out-of-country applicants
        client.move([msg_id], "Archive")
        print(f"Message archived for {recipient_email} (Out of Country).")
        message = out_of_country_message
        subject = "Thank You from Select Home Cleaning"
        send_email(recipient_email, subject, message)
        
        # Archive the message for out-of-country applicants
        client.move([msg_id], "Archive")
        print(f"Message archived for {recipient_email} (Out of Country).")

# Initialize a set to keep track of checked message IDs
checked_message_ids = set()

def fetch_unread_emails():
    global checked_message_ids  # Use the global set to persist checked IDs across polls
    try:
        # Connect to the IMAP server
        print("Connecting to IMAP server...")
        with IMAPClient(IMAP_SERVER, ssl=True, port=IMAP_PORT) as client:
            client.login(EMAIL_ACCOUNT, PASSWORD)
            print("Logged in successfully.")

            # Select the inbox
            client.select_folder("INBOX")

            # Search for unread messages
            print("Searching for unread messages...")
            unread_messages = client.search("UNSEEN")
            print(f"Found {len(unread_messages)} unread messages.")

            # Loop through each unread message and fetch details
            for msg_id in unread_messages:
                # Skip if the message was already checked in a previous cycle
                if msg_id in checked_message_ids:
                    print(f"Skipping already checked message ID: {msg_id}")
                    continue

                # Initialize additional content for each email
                additional_content = ""

                # Fetch email data
                raw_message = client.fetch([msg_id], ["RFC822"])[msg_id][b"RFC822"]
                email = parse_from_bytes(raw_message)

                # Extract sender's email
                from_data = email.from_
                recipient_email = from_data[0][1] if from_data and len(from_data[0]) > 1 else None
                if not recipient_email:
                    print(f"Skipping message {msg_id}, no sender email found.")
                    continue

                # Extract subject, body, and attachments
                subject = email.subject
                body = email.body

                print("Sender Email:", recipient_email)
                print("Subject:", subject)
                print("Body:", body)

                # Process attachments (if any)
                for attachment in email.attachments:
                    filename = attachment["filename"]
                    content = attachment["payload"]

                    if filename:
                        attachment_present = True 
                        if filename.lower().endswith(".pdf"):
                            additional_content += "\n" + extract_text_from_pdf(content)
                        elif filename.lower().endswith(".docx"):
                            additional_content += "\n" + extract_text_from_docx(content)
                        elif filename.lower().endswith((".jpg", ".jpeg")):
                            additional_content += f"\n[Image attachment: {filename}]"
                        else:
                            print(f"Skipping unsupported attachment type: {filename}")

                # Combine body and any extracted attachment text
                full_content = f"{'Attachment included: ' if attachment_present else ''}{subject}\n{body}\n{additional_content}"
                analysis = analyze_email_with_ollama(full_content)

                if analysis.get("jobApplication"):
                    print("Processing job application:", analysis)
                    process_job_application(client, msg_id, analysis, recipient_email)
                else:
                    print("Not a job application. Skipping this email.")
                    client.remove_flags([msg_id], ["\\Seen"])
                    print(f"Email reset to unread for message ID: {msg_id}")

                # Add message ID to the checked set
                checked_message_ids.add(msg_id)

    except Exception as e:
        print("An error occurred:", e)

def analyze_email_with_ollama(content):
    # Format the prompt by injecting the email and attachment content
    prompt = PROMPT_TEMPLATE.format(content=content)
    print("prompt: ",prompt)

    # Define the JSON payload
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        # Send the request to Ollama
        # print("payload:", payload)
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("Ollama Response:", result)

            # Extract and parse the 'response' key content as JSON
            if 'response' in result:
                try:
                    # Parse the response field as JSON
                    analysis = json.loads(result['response'].strip())
                    print("Parsed Analysis:", analysis)
                    return analysis
                except json.JSONDecodeError as e:
                    print(f"JSON decoding error: {e}. Response content: {result['response']}")
                    return None
            else:
                print("No 'response' key found in Ollama response.")
                return None
        else:
            print(f"Failed to generate response from Ollama. Status code: {response.status_code}")

    except requests.RequestException as e:
        print("Error sending data to Ollama:", e)

# Check connection to Ollama
check_ollama_connection()

# Run the function to test it
fetch_unread_emails()

def start_polling():
    while True:
        fetch_unread_emails()
        print(f"Waiting {POLL_INTERVAL} seconds until next check...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    start_polling()