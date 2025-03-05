import chainlit as cl
import gspread
import cohere
import numpy as np
import re
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from datetime import datetime

# 🔹 Cohere API Key (directly embedded)
COHERE_API_KEY = "EFWoGl23ROfZ1nzMcOtI4CZzQL6KBX6lTH2eJfSX"  # Replace with your actual Cohere API key

# Initialize Cohere client
co = cohere.Client(COHERE_API_KEY)

# Google Sheets configuration
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "C:/Users/Jeyavarman Murugan/Downloads/testbot-450217-01569e11e763.json"  # Replace with your actual credentials file
SPREADSHEET_NAME = "Untitled spreadsheet"  # Replace with your actual Google Sheet name

# 🔹 Authenticate and connect to Google Sheets
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPE)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# Caching to reduce API calls
cached_data = None
cached_embeddings = None

# Function to preprocess text
def preprocess_text(text):
    # Normalize text: lowercase and remove special characters
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text

# Function to extract keywords (e.g., machine names) from user input
def extract_keywords(text, machine_names):
    # Extract keywords that match machine names
    keywords = []
    for machine in machine_names:
        if machine.lower() in text.lower():
            keywords.append(machine)
    return keywords

# Function to generate Cohere embeddings
def get_embedding(text):
    response = co.embed(texts=[text], model="embed-english-v3.0", input_type="search_query")
    return np.array(response.embeddings[0])

# Fetch and preprocess machine issues (cache for efficiency)
def get_machine_issues():
    global cached_data, cached_embeddings
    if cached_data is None:
        cached_data = sheet.get_all_records()
        if cached_data:
            print(f"✅ Column Names in Sheet: {cached_data[0].keys()}")
            
            # Generate embeddings for all issue descriptions
            cached_embeddings = [get_embedding(row.get("Issue Description", "")) for row in cached_data]
        else:
            print("⚠️ No data found in the sheet!")
            cached_embeddings = []
    
    return cached_data, cached_embeddings

# Function to generate detailed responses using Cohere
def generate_detailed_response(prompt):
    response = co.generate(
        model='command',
        prompt=prompt,
        max_tokens=300,
        temperature=0.7
    )
    return response.generations[0].text.strip()

# Find the best match using NLP-based similarity search
def find_best_match(user_query):
    data, embeddings = get_machine_issues()
    
    if not data or not embeddings:
        return None
    
    # Preprocess user query
    processed_query = preprocess_text(user_query)
    
    # Extract machine names from the data
    machine_names = list(set(row.get("Machine Name", "") for row in data))
    
    # Extract keywords from the user query
    keywords = extract_keywords(processed_query, machine_names)
    
    # Generate embeddings for the user query
    query_embedding = get_embedding(processed_query)
    
    # Compute similarity scores
    similarities = cosine_similarity([query_embedding], embeddings)[0]
    
    # Find the best match
    best_match_index = np.argmax(similarities)
    
    # If similarity is high, return the corresponding row
    if similarities[best_match_index] > 0.5:  # Adjust threshold if needed
        return data[best_match_index]
    
    return None

# Function to count machines by type
def count_machines_by_type(data):
    machine_counts = defaultdict(int)
    for row in data:
        machine_type = row.get("Machine Name", "").split()[0]  # Assuming the type is the first word in the machine name
        machine_counts[machine_type] += 1
    return machine_counts

# Function to get the last repair date for a specific machine
def get_last_repair_date(data, machine_name):
    last_repair_date = None
    for row in data:
        if row.get("Machine Name", "").lower() == machine_name.lower():
            date_str = row.get("Date of Repair", "")
            if date_str:
                date = datetime.strptime(date_str, "%Y-%m-%d")  # Adjust the date format as per your sheet
                if last_repair_date is None or date > last_repair_date:
                    last_repair_date = date
    return last_repair_date

# Function to search for a specific machine in the spreadsheet
def search_machine_in_spreadsheet(machine_name):
    # Fetch all rows from the spreadsheet
    data = sheet.get_all_records()
    
    # Iterate through each row to find the machine
    for row in data:
        if row.get("Machine Name", "").lower() == machine_name.lower():
            return row  # Return the matching row
    
    return None  # Return None if no match is found

# Function to get the latest details of a specific machine by its ID
def get_latest_machine_details_by_id(data, machine_id):
    latest_entry = None
    latest_date = None
    
    for row in data:
        if row.get("ID", "").lower() == machine_id.lower():
            date_str = row.get("Date of Repair", "")
            if date_str:
                date = datetime.strptime(date_str, "%Y-%m-%d")  # Adjust the date format as per your sheet
                if latest_date is None or date > latest_date:
                    latest_date = date
                    latest_entry = row
    
    return latest_entry

# Function to extract machine ID from the user query
def extract_machine_id(user_query):
    # Use regex to find patterns like "mm001", "MM001", "mm 001", etc.
    machine_id_match = re.search(r'\b(mm|MM)?\s?\d{3}\b', user_query)
    if machine_id_match:
        return machine_id_match.group().replace(" ", "").lower()  # Normalize the machine ID
    return None

# Function to detect intent from user query
def detect_intent(user_query):
    user_query = user_query.lower()
    
    # Check if the query contains a machine ID
    machine_id = extract_machine_id(user_query)
    if machine_id:
        return "get_machine_details_by_id", machine_id
    
    # Intent: Count CNC machines
    if "cnc" in user_query and ("count" in user_query or "number" in user_query or "how many" in user_query):
        return "count_cnc_machines", None
    
    # Intent: Count total machines
    if ("total" in user_query or "number" in user_query or "how many" in user_query) and "machine" in user_query:
        return "count_total_machines", None
    
    # Intent: Machines repaired before a specific year
    if "repaired before" in user_query or "repaired till" in user_query:
        return "machines_repaired_before_year", None
    
    # Intent: Machines repaired by a specific technician
    if "repaired by" in user_query or "technician" in user_query:
        return "get_machines_repaired_by_technician", None
    
    # Default intent: General query
    return "general_query", None

# Main function to handle user queries
@cl.on_message
async def main(message):
    user_query = message.content
    print(f"🔍 Received Query: {user_query}")

    # Fetch data and machine names
    data, _ = get_machine_issues()
    machine_names = list(set(row.get("Machine Name", "") for row in data))

    # Detect intent and extract machine ID (if any)
    intent, machine_id = detect_intent(user_query)

    # Handle specific intents
    if intent == "get_machine_details_by_id":
        result = get_latest_machine_details_by_id(data, machine_id)
        if result:
            response = (
                f"**🔧 Machine Name:** {result.get('Machine Name', 'N/A')}\n\n"
                f"**🔧 Problem:** {result.get('Issue Description', 'N/A')}\n\n"
                f"**⚠️ Root Cause:** {result.get('Root Cause', 'N/A')}\n\n"
                f"**💡 Solution Applied:** {result.get('Solution Applied', 'N/A')}\n\n"
                f"**👷 Technician:** {result.get('Technician Name', 'N/A')}\n"
                f"📅 **Date of Repair:** {result.get('Date of Repair', 'N/A')}\n"
                f"⏳ **Time Taken:** {result.get('Time Taken (in hours)', 'N/A')} hours\n"
                f"📉 **Production Loss:** {result.get('Production Loss ()', 'N/A')}%\n\n"
                f"📝 **Additional Info:** {result.get('Additional Information', 'None')}"
            )
        else:
            response = f"No machine found with ID {machine_id}."
    elif intent == "count_cnc_machines":
        count = count_cnc_machines(data)
        response = f"There are {count} CNC machines in the list."
    elif intent == "count_total_machines":
        total_count = len(data)
        response = f"There are a total of {total_count} machines in the list."
    elif intent == "machines_repaired_before_year":
        # Extract the year from the query
        year_match = re.search(r"\d{4}", user_query)
        if year_match:
            year = int(year_match.group())
            machines = get_machines_repaired_before_year(data, year)
            count = len(machines)
            response = f"There are {count} machines repaired before {year}."
        else:
            response = "Please specify a valid year in your query."
    elif intent == "get_machines_repaired_by_technician":
        technician_name = user_query.lower().split("repaired by")[1].strip()
        machines = get_machines_repaired_by_technician(data, technician_name)
        if machines:
            response = f"Machines repaired by {technician_name}: {', '.join(machines)}"
        else:
            response = f"No machines found repaired by {technician_name}."
    else:
        # Find best match using NLP-based search
        result = find_best_match(user_query)

        if result:
            # If a match is found, provide the details from the Google Sheet
            response = (
                f"**🔧 Problem:** {result.get('Issue Description', 'N/A')}\n\n"
                f"**⚠️ Root Cause:** {result.get('Root Cause', 'N/A')}\n\n"
                f"**💡 Solution Applied:** {result.get('Solution Applied', 'N/A')}\n\n"
                f"**👷 Technician:** {result.get('Technician Name', 'N/A')}\n"
                f"📅 **Date of Repair:** {result.get('Date of Repair', 'N/A')}\n"
                f"⏳ **Time Taken:** {result.get('Time Taken (in hours)', 'N/A')} hours\n"
                f"📉 **Production Loss:** {result.get('Production Loss ()', 'N/A')}%\n\n"
                f"📝 **Additional Info:** {result.get('Additional Information', 'None')}"
            )
        else:
            # If no match is found, generate a detailed response using Cohere
            prompt = f"Provide a step-by-step process to resolve the following issue: {user_query}"
            response = generate_detailed_response(prompt)

    # Send the response back to the Chainlit UI
    await cl.Message(content=response).send()