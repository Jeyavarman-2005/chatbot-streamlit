import gspread
import chainlit as cl
from oauth2client.service_account import ServiceAccountCredentials
from fuzzywuzzy import process

# 🔹 Setup Google Sheets API
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "C:/Users/Jeyavarman Murugan/Downloads/mechmate-449307-12fe16037e5d.json"  # Replace with your actual credentials file
SPREADSHEET_NAME = "MechMate"  # Replace with your actual Google Sheet name

# 🔹 Authenticate and connect to Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1  # Access first sheet

# 🔹 Fetch all data
data = sheet.get_all_records()
problems = {row["Problem Description"]: row for row in data}  # Create a dictionary for quick search


# 🔹 Function to find the best matching problem
def find_best_match(query):
    problem_list = list(problems.keys())
    best_match, score = process.extractOne(query, problem_list)
    if score > 70:  # Adjust threshold as needed
        return problems[best_match]
    return None


# 🔹 Chainlit Chatbot
@cl.on_message
async def on_message(message):
    query = message.content.strip()
    match = find_best_match(query)

    if match:
        response = (
            f"🔹 **Problem:** {match['Problem Description']}\n"
            f"🔍 **Possible Cause:** {match['Possible Causes']}\n"
            f"💡 **Solution:** {match['Solution']}"
        )
    else:
        response = "⚠️ No matching solution found. Please provide more details."

    await cl.Message(content=response).send()