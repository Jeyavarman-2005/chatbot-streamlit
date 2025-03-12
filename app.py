import chainlit as cl
import gspread
import cohere
import os
import json
import re
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict, Counter

# Load environment variables from .env file (useful for local testing)
load_dotenv()

# Retrieve values from environment variables
COHERE_API_KEY = os.getenv("API_KEY")  
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # Must be a single-line JSON string
SPREADSHEET_NAME = "Untitled spreadsheet"  # Replace with your actual Google Sheet name

# Ensure required environment variables are set
if not COHERE_API_KEY:
    raise ValueError("ERROR: COHERE_API_KEY environment variable is not set.")
if not GOOGLE_CREDENTIALS:
    raise ValueError("ERROR: GOOGLE_CREDENTIALS environment variable is not set.")

# Initialize Cohere API client
co = cohere.Client(COHERE_API_KEY)

# Google Sheets API Scope
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load Google credentials safely
try:
    google_credentials = json.loads(GOOGLE_CREDENTIALS)
    if "private_key" not in google_credentials or not google_credentials["private_key"]:
        raise ValueError("ERROR: Invalid GOOGLE_CREDENTIALS JSON (Missing private_key).")
except json.JSONDecodeError as e:
    raise ValueError(f"ERROR: Failed to parse GOOGLE_CREDENTIALS JSON: {e}")

# Authenticate with Google Sheets
creds = Credentials.from_service_account_info(google_credentials, scopes=SCOPE)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

@cl.on_message
async def main(message: cl.Message):
    await cl.Message(content="Hello! How can I help you?").send()

cached_data = None

# For fetching data from the google sheet 
def get_machine_issues():
    global cached_data
    if cached_data is None:
        cached_data = sheet.get_all_records()
        if cached_data:
            print(f"✅ Column Names in Sheet: {cached_data[0].keys()}")
        else:
            print("⚠️ No data found in the sheet!")
    return cached_data


def preprocess_text(text):
    # Normalize text: lowercase and remove special characters
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text

# Function to extract Machine ID from user query
def extract_machine_id(query):
    machine_id = re.search(r'(mm\d{3})', query, re.IGNORECASE)
    if machine_id:
        return machine_id.group(0).upper() 
    return None

# Function to extract Machine Name from user query
def extract_machine_name(query):
    machine_names = ["cnc machine", "lathe machine", "milling machine", "grinding machine", "drilling machine"]
    for name in machine_names:
        if name in query.lower():
            return name
    return None

# Function to extract Technician Name from user query
def extract_technician_name(query):
    technician_names = ["rajesh", "suresh", "vikram", "gopal", "sanjay", "manoj", "anil"]
    for name in technician_names:
        if name in query.lower():
            return name
    return None

# Function to extract Issue from user query
def extract_issue(query):
    issues = ["bearing failure", "spindle overheating", "unexpected shutdown", "excessive vibration", "chatter marks"]
    for issue in issues:
        if issue in query.lower():
            return issue
    return None

# Function to get the latest record for a Machine ID
def get_latest_machine_info(machine_id):
    data = get_machine_issues()
    if not data:
        return None
    machine_records = [row for row in data if row.get("ID", "").upper() == machine_id.upper()]
    if not machine_records:
        return None
    latest_record = max(machine_records, key=lambda x: datetime.strptime(x.get("Date of Repair", ""), "%m/%d/%Y"))
    return latest_record

# Function to get specific column data for a Machine ID
def get_column_data(machine_id, column_name):
    data = get_machine_issues()
    if not data:
        return None
    machine_records = [row for row in data if row.get("ID", "").upper() == machine_id.upper()]
    if not machine_records:
        return None
    column_data = [row.get(column_name, "N/A") for row in machine_records]
    return column_data

# Function to get the most repeated issue(s) across all machines or for a specific machine
def get_most_repeated_issue(machine_id=None, machine_name=None):
    data = get_machine_issues()
    if not data:
        return None
    if machine_id:
        machine_records = [row for row in data if row.get("ID", "").upper() == machine_id.upper()]
    elif machine_name:
        machine_records = [row for row in data if row.get("Machine Name", "").lower() == machine_name.lower()]
    else:
        machine_records = data

    if not machine_records:
        return None

    # Count occurrences of each issue
    issue_counter = Counter(row.get("Issue Description", "N/A") for row in machine_records)
    if not issue_counter:
        return None

    # Find the most repeated issue(s)
    max_count = max(issue_counter.values())
    most_repeated_issues = [issue for issue, count in issue_counter.items() if count == max_count]

    # Get details for the most repeated issue(s)
    result = []
    for issue in most_repeated_issues:
        # Calculate total production loss and total repair time for the issue
        total_production_loss = sum(
            float(row.get("Production Loss (%)", "0").replace("%", ""))  # Remove % and convert to float
            for row in machine_records if row.get("Issue Description", "N/A") == issue
        )
        total_repair_time = sum(
            float(row.get("Time Taken (in hours)", 0))
            for row in machine_records if row.get("Issue Description", "N/A") == issue
        )

        issue_details = {
            "Issue": issue,
            "Affected Machines": list(set(row.get("Machine Name", "N/A") for row in machine_records if row.get("Issue Description", "N/A") == issue)),
            "Root Cause": list(set(row.get("Root Cause", "N/A") for row in machine_records if row.get("Issue Description", "N/A") == issue)),
            "Solution Applied": list(set(row.get("Solution Applied", "N/A") for row in machine_records if row.get("Issue Description", "N/A") == issue)),
            "Occurrence Count": issue_counter[issue],
            "Total Production Loss": total_production_loss,
            "Total Repair Time": total_repair_time
        }
        result.append(issue_details)

    return result

# Function to count machines by type
def count_machines_by_type(machine_type=None):
    data = get_machine_issues()
    if not data:
        return None

    if machine_type:
        # Count machines of the specified type
        machine_count = len([row for row in data if row.get("Machine Name", "").lower() == machine_type.lower()])
    else:
        # Count all machines
        machine_count = len(data)

    return machine_count

# Function to get machines repaired by a specific technician
def get_machines_repaired_by_technician(technician_name):
    data = get_machine_issues()
    if not data:
        return None

    # Filter records for the specified technician
    technician_records = [row for row in data if row.get("Technician Name", "").lower() == technician_name.lower()]
    if not technician_records:
        return None

    # Prepare the response
    result = []
    for row in technician_records:
        result.append({
            "Machine Name": row.get("Machine Name", "N/A"),
            "Issue Description": row.get("Issue Description", "N/A"),
            "Solution Applied": row.get("Solution Applied", "N/A")
        })

    return result
# Function to calculate total production loss and repair time for all machines, a specific machine type, or a specific machine ID
def calculate_total_production_loss_and_repair_time(machine_type=None, issue=None, machine_id=None):
    data = get_machine_issues()
    if not data:
        return None

    # Filter records based on the specified machine type, issue, or machine ID
    if machine_type:
        filtered_records = [row for row in data if row.get("Machine Name", "").lower() == machine_type.lower()]
    elif issue:
        filtered_records = [row for row in data if row.get("Issue Description", "").lower() == issue.lower()]
    elif machine_id:
        filtered_records = [row for row in data if row.get("ID", "").upper() == machine_id.upper()]
    else:
        filtered_records = data

    if not filtered_records:
        return None

    # Calculate total production loss and total repair time
    total_production_loss = 0.0
    total_repair_time = 0.0

    for row in filtered_records:
        # Handle production loss
        production_loss_str = str(row.get("Production Loss (%)", "0")).replace("%", "").strip()
        if production_loss_str:  # Check if the string is not empty
            try:
                total_production_loss += float(production_loss_str)
            except ValueError:
                print(f"Warning: Could not convert '{production_loss_str}' to float. Skipping this record.")

        # Handle repair time
        repair_time_str = str(row.get("Time Taken (in hours)", "0")).strip()
        if repair_time_str:  # Check if the string is not empty
            try:
                total_repair_time += float(repair_time_str)
            except ValueError:
                print(f"Warning: Could not convert '{repair_time_str}' to float. Skipping this record.")

    return {
        "Total Production Loss": total_production_loss,
        "Total Repair Time": total_repair_time
    }

# Function to get root cause, affected machines, and solutions for a specific issue
def get_issue_details(issue_description):
    data = get_machine_issues()
    if not data:
        return None

    # Filter records for the specified issue description
    issue_records = [row for row in data if row.get("Issue Description", "").lower() == issue_description.lower()]
    if not issue_records:
        return None

    # Prepare the response
    result = {
        "Issue": issue_description,
        "Affected Machines": list(set(row.get("Machine Name", "N/A") for row in issue_records)),
        "Root Cause": list(set(row.get("Root Cause", "N/A") for row in issue_records)),
        "Solution Applied": list(set(row.get("Solution Applied", "N/A") for row in issue_records)),
        "Occurrence Count": len(issue_records)
    }

    return result

# Main function to handle user queries
@cl.on_message
async def main(message):
    user_query = message.content
    print(f"🔍 Received Query: {user_query}")

    # Step 5: Handle queries related to the root cause of a specific issue
    if "root cause" in user_query.lower() or "cause of" in user_query.lower() or "what causes" in user_query.lower():
        # Extract issue description from the query
        issue_description = extract_issue(user_query)
        if not issue_description:
            await cl.Message(content="❌ Please provide a valid issue description.").send()
            return

        # Get issue details
        issue_details = get_issue_details(issue_description)
        if not issue_details:
            await cl.Message(content=f"❌ No records found for the issue: {issue_description}.").send()
            return

        # Prepare the response
        response = (
            f"🔧 Issue: {issue_details['Issue']}\n"
            f"🔧 Occurrence Count: {issue_details['Occurrence Count']}\n"
            f"🔧 Affected Machines: {', '.join(issue_details['Affected Machines'])}\n"
            f"🔧 Root Cause(s): {', '.join(issue_details['Root Cause'])}\n"
            f"🔧 Solution(s) Applied: {', '.join(issue_details['Solution Applied'])}"
        )

        await cl.Message(content=response).send()
        return

    # Step 4: Calculate total production loss and repair time
    if "production loss" in user_query.lower() or "hours taken" in user_query.lower():
        # Extract machine type, issue, or machine ID from the query
        machine_type = extract_machine_name(user_query)
        issue = extract_issue(user_query)
        machine_id = extract_machine_id(user_query)

        # Calculate total production loss and repair time
        result = calculate_total_production_loss_and_repair_time(machine_type, issue, machine_id)
        if not result:
            await cl.Message(content="❌ No data found for the specified query.").send()
            return

        # Prepare the response
        if machine_type:
            response = (
                f"🔧 Total Production Loss for {machine_type}: {result['Total Production Loss']}%\n"
                f"🔧 Total Repair Time for {machine_type}: {result['Total Repair Time']} hours"
            )
        elif issue:
            response = (
                f"🔧 Total Production Loss due to {issue}: {result['Total Production Loss']}%\n"
                f"🔧 Total Repair Time for {issue}: {result['Total Repair Time']} hours"
            )
        elif machine_id:
            response = (
                f"🔧 Total Production Loss for {machine_id}: {result['Total Production Loss']}%\n"
                f"🔧 Total Repair Time for {machine_id}: {result['Total Repair Time']} hours"
            )
        else:
            response = (
                f"🔧 Total Production Loss for all machines: {result['Total Production Loss']}%\n"
                f"🔧 Total Repair Time for all machines: {result['Total Repair Time']} hours"
            )

        await cl.Message(content=response).send()
        return

    # Step 3: Count machines by type or total machines
    if "count" in user_query.lower() or "number of" in user_query.lower() or "how many" in user_query.lower():
        # Extract machine type from the query
        machine_type = extract_machine_name(user_query)

        # Get the count of machines
        machine_count = count_machines_by_type(machine_type)
        if machine_count is None:
            await cl.Message(content="❌ No data found for the specified machine type.").send()
            return

        # Prepare the response
        if machine_type:
            response = f"Total number of {machine_type} machines: {machine_count}"
        else:
            response = f"Total number of machines: {machine_count}"

        await cl.Message(content=response).send()
        return

    # Step 3: Machines repaired by a specific technician
    if "repaired by" in user_query.lower() or "handled by" in user_query.lower():
        # Extract technician name from the query
        technician_name = extract_technician_name(user_query)
        if not technician_name:
            await cl.Message(content="❌ Please provide a valid technician name.").send()
            return

        # Get machines repaired by the technician
        machines_repaired = get_machines_repaired_by_technician(technician_name)
        if not machines_repaired:
            await cl.Message(content=f"❌ No machines repaired by {technician_name} found.").send()
            return

        # Prepare the response
        response = f"🔧 Machines repaired by {technician_name}:\n\n"
        for machine in machines_repaired:
            response += (
                f"**Machine Name:** {machine['Machine Name']}\n"
                f"**Issue Description:** {machine['Issue Description']}\n"
                f"**Solution Applied:** {machine['Solution Applied']}\n\n"
            )

        await cl.Message(content=response).send()
        return

    # Step 2: Most repeated issue(s)
    if "most repeated" in user_query.lower() or "most occured" in user_query.lower() or "repeated problem" in user_query.lower():
        # Extract Machine ID or Machine Name from the query
        machine_id = extract_machine_id(user_query)
        machine_name = extract_machine_name(user_query)

        # Get the most repeated issue(s)
        most_repeated_issues = get_most_repeated_issue(machine_id, machine_name)
        if not most_repeated_issues:
            await cl.Message(content="❌ No repeated issues found.").send()
            return

        # Prepare the response
        response = "🔧 Most Repeated Issue(s):\n\n"
        for issue in most_repeated_issues:
            response += (
                f"**Issue:** {issue['Issue']}\n"
                f"**Occurrence Count:** {issue['Occurrence Count']}\n"
                f"**Affected Machines:** {', '.join(issue['Affected Machines'])}\n"
                f"**Root Cause(s):** {', '.join(issue['Root Cause'])}\n"
                f"**Solution(s) Applied:** {', '.join(issue['Solution Applied'])}\n"
                f"**Total Production Loss:** {issue['Total Production Loss']}%\n"
                f"**Total Repair Time:** {issue['Total Repair Time']} hours\n\n"
            )

        await cl.Message(content=response).send()
        return

    # Step 1 functionality (unchanged)
    machine_id = extract_machine_id(user_query)
    if not machine_id:
        await cl.Message(content="❌ Please provide a valid Machine ID (e.g., MM001).").send()
        return

    # Fetch the latest record for the Machine ID
    latest_record = get_latest_machine_info(machine_id)
    if not latest_record:
        await cl.Message(content=f"❌ No records found for Machine ID: {machine_id}.").send()
        return

    # Check if the query is asking for specific column data
    if "technician" in user_query.lower() or "name of technician" in user_query.lower() or "who handled" in user_query.lower():
        # Get all technician names for the Machine ID
        technicians = get_column_data(machine_id, "Technician Name")
        if technicians:
            response = f"Technicians who handled {machine_id}:\n" + "\n".join(technicians)
        else:
            response = f"No technician records found for {machine_id}."
    elif "issue" in user_query.lower():
        # Get all issue descriptions for the Machine ID
        issues = get_column_data(machine_id, "Issue Description")
        if issues:
            response = f"Issues for {machine_id}:\n" + "\n".join(issues)
        else:
            response = f"No issue records found for {machine_id}."
    elif "root cause"  in user_query.lower():
        # Get all root causes for the Machine ID
        root_causes = get_column_data(machine_id, "Root Cause")
        if root_causes:
            response = f"Root causes for {machine_id}:\n" + "\n".join(root_causes)
        else:
            response = f"No root cause records found for {machine_id}."
    elif "solution" in user_query.lower():
        # Get all solutions applied for the Machine ID
        solutions = get_column_data(machine_id, "Solution Applied")
        if solutions:
            response = f"Solutions applied to {machine_id}:\n" + "\n".join(solutions)
        else:
            response = f"No solution records found for {machine_id}."
    elif "date" in user_query.lower():
        # Get all repair dates for the Machine ID
        dates = get_column_data(machine_id, "Date of Repair")
        if dates:
            response = f"Repair dates for {machine_id}:\n" + "\n".join(dates)
        else:
            response = f"No repair date records found for {machine_id}."
    elif "time" in user_query.lower():
        # Get all repair times for the Machine ID
        times = get_column_data(machine_id, "Time Taken (in hours)")
        if times:
            response = f"Repair times for {machine_id}:\n" + "\n".join(times)
        else:
            response = f"No repair time records found for {machine_id}."
    elif "production loss" in user_query.lower():
        # Get all production loss values for the Machine ID
        losses = get_column_data(machine_id, "Production Loss (%)")
        if losses:
            response = f"Production losses for {machine_id}:\n" + "\n".join(losses)
        else:
            response = f"No production loss records found for {machine_id}."
    else:
        # If no specific column is mentioned, return the latest record
        response = (
            f"**🔧 Latest Information for {machine_id}:**\n\n"
            f"**Machine Name:** {latest_record.get('Machine Name', 'N/A')}\n"
            f"**Issue Description:** {latest_record.get('Issue Description', 'N/A')}\n"
            f"**Root Cause:** {latest_record.get('Root Cause', 'N/A')}\n"
            f"**Solution Applied:** {latest_record.get('Solution Applied', 'N/A')}\n"
            f"**Technician Name:** {latest_record.get('Technician Name', 'N/A')}\n"
            f"**Date of Repair:** {latest_record.get('Date of Repair', 'N/A')}\n"
            f"**Time Taken (in hours):** {latest_record.get('Time Taken (in hours)', 'N/A')}\n"
            f"**Production Loss (%):** {latest_record.get('Production Loss (%)', 'N/A')}\n"
            f"**Additional Notes:** {latest_record.get('Additional Notes', 'N/A')}"
        )

    # Send the response back to the Chainlit UI
    await cl.Message(content=response).send()
