import os

# Retrieve values from environment variables
api_key = os.getenv("API_KEY")
google_credentials = os.getenv("GOOGLE_CREDENTIALS")

# Print or use them in your script
print("API Key:", api_key)
print("Google Credentials File:", google_credentials)