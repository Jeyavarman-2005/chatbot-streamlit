from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import chainlit as cl

# 🔹 Step 1: Authenticate with Google Sheets API
SERVICE_ACCOUNT_FILE = "C:/Users/Jeyavarman Murugan/Downloads/mechmate-449307-12fe16037e5d.json"  # Update your JSON key path
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly","https://www.googleapis.com/auth/spreadsheets"]

# Load credentials
try:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
except Exception as e:
    print(f"Error during authentication or API setup: {e}")
    exit(1)

# 🔹 Step 2: Define the Spreadsheet ID & Range
SPREADSHEET_ID = "1NUajw-DwCS9pScyoVhzGOAKVl25ycfXie-h4Q5Drr7E"  # Your Sheet ID
RANGE_NAME = "Sheet1!A:D"  # Adjust based on your Google Sheet structure

# 🔹 Step 3: Function to Retrieve Troubleshooting Data

try:
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    print("✅ API Request Successful!")
except Exception as e:
    print(f"❌ Error fetching data: {e}")
    
def get_solution(issue_description):
    """Fetch solution from Google Sheets based on user input."""
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        rows = result.get("values", [])

        if not rows:
            return "⚠️ No data found in the spreadsheet."

        for row in rows:
            if len(row) > 1 and issue_description.lower() in row[0].lower():  # Check if input matches a stored issue
                return f"🔧 Solution: {row[1]}"  # Assuming column B has solutions

        return "⚠️ No matching solution found. Please provide more details."
    except Exception as e:
        return f"❌ Error fetching data from Google Sheets: {e}"

# 🔹 Step 4: Chainlit Integration (Chatbot UI)
@cl.on_message
async def on_message(message: cl.Message):
    """Handles chatbot queries and fetches responses."""
    issue = message.content.strip()
    if not issue:
        await cl.Message("Please provide a valid issue description.").send()
        return

    response = get_solution(issue)
    await cl.Message(response).send()

# 🔹 Step 5: Run the Chainlit App
if __name__ == "__main__":
    cl.run()


