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

# Function to detect intent from user query using semantic similarity
def detect_intent(user_query):
    user_query = user_query.lower()
    best_intent = "general_query"
    highest_similarity = 0.5  # Set a threshold for similarity

    # Define intent phrases
    intent_phrases = {
        "get_issue_description": [
            "What is the issue with",
            "Describe the problem for",
            "Tell me about the issue for",
            "What's wrong with",
        ],
        "get_root_cause": [
            "What caused the issue with",
            "Root cause of",
            "Why did the problem occur for",
            "What led to the issue for",
        ],
        "get_solution_applied": [
            "What was the solution for",
            "How was the issue resolved for",
            "What fix was applied to",
            "Solution for",
        ],
        "count_repairs_for_machine": [
            "How many times has this machine been repaired",
            "Number of repairs for",
            "How often has this machine been fixed",
        ],
        "get_last_repair_technician": [
            "When was the last repair for",
            "Who last repaired",
            "Last repair date for",
        ],
        "get_production_loss": [
            "What is the production loss for",
            "How much production was lost for",
            "Production loss caused by",
        ],
        "get_repair_time": [
            "How long did it take to repair",
            "Repair time for",
            "Time taken to fix",
        ],
        "list_issues_for_machine": [
            "List all issues for",
            "What are the problems with",
            "Issues related to",
        ],
        "list_solutions_for_machine": [
            "List all solutions for",
            "What fixes were applied to",
            "Solutions for",
        ],
        "find_machine_with_highest_repair_time": [
            "Which machine took the longest to repair",
            "Machine with the highest repair time",
            "Longest repair time for a machine",
        ],
        "count_machines_repaired_by_technician": [
            "How many machines were repaired by",
            "Number of machines fixed by",
            "Machines repaired by",
        ],
        "list_machines_repaired_by_technician": [
            "List all machines repaired by",
            "Machines fixed by",
            "Which machines were repaired by",
        ],
        "find_technician_with_most_repairs": [
            "Which technician handled the most repairs",
            "Technician with the most repairs",
            "Who fixed the most machines",
        ],
    }

    # Get the embedding for the user query
    query_embedding = get_embedding(user_query)

    # Compare the query embedding with each intent phrase
    for intent, phrases in intent_phrases.items():
        for phrase in phrases:
            phrase_embedding = get_embedding(phrase)
            similarity = cosine_similarity([query_embedding], [phrase_embedding])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_intent = intent

    return best_intent

# Main function to handle user queries
@cl.on_message
async def main(message):
    user_query = message.content
    print(f"🔍 Received Query: {user_query}")

    # Fetch data and machine names
    data, _ = get_machine_issues()
    machine_names = list(set(row.get("Machine Name", "") for row in data))

    # Detect intent from the user query
    intent = detect_intent(user_query)

    # Handle specific intents
    if intent == "get_issue_description":
        machine_name = user_query.split("for ")[1].strip()
        issues = list_issues_for_machine(data, machine_name)
        response = f"Issues for {machine_name}:\n" + "\n".join(issues)
    elif intent == "get_root_cause":
        machine_name = user_query.split("for ")[1].strip()
        root_cause = None
        for row in data:
            if row.get("Machine Name", "").lower() == machine_name.lower():
                root_cause = row.get("Root Cause", "N/A")
                break
        response = f"Root cause for {machine_name}: {root_cause}"
    elif intent == "get_solution_applied":
        machine_name = user_query.split("for ")[1].strip()
        solutions = list_solutions_for_machine(data, machine_name)
        response = f"Solutions applied to {machine_name}:\n" + "\n".join(solutions)
    elif intent == "count_repairs_for_machine":
        machine_name = user_query.split("has ")[1].split(" been")[0].strip()
        count = count_repairs_for_machine(data, machine_name)
        response = f"{machine_name} has been repaired {count} times."
    elif intent == "get_last_repair_technician":
        machine_name = user_query.split("last repaired ")[1].strip()
        last_repair_date = get_last_repair_date(data, machine_name)
        if last_repair_date:
            response = f"The last repair for {machine_name} was on {last_repair_date.strftime('%Y-%m-%d')}."
        else:
            response = f"No repair records found for {machine_name}."
    elif intent == "get_production_loss":
        machine_name = user_query.split("for ")[1].strip()
        production_loss = get_production_loss(data, machine_name)
        response = f"Production loss for {machine_name}: {production_loss}%"
    elif intent == "get_repair_time":
        machine_name = user_query.split("repair ")[1].split(" on")[0].strip()
        date = user_query.split("on ")[1].strip()
        repair_time = get_repair_time(data, machine_name, date)
        response = f"Repair time for {machine_name} on {date}: {repair_time} hours"
    elif intent == "list_issues_for_machine":
        machine_name = user_query.split("related to ")[1].strip()
        issues = list_issues_for_machine(data, machine_name)
        response = f"Issues related to {machine_name}:\n" + "\n".join(issues)
    elif intent == "list_solutions_for_machine":
        machine_name = user_query.split("applied to ")[1].strip()
        solutions = list_solutions_for_machine(data, machine_name)
        response = f"Solutions applied to {machine_name}:\n" + "\n".join(solutions)
    elif intent == "find_machine_with_highest_repair_time":
        machine_name, repair_time = find_machine_with_highest_repair_time(data)
        response = f"The machine with the highest repair time is {machine_name} with {repair_time} hours."
    elif intent == "count_machines_repaired_by_technician":
        technician_name = user_query.split("has ")[1].split(" repaired")[0].strip()
        count = count_machines_repaired_by_technician(data, technician_name)
        response = f"{technician_name} has repaired {count} machines."
    elif intent == "list_machines_repaired_by_technician":
        technician_name = user_query.split("repaired by ")[1].strip()
        machines = list_machines_repaired_by_technician(data, technician_name)
        response = f"Machines repaired by {technician_name}:\n" + "\n".join(machines)
    elif intent == "find_technician_with_most_repairs":
        technician = find_technician_with_most_repairs(data)
        response = f"The technician who handled the most repairs is {technician}."
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