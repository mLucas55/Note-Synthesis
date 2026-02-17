from pathlib import Path
import json
from model import Model, GeminiModel
from pydantic import BaseModel, Field
from typing import List, Dict
import shutil


class Extraction(BaseModel):
    """Response model for extracted categories and content"""
    category: str = Field(description="The category name")
    content: str = Field(description="The extracted content relevant to this category")

class CategoryExtractionResponse(BaseModel):
    """Response model for extracted note categories and content"""
    note_id: str = Field(description="The note ID")
    extractions: List[Extraction] = Field(description="List of extracted categories and content")
    unused: bool = Field(description="Whether the note should be marked as unused")

class CategoryNormalization(BaseModel):
    """Response model for category mapping structure"""
    categories: Dict[str, List[str]] = Field(description="Mapping of final categories to their source categories that were merged into them")

PHASE_1_PROMPT = """
Analyze this note, identify the PRIMARY category or categories it belongs to, and extract the content that belongs to the category[s].

Category Guidelines:
- Focus on the MAIN purpose/theme of the note, not every micro-topic mentioned
- A note should typically belong to 1-3 categories maximum
- Only assign multiple categories if the note contains TRULY DISTINCT topics (e.g., a shopping list mixed with a movie recommendation)
- Prefer broad, actionable categories over hyper-specific ones
- Use natural, human-readable category names
- If a note is too vague or lacks meaningful content (e.g., a lone phone number, a single word, incoherent text, just a filename), mark it as unused

Examples:
GOOD:
- A note about a custom Ferrari → ["Car Observations"]
- A note saying "Check out Dune, also remember to buy milk, and that story John told" → ["Movies to Watch", "Shopping List", "Stories to Remember"]
- A career planning conversation → ["Career Planning"]

BAD - Over-fragmentation:
- A note about a custom Ferrari → ["Ferrari", "Car Customization", "Automotive Design", "Color Analysis", "Design Aesthetics"] (TOO MANY - just use "Car Observations")
- A philosophical thought → ["Philosophy", "Personal Musings", "Reflections", "Deep Thoughts"] (TOO MANY - just use "Personal Musings")

Extraction Guidelines:
- Extract each piece of content to its MOST RELEVANT category only
- Do not split a cohesive note into multiple categories unless it genuinely covers distinct topics
- Preserve the full context of the content - don't fragment a single thought
- If the entire note is about one topic, assign it to one category even if it mentions related concepts
- If the note contains nothing relevant to any category, return an empty extractions array

Examples:
GOOD extraction:
Note: "This Ferrari SF90 has a purple custom paint job with yellow accents"
→ Extract ONCE to "Car Observations" (not also to "Color Analysis", "Ferrari", "Design", etc.)

BAD extraction (over-fragmentation):
Note: "This Ferrari SF90 has a purple custom paint job with yellow accents"
→ Extract to "Ferrari", "Car Customization", "Color Analysis", "Design Aesthetics" (TOO FRAGMENTED)

Output format: Return ONLY valid JSON in this structure:
{
  "note_id": "note_123",
  "extractions": [
    {"category": "Category 1", "content": "Relevant content here..."},
    {"category": "Category 2", "content": "More relevant content..."}
  ],
  "unused": false
}

OR if the note should be marked as unused:
{
  "note_id": "note_123",
  "extractions": [],
  "unused": true
}
"""

PHASE_2_PROMPT = """
Review this list of categories from individual notes. Aggressively merge similar/overlapping categories into a clean, consolidated taxonomy.

Rules:
- **Merge aggressively** - When in doubt, combine rather than keep separate
- Combine near-duplicates (e.g., "Movies to Watch" + "Films to See" → "Movies to Watch")
- Combine related micro-categories into broader themes (e.g., "Ferrari" + "Car Customization" + "Automotive Design" → "Car Observations")
- Only keep categories separate if they represent FUNDAMENTALLY different purposes (e.g., "Movies to Watch" vs "Movie Reviews" vs "Movie Quotes")
- Typically aim for 8-15 final categories total - more than this suggests over-fragmentation
- Prefer the most natural/common phrasing as the normalized category name

Examples of aggressive merging:
- "Books to Read" + "Reading List" + "Book Recommendations" → "Books to Read"
- "Ferrari" + "Car Customization" + "Automotive Design" + "Automotive Observations" → "Car Observations"
- "Personal Musings" + "Reflections" + "Deep Thoughts" + "Random Thoughts" → "Personal Musings"
- "Career Planning" + "Job Search" + "Post-Graduation Employment" → "Career Planning"

Output format: Return ONLY a valid JSON object where:
- Keys are the normalized category names (the "canonical" version)
- Values are arrays of all original category names that map to this normalized category

Example output:
{
  "Books to Read": ["Books to Read", "Reading List", "Book Recommendations", "Books I Want"],
  "Car Observations": ["Ferrari", "Car Customization", "Automotive Design", "Automotive Observations", "Color and Material Analysis"],
  "Movie Quotes": ["Movie Quotes", "Film Quotes", "Quotes from Movies"]
}
"""

# Pre-processing
# OUTPUT: notes.json
def pre_process_notes():
    print("Pre-processing...")
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
    print("Complete ✅")

# Phase 1
# OUTPUT: all_categories.json
def extract_categories(model: Model):
    """
    Extract categories and content from notes
    
    Args:
        model: An object that implements the Model interface
    """
    print("Extracting...")
    # Load notes.json
    with open("notes/structured/notes.json", "r", encoding="utf-8") as file:
        notes = json.load(file)

    response_list = []
    output_file = Path(__file__).parent / "notes" / "structured" / "extractions.json"

    # Loop through each note
    for note in notes:
        Id = (note["ID"])
        title = (note["title"])
        content = (note["content"])
        
        PAYLOAD = f"""
        Note ID: {Id}
        Note title: {title}
        Note content: {content}
        """

        print(f"🛜 Invoking model for note {Id}...")
        response = model.invoke(PHASE_1_PROMPT, PAYLOAD, response_schema=CategoryExtractionResponse)
        
        # Parse the structured JSON response
        response_data = CategoryExtractionResponse.model_validate_json(response)
        response_list.append(response_data.model_dump())

    # Write final list to JSON file
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(response_list, file, indent=2)
    print("Complete ✅")

# Phase 2
# OUTPUT: merged_categories.json
def merge_categories(model: Model):
    print("Merging similar categories...")
    with open("notes/structured/extractions.json", "r", encoding="utf-8") as file:
        extractions = json.load(file)
    
    output_file = Path(__file__).parent / "notes" / "structured" / "merged_categories.json"
    merged_category_list = []

    # Extract only the categories field from each entry
    all_categories_list = []
    for note in extractions:
        if not note["unused"]:  # Skip unused notes
            for extraction in note["extractions"]:
                all_categories_list.append(extraction['category'])

    print(f"🛜 Invoking model...")
    response = model.invoke(PHASE_2_PROMPT, json.dumps(all_categories_list, indent=2), response_schema=CategoryNormalization)
    response_data = CategoryNormalization.model_validate_json(response)
    # Convert Pydantic model object to JSON
    merged_category_list = response_data.model_dump()

    with open(output_file, "w", encoding="utf-8") as file:
            #json.dump(merged_category_list, file, indent=2)
            json.dump(merged_category_list, file, indent=2)
    print("Complete ✅")

# Phase 3
# OUTPUT: category_notes.json (organized by normalized category)
def build_category_notes():
    """
    Build an index of content organized by normalized categories.
    """
    print("Mapping content...")
    # Load the extractions from phase 1
    with open("notes/structured/extractions.json", "r", encoding="utf-8") as file:
        extractions = json.load(file)
    
    # Load the category mapping from phase 2
    with open("notes/structured/merged_categories.json", "r", encoding="utf-8") as file:
        merged_data = json.load(file)
    
    output_file = Path(__file__).parent / "notes" / "structured" / "category_notes.json"
    
    # Step 1: Build a lookup for sub category -> normalized category
    category_mapping = {}
    categories_dict = merged_data["categories"]
    
    # Loop through normalized categories in JSON file
    for normalized_name in categories_dict:
        # Collect all sub categories for a normalized category 
        sub_categories = categories_dict[normalized_name]
        # Loop through all sub categories
        for sub_name in sub_categories:
            # Map sub category name to normalized (key) category
            category_mapping[sub_name] = normalized_name
    
    # Step 2: Go through each note and organize content by normalized category
    organized_notes = {}
    
    for note in extractions:
        note_id = note["note_id"]
        is_unused = note["unused"]
        
        # Skip if this note was marked unused
        if is_unused:
            continue
        
        # Look at each extraction in this note
        extractions_list = note["extractions"]
        for extraction in extractions_list:
            raw_cat = extraction["category"]
            content = extraction["content"]
            
            # Find the normalized category name
            if raw_cat in category_mapping:
                # Lookup raw category in normalized category map
                normalized_cat = category_mapping[raw_cat]
            else:
                normalized_cat = raw_cat
            
            # Create the normalized category in output if it doesn't exist
            if normalized_cat not in organized_notes:
                organized_notes[normalized_cat] = []
            
            # Add note's content to the category
            organized_notes[normalized_cat].append({
                "note_id": note_id,
                "content": content
            })
    
    # Step 3: Write to file
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(organized_notes, file, indent=2)
    
    print(f"Mapping finished! Created index with {len(organized_notes)} categories")
    print("Complete ✅")


if __name__ == "__main__":
    gemini_model = GeminiModel()
    
    print("\nNote Synthesis")
    print("="*50)
    print("1. Run full pipeline (all steps 1-4)")
    print("2. Run individual step")
    print("="*50)
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        print("\nRunning full pipeline...\n")
        print("STEP 1: Pre-processing")
        pre_process_notes()
        
        print("\nSTEP 2: Category Extraction")
        extract_categories(gemini_model)
        
        print("\nSTEP 3: Normalize Categories")
        merge_categories(gemini_model)
        
        print("\nSTEP 4: Map Content to Categories")
        build_category_notes()
        
        print("\n✅ Pipeline complete!")
        
    elif choice == "2":
        print("\n1. Pre-process notes")
        print("2. Extract categories")
        print("3. Normalize categories")
        print("4. Map content to categories")
        
        step = input("\nEnter step (1-4): ").strip()
        
        if step == "1":
            pre_process_notes()
        elif step == "2":
            extract_categories(gemini_model)
        elif step == "3":
            merge_categories(gemini_model)
        elif step == "4":
            build_category_notes()
        else:
            print("Invalid step")
    else:
        print("Invalid choice")