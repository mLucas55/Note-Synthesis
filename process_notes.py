from pathlib import Path
import json
import shutil

def pre_process_notes():
    notes_inbox = Path(__file__).parent / "notes" / "inbox"
    notes_processed = Path(__file__).parent / "notes" / "processed"
    output_file = Path(__file__).parent / "notes" / "structured" / "notes.json"

    # Ingest all raw notes from inbox directory -> write their data to array -> move to processed
    notes_array = []
    for i, note_file in enumerate(notes_inbox.glob("*.md")):
        notes_array.append({
            "title": note_file.name,
            "content": note_file.read_text(encoding="utf-8"),
            "ID": i
        })
        shutil.move(note_file, notes_processed)

    # Write all ingested notes to notes.json file
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(notes_array, file, indent=2)

pre_process_notes()