# Note Synthesis

https://ai.google.dev/gemini-api/docs/gemini-3



## INGESTION:

Notes should be ingested in batches

For each note individually:
1. Send note → LLM
2. Ask: "Suggest 1-5 categories/topics this note belongs to for example (movies to watch, interesting facts, things to check out, memories, stories,)"
3. Collect all suggested categories

Next:
1. Aggregate all suggested categories from Phase 1
2. Send aggregated list → LLM
3. Ask: "Merge similar categories and create final taxonomy"

Next, for each note:
1. Send note + final category list → LLM
2. Ask: "Assign this note to a category & extract the key details to start building a library of knowledge in this category"

## Store data
- Data will be stored in SQL light, API endpoints will exist in backend to query this data.


## How to view data:

- General topics and list modified version notes contents in them (IE combine multiple movie watchlists into one list)

- Attach the actual note that sourced the data to the category as well.
    - Will need to include some sort of metadata/tag to track this