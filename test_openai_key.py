import cohere

# Replace 'your-api-key' with your actual Cohere API key
api_key = "EFWoGl23ROfZ1nzMcOtI4CZzQL6KBX6lTH2eJfSX"

try:
    # Initialize Cohere client
    co = cohere.Client(api_key)

    # Test API by generating a simple response
    response = co.chat(message="Hello, can you tell me a joke?")

    # Print the response from Cohere API
    print("✅ API Key is working!")
    print("Response from Cohere:", response.text)

except Exception as e:
    print("❌ Error:", e)
    print("API Key is NOT working. Please check your key and try again.")