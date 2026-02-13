from pathlib import Path
import json
from model import Model, GeminiModel
from pydantic import BaseModel, Field
from typing import List

class CategoryExtractionResponse(BaseModel):
    """Response model for extracted note categories"""
    categories: List[str] = Field(description="List of categories the note belongs to")
    unused: bool = Field(description="Whether the note should be marked as unused")
    ID: int = Field(description="The note ID")

class MergedCategoryResponse(BaseModel):
    """Response model for merged note categories"""
    categories: List[str] = Field(description= "List of aggregated note catorgies")

class CategoryExtraction(BaseModel):
    """Model for individual category extraction"""
    category: str = Field(description="The category name")
    content: str = Field(description="The extracted content relevant to this category")

class NoteCategorizationResponse(BaseModel):
    """Response model for categorized notes"""
    note_id: str = Field(description="The ID of the note being categorized")
    extractions: List[CategoryExtraction] = Field(description="List of category extractions from the note")

PHASE_1_PROMPT = """
Analyze this note and identify the PRIMARY category or categories it belongs to.

Guidelines:
- Focus on the MAIN purpose/theme of the note, not every micro-topic mentioned
- A note should typically belong to 1-3 categories maximum
- Only assign multiple categories if the note contains TRULY DISTINCT topics (e.g., a shopping list mixed with a movie recommendation)
- Prefer broad, actionable categories over hyper-specific ones
- Use natural, human-readable category names
- If a note is too vague or lacks meaningful content (e.g., a lone phone number, a single word, incoherent text, just a filename), mark it as unused

Examples:
GOOD - Appropriate category assignment:
- A note about a custom Ferrari → ["Car Observations"]
- A note saying "Check out Dune, also remember to buy milk, and that story John told" → ["Movies to Watch", "Shopping List", "Stories to Remember"]
- A career planning conversation → ["Career Planning"]

BAD - Over-fragmentation:
- A note about a custom Ferrari → ["Ferrari", "Car Customization", "Automotive Design", "Color Analysis", "Design Aesthetics"] (TOO MANY - just use "Car Observations")
- A philosophical thought → ["Philosophy", "Personal Musings", "Reflections", "Deep Thoughts"] (TOO MANY - just use "Personal Musings")

Output format: Return ONLY valid JSON in this structure:
{
  "categories": ["Category 1", "Category 2"],
  "unused": false
}

OR if the note should be marked as unused:
{
  "categories": [],
  "unused": true
}
"""

PHASE_2_PROMPT = """
Review this list of categories from individual notes. Aggressively merge similar/overlapping categories into a clean, consolidated taxonomy.

Rules:
- **Merge aggressively** - When in doubt, combine rather than keep separate
- Combine near-duplicates (e.g., "Movies to Watch" + "Films to See" → "Movies to Watch")
- Combine related micro-categories into broader themes (e.g., "Ferrari" + "Car Customization" + "Automotive Design" + "Automotive Observations" + "Color and Material Analysis" → "Car Observations")
- Only keep categories separate if they represent FUNDAMENTALLY different purposes (e.g., "Movies to Watch" vs "Movie Reviews I Wrote" vs "Movie Quotes")
- Typically aim for 8-15 final categories total - more than this suggests over-fragmentation
- Prefer the most natural/common phrasing when merging

Examples of aggressive merging:
- "Books to Read" + "Reading List" + "Book Recommendations" + "Books I Want" → "Books to Read"
- "Ferrari" + "Car Customization" + "Automotive Design" + "Automotive Observations" + "Design Aesthetics" + "Color and Material Analysis" → "Car Observations"
- "Personal Musings" + "Reflections on Detail" + "Deep Thoughts" + "Random Thoughts" → "Personal Musings"
- "Career Planning" + "Job Search" + "Post-Graduation Employment" → "Career Planning"

Output format: Return ONLY a valid JSON array of category strings:
["Category 1", "Category 2", "Category 3"]

Category list to merge:
"""

PHASE_3_PROMPT = """
You are analyzing a note to extract content relevant to specific categories.

Task:
1. Review the note against the provided category list
2. Identify which category (or categories) this note PRIMARILY belongs to
3. Extract the content ONCE per category - do not duplicate content across multiple categories
4. If a note clearly belongs to just ONE category, only extract it to that one category

Guidelines:
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
  "note_id": "the_note_id_here",
  "extractions": [
    {
      "category": "Category Name",
      "content": "The full relevant content from the note"
    }
  ]
}

Example JSON for multiple categories:
{
  "note_id": "note_456",
  "extractions": [
    {
      "category": "Movies to Watch",
      "content": "Blade Runner 2049 - heard it's visually stunning"
    },
    {
      "category": "Quotes",
      "content": "one giant leap for mankind"
    },
    {
      "category": "Gift Ideas",
      "content": "sci-fi art book for Dad's birthday"
    }
  ]
}
"""

PHASE_4_PROMPT = """
You are creating a consolidated note for the category: "{category_name}"

You have been provided with multiple text excerpts from different source notes that all relate to this category. Your task is to:

1. Synthesize all the excerpts into a single, well-organized note
2. Preserve all unique information - don't drop any items or details
3. Remove redundancies if the same item appears multiple times
4. Organize the content in a logical, readable way
5. Maintain the original intent and wording where important
6. Add citations showing which source notes contributed to each piece of information

Guidelines:
- Keep the tone natural and useful (this is a personal note, not a formal document)
- Group related items together
- Use formatting (lists, sections) if it improves readability
- Preserve specific details (dates, names, context) from the original notes

Output format: Return ONLY valid JSON:
{
  "category": "{category_name}",
  "synthesized_note": "The complete, synthesized note body in markdown format",
  "source_notes": ["note_id_1", "note_id_2", "note_id_3"],
  "item_count": 5
}

Source excerpts:
{excerpts_json}
"""
# Phase 1
# OUTPUT: all_categories.json
def extract_categories(model: Model):
    """
    Extract categories from notes
    
    Args:
        model: An object that implements the Model interface
    """
    # Load notes.json
    with open("notes/structured/notes.json", "r", encoding="utf-8") as file:
        notes = json.load(file)

    response_list = []
    output_file = Path(__file__).parent / "notes" / "structured" / "all_categories.json"

    # Loop through each note
    for note in notes:
        title = (note["title"])
        content = (note["content"])
        ID = (note["ID"])

        PAYLOAD = f"""
        Note title: {title}
        Note ID: {ID}
        Note content: {content}
        """

        print(f"Invoking model for note {ID}")
        response = model.invoke(PHASE_1_PROMPT, PAYLOAD, response_schema=CategoryExtractionResponse)
        print(response)
        
        # Parse the structured JSON response
        response_data = CategoryExtractionResponse.model_validate_json(response)
        response_list.append(response_data.model_dump())

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(response_list, file, indent=2)

# Phase 2
# OUTPUT: merged_categories.json
def merge_categories(model: Model):
    with open("notes/structured/all_categories.json", "r", encoding="utf-8") as file:
        all_categories = json.load(file)
    
    output_file = Path(__file__).parent / "notes" / "structured" / "merged_categories.json"
    merged_category_list = []

    # Extract only the categories field from each entry
    all_categories_list = []
    for entry in all_categories:
        if not entry["unused"]:  # Skip unused notes
            all_categories_list.extend(entry["categories"])
    
    # Convert to string for the model
    response = model.invoke(PHASE_2_PROMPT, json.dumps(all_categories_list, indent=2), response_schema=MergedCategoryResponse)
    response_data = MergedCategoryResponse.model_validate_json(response)
    merged_category_list.append(response_data.model_dump())

    with open(output_file, "w", encoding="utf-8") as file:
            json.dump(merged_category_list, file, indent=2)


# Phase 3
# OUTPUT: extractions.json
def extract_details(model: Model):
    with open("notes/structured/all_categories.json", "r", encoding="utf-8") as file:
        all_categories = json.load(file)
    
    with open("notes/structured/merged_categories.json", "r", encoding="utf-8") as file:
        merged_categories = json.load(file)
        categories = merged_categories[0]["categories"]
        categories_text = ", ".join(categories)

    with open("notes/structured/notes.json", "r", encoding="utf-8") as file:
        notes = json.load(file)

    output_file = Path(__file__).parent / "notes" / "structured" / "extractions.json"

    # Create list of unused IDs
    unused_list = []
    for entry in all_categories:
        if entry["unused"] == True:
            unused_list.append(entry["ID"])

    # Main logic -> Sending notes + categories to LLM
    response_list = []
    for note in notes:
        # If note is unused in categorization step, do not send it
        if (note["ID"]) in unused_list:
            pass
        else:
            title = (note["title"])
            content = (note["content"])
            ID = (note["ID"])

            PAYLOAD = f"""
            List of available categories: {categories_text}

            Note title: {title}
            Note ID: {ID}
            Note content: {content}
            """

            print(f"🛜 Invoking model for note: {ID}")
            response = model.invoke(PHASE_3_PROMPT, PAYLOAD, response_schema=NoteCategorizationResponse)
            
            # Parse the structured JSON response
            response_data = NoteCategorizationResponse.model_validate_json(response)
            response_list.append(response_data.model_dump())

            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(response_list, file, indent=2) 

# Phase 4
# OUTPUT: final_taxonomy.json
def generate_notes(mode: Model):
    with open("notes/structured/merged_categories.json", "r", encoding="utf-8") as file:
        merged_categories = json.load(file)
        categories = merged_categories[0]["categories"]
    
    with open("notes/structured/extractions.json", "r", encoding="utf-8") as file:
        extractions = json.load(file)

    
    
    pass

def testOutput(model: Model):
    with open("notes/structured/merged_categories.json", "r", encoding="utf-8") as file:
        merged_categories = json.load(file)

    categories = merged_categories[0]["categories"]
    categories_text = ", ".join(categories)


    print(categories_text)
    #response = model.invoke("Return whatever you were provided, identically. No changes", categories_text)

    #print(response)


# Example usage:
if __name__ == "__main__":
    # Create an instance of your model
    gemini_model = GeminiModel()
    
    # Pass it to your function

    #extract_categories(gemini_model)
    #merge_categories(gemini_model)
    extract_details(gemini_model)
    
    # The beauty: You could easily swap to a different model later!
    # different_model = OpenAIModel()  # hypothetical
    # extract_categories(different_model)  # works the same way!