import chainlit as cl
import gspread
import cohere
import numpy as np
import re
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from sklearn.metrics.pairwise import cosine_similarity

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
        if machine.lower() in text:
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
    if similarities[best_match_index] > 0.75:  # Adjust threshold if needed
        return data[best_match_index]
    
    return None

@cl.on_message
async def main(message):
    user_query = message.content
    print(f"🔍 Received Query: {user_query}")

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
            f"📉 **Production Loss:** {result.get('Production Loss (%)', 'N/A')}%\n\n"
            f"📝 **Additional Info:** {result.get('Additional Information', 'None')}"
        )
    else:
        # If no match is found, generate a detailed response using Cohere
        prompt = f"Provide a step-by-step process to resolve the following issue: {user_query}"
        response = generate_detailed_response(prompt)

    # Send the response back to the Chainlit UI
    await cl.Message(content=response).send()