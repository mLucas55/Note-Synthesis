from google import genai
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.environ.get('API_KEY')

def call_llm():
    # The client gets the API key from the environment variable `GEMINI_API_KEY`.
    client = genai.Client(api_key=API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents="Explain how AI works in a few words"
    )
    print(response.text)