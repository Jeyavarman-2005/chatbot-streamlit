from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import time

# 🔹 1. Google Sheets API Authentication
SERVICE_ACCOUNT_FILE = "C:/Users/Jeyavarman Murugan/Downloads/chatbot-project-449205-7d9c06a22f7a.json"  # Update with correct JSON file path
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# 🔹 2. Connect to Google Sheets
SPREADSHEET_ID = "1J1yRJsrv4V7UHZVBn2QTXxuqqSBUzcJE4pyrix63YZA"  # Update with your Google Sheet ID
SHEET_NAME = "Sheet1"  # Ensure this matches your sheet's name
RANGE_NAME = f"{SHEET_NAME}!A:D"  # Adjust based on your column range

# 🔹 3. Initialize Google Sheets API
service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()

# 🔹 4. Fetch Data from Google Sheets
def fetch_google_sheets_data():
    try:
        print("🔹 Fetching data from Google Sheets...")  
        time.sleep(2)  # Prevent hitting API rate limits
        
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        rows = result.get("values", [])

        print("✅ API Response Received:", result)  # Debugging Output

        if not rows:
            print("❌ ERROR: No data found in the specified range!")
            return None

        return rows

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

# 🔹 5. Run the script
if __name__ == "__main__":
    data = fetch_google_sheets_data()

    if data:
        print("\n📌 First 5 Rows of Data:")
        for row in data[:5]:  # Print only first 5 rows to avoid clutter
            print(row)
    else:
        print("❌ No data retrieved. Check your sheet permissions and range.")
