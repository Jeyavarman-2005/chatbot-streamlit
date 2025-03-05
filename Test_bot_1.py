import chainlit as cl
import gspread
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process, fuzz

# Google Sheets API Setup
SPREADSHEET_ID = "1NUajw-DwCS9pScyoVhzGOAKVl25ycfXie-h4Q5Drr7E"  # Replace with actual spreadsheet ID
SHEET_NAME = "Test_Bot"  # Change if needed

# Authenticate with Google Sheets API
creds = Credentials.from_service_account_file("C:/Users/Jeyavarman Murugan/Downloads/Rane_Internship_2025\MechMate_Chatbot/mechmate-449304-9a27927dbeba.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# Caching mechanism to avoid excessive API calls
cached_data = None

def get_machine_issues():
    global cached_data
    if cached_data is None:
        cached_data = sheet.get_all_records()
        if cached_data:
            print(f"✅ Column Names in Sheet: {cached_data[0].keys()}")
        else:
            print("⚠️ No data found in the sheet!")
    return cached_data

# Improved fuzzy matching function
def find_best_match(query, data):
    problem_descriptions = [row.get("Issue Description", "") for row in data]
    best_match, score = process.extractOne(query, problem_descriptions, scorer=fuzz.partial_ratio)

    if score > 65:  # Reduced threshold to match broader queries
        for row in data:
            if row.get("Issue Description", "") == best_match:
                return row  # Return the full row of data
    return None

@cl.on_message
async def main(message):
    user_query = message.content
    cl.console.print(f"🔍 Received Query: {user_query}", style="bold green")

    # Fetch machine issues
    data = get_machine_issues()

    if not data:
        await cl.Message(content="⚠️ No data found in the sheet. Please check your Google Sheet.").send()
        return

    # Find best match
    result = find_best_match(user_query, data)

    if result:
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
        response = "⚠️ No matching solution found. Please provide more details."

    await cl.Message(content=response).send()
