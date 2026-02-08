from pathlib import Path
import json
import shutil



def process_notes():
    notes_inbox = Path(__file__).parent / "notes" / "inbox"
    notes_processed = Path(__file__).parent / "notes" / "processed"

    notes_array = []
    for note_file in notes_inbox.glob("*.md"):
        notes_array.append({
            "title": note_file.name,
            "content": note_file.read_text(encoding="utf-8")
        })
        shutil.move(note_file, notes_processed)

    output_file = Path(__file__).parent / "notes" / "notes.json"
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(notes_array, file, indent=2)

process_notes()