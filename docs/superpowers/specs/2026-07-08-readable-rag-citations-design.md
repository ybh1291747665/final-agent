# Readable RAG Citations Design

## Goal

Replace learner-visible chunk-id citations with readable source labels that prefer file name and page number, while preserving internal chunk IDs for citation extraction, hallucination checks, and chunk lookup.

## Behavior

- Main RAG answers should display citations such as `[software-engineering.pdf, page 12]` instead of `[abc12345]`.
- Evidence and validation panels should use the same readable labels.
- If a page number is unavailable, show the file name.
- If a file name is unavailable, fall back to document ID.
- If neither source metadata nor page number is available, fall back to a short chunk label.

## Design

The generation layer remains chunk-id based because existing grounding and hallucination guard code depends on chunk IDs. The UI layer builds a citation registry from retrieved chunks and document metadata, then replaces citation tokens only for display.

`chunk_registry` entries will include source metadata:

- `doc_id`
- `source_path`
- `file_name`
- `page_num`
- `citation_label`

The Streamlit UI will store the display-safe answer text in conversation history while preserving `citations` and `chunk_registry` for inspection.

## Tests

- Unit tests for readable citation label selection.
- Unit tests that answer text replacement hides chunk IDs.
- Existing UI evidence tests remain compatible.
