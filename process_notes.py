from google import genai
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()
API_KEY = os.environ.get('API_KEY')

notes_inbox = Path(__file__).parent / "notes" / "inbox"

def process_notes():
    notes = []
    for note_file in notes_inbox.glob("*.md"):
        notes.append(note_file)

    return notes

def call_llm():
    # The client gets the API key from the environment variable `GEMINI_API_KEY`.
    client = genai.Client(api_key=API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents="Explain how AI works in a few words"
    )
    print(response.text)

note_array = process_notes()

for note in note_array:
    content = note.read_text(encoding="utf-8")
    print(content)