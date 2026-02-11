from pathlib import Path
import json
from model import Model, GeminiModel
from pydantic import BaseModel, Field
from typing import List

class CategorizationResponse(BaseModel):
    """Response model for note categorization"""
    categories: List[str] = Field(description="List of categories the note belongs to")
    unused: bool = Field(description="Whether the note should be marked as unused")
    ID: int = Field(description="The note ID")

class MergedCategorizationResponse(BaseModel):
    """Response model for merged note categories"""
    categories: List[str] = Field(description= "List of aggregated note catorgies")

PHASE_1_PROMPT = """
Analyze this note and identify ALL categories or topics it contains content for.

Guidelines:
- A single note can belong to MULTIPLE categories - list all that apply
- Each category should represent a distinct theme, topic, or purpose within the note
- Prefer actionable categories (e.g., "Books to Read") over abstract ones (e.g., "Literature")
- Use natural, human-readable category names
- Be specific enough to be useful, but general enough to group related notes
- If a note has 3 different topics, suggest all 3 categories
- If a note is too vague or lacks meaningful content (e.g., a lone phone number, a single word, incoherent text, just a filename for an image/recording, etc.), do not assign any categories and mark it as unused
- Always include the note ID in the JSON response

Examples:
- A note saying "Check out Dune, also remember to buy milk, and that story John told about Paris" 
  → ["Movies to Watch", "Shopping List", "Stories to Remember"]
- A note with movie recommendations AND book recommendations
  → ["Movies to Watch", "Books to Read"]
- A note with just "IMG_1234.jpg" or "847-555-0123"
  → Mark as unused

Output format: Return ONLY valid JSON in EXACTLY this structure:
{
  "categories": ["Category 1", "Category 2"],
  "unused": False
  "ID": 1
}

OR if the note should be marked as unused:
{
  "categories": [],
  "unused": True
  "ID": 3
}

Note content:
"""

PHASE_2_PROMPT = """
Review this list of categories from individual notes. Merge similar/overlapping categories into a clean, consolidated taxonomy.

Rules:
- Combine near-duplicates (e.g., "Movies to Watch" + "Films to See" + "Movies to Check Out" → "Movies to Watch")
- Keep categories at a consistent level of specificity across the taxonomy
- Prefer the most common or most natural phrasing when merging
- Preserve distinct categories even if they seem related (e.g., "Movies to Watch" and "Movie Reviews" are different)
- Aim for 15-30 final categories - merge aggressively to avoid fragmentation, but do not do so at the expense of detail
- Maintain the actionable nature of category names where applicable

Examples of good merges:
- "Books to Read" + "Reading List" + "Book Recommendations" → "Books to Read"
- "Gift Ideas" + "Present Ideas" + "Gift Ideas for Mom" → "Gift Ideas"
- "Work Notes" + "Work Meeting Notes" + "Office Notes" → "Work Notes"

Output format: Return ONLY a valid JSON array of category strings:
["Category 1", "Category 2", "Category 3"]

Category list to merge:
"""

PHASE_3_PROMPT = """

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
        response = model.invoke(PHASE_1_PROMPT, PAYLOAD, response_schema=CategorizationResponse)
        print(response)
        
        # Parse the structured JSON response
        response_data = CategorizationResponse.model_validate_json(response)
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
    response = model.invoke(PHASE_2_PROMPT, json.dumps(all_categories_list, indent=2), response_schema=MergedCategorizationResponse)
    response_data = MergedCategorizationResponse.model_validate_json(response)
    merged_category_list.append(response_data.model_dump())

    with open(output_file, "w", encoding="utf-8") as file:
            json.dump(merged_category_list, file, indent=2)


# Phase 3
def extract_details(model: Model):
    with open("notes/structured/all_categories.json", "r", encoding="utf-8") as file:
        all_categories = json.load(file)
    
    with open("notes/structured/merged_categories.json", "r", encoding="utf-8") as file:
        merged_categories = json.load(file)
        categories = merged_categories[0]["categories"]
        categories_text = " ".join(categories)

    with open("notes/structured/notes.json", "r", encoding="utf-8") as file:
        notes = json.load(file)

    # Create list of unused IDs
    unused_list = []
    for entry in all_categories:
        if entry["unused"] == True:
            unused_list.append(entry["ID"])

    for note in notes:
        # If note is unused in categorization step, do not send it
        if (note["ID"]) in unused_list:
            pass
        else:
            title = (note["title"])
            content = (note["content"])
            ID = (note["ID"])

            categories = merged_categories[0]["categories"]

            PAYLOAD = f"""
            Categories: {categories_text}

            Note title: {title}
            Note ID: {ID}
            Note content: {content}
            """
            return 




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
    testOutput(gemini_model)
    
    # The beauty: You could easily swap to a different model later!
    # different_model = OpenAIModel()  # hypothetical
    # extract_categories(different_model)  # works the same way!