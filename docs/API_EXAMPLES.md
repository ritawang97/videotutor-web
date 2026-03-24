# API Usage Examples

This document provides example curl commands for using the Assets API and Q&A API.

## Prerequisites

1. Start the API servers:

```bash
# Terminal 1: Assets API
cd app/api
python assets_api.py
# Server runs on http://0.0.0.0:8000

# Terminal 2: Q&A API (optional, for Q&A queries)
python qa_api.py
# Server runs on http://0.0.0.0:8001
```

## Assets API Examples

### 1. List Assets for a Document

Get all assets (images) extracted from a specific PDF document:

```bash
curl "http://localhost:8000/documents/my_document/assets"
```

**Response:**
```json
[
  {
    "asset_id": "my_document_page12_img0",
    "doc_id": "my_document",
    "page_no": 12,
    "bbox": [100.0, 200.0, 400.0, 500.0],
    "type": "figure",
    "image_path": "/path/to/AppData/assets/my_document/page_12/img_0.png",
    "teacher_note": null,
    "created_at": "2025-01-27T10:00:00",
    "updated_at": "2025-01-27T10:00:00"
  },
  {
    "asset_id": "my_document_page12_img1",
    "doc_id": "my_document",
    "page_no": 12,
    "bbox": [500.0, 200.0, 800.0, 500.0],
    "type": "figure",
    "image_path": "/path/to/AppData/assets/my_document/page_12/img_1.png",
    "teacher_note": null,
    "created_at": "2025-01-27T10:00:00",
    "updated_at": "2025-01-27T10:00:00"
  }
]
```

### 2. Add Teacher Note to an Asset

Add or update a teacher note for a specific image:

```bash
curl -X POST "http://localhost:8000/assets/my_document_page12_img0/note" \
  -H "Content-Type: application/json" \
  -d '{
    "teacher_note": "This diagram illustrates the neural network architecture with three hidden layers."
  }'
```

**Response:**
```json
{
  "asset_id": "my_document_page12_img0",
  "doc_id": "my_document",
  "page_no": 12,
  "bbox": [100.0, 200.0, 400.0, 500.0],
  "type": "figure",
  "image_path": "/path/to/AppData/assets/my_document/page_12/img_0.png",
  "teacher_note": "This diagram illustrates the neural network architecture with three hidden layers.",
  "created_at": "2025-01-27T10:00:00",
  "updated_at": "2025-01-27T10:05:00"
}
```

**Note:** After adding a teacher note, the note is automatically embedded and added to the vector database for search.

### 3. Update Teacher Note

You can update an existing note by calling the same endpoint with new content:

```bash
curl -X POST "http://localhost:8000/assets/my_document_page12_img0/note" \
  -H "Content-Type: application/json" \
  -d '{
    "teacher_note": "Updated: This diagram shows a deep neural network with ReLU activation functions."
  }'
```

### 4. Health Check

Check if the API is running:

```bash
curl "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "ok"
}
```

## Q&A API Examples

### 1. Ask a Question (with Figure Notes)

Query the system with a question. The response will include relevant text pages AND figure notes:

```bash
curl -X POST "http://localhost:8001/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does the neural network diagram show?",
    "top_k": 5
  }'
```

**Response:**
```json
{
  "answer": "Based on the retrieved documents:\n\n[1] my_document - Page 12:\nThe neural network consists of...\n\nRelevant Figures:\n- Page 12: This diagram illustrates the neural network architecture with three hidden layers. (asset_id=my_document_page12_img0)\n",
  "sources": [
    {
      "pdf_name": "my_document",
      "page": 12,
      "content": "The neural network consists of multiple layers...",
      "distance": 0.15
    }
  ],
  "figures": [
    {
      "asset_id": "my_document_page12_img0",
      "page_no": 12,
      "image_path": "/path/to/AppData/assets/my_document/page_12/img_0.png",
      "teacher_note": "This diagram illustrates the neural network architecture with three hidden layers."
    }
  ]
}
```

### 2. Query with Custom Top-K

Specify how many results to return:

```bash
curl -X POST "http://localhost:8001/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain the process flow",
    "top_k": 10
  }'
```

## Complete Workflow Example

### Step 1: Ingest PDF (via Desktop App)

The PDF is ingested through the desktop application UI. Images are automatically extracted.

### Step 2: List Extracted Assets

```bash
curl "http://localhost:8000/documents/my_document/assets"
```

### Step 3: Add Teacher Notes

```bash
# Add note to first image
curl -X POST "http://localhost:8000/assets/my_document_page12_img0/note" \
  -H "Content-Type: application/json" \
  -d '{"teacher_note": "Process flow diagram showing input to output transformation"}'

# Add note to second image
curl -X POST "http://localhost:8000/assets/my_document_page15_img0/note" \
  -H "Content-Type: application/json" \
  -d '{"teacher_note": "Architecture diagram of the system components"}'
```

### Step 4: Query with Question

```bash
curl -X POST "http://localhost:8001/qa" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What diagrams are available in this document?",
    "top_k": 5
  }'
```

The response will include:
- Relevant text pages
- Relevant figure notes (if they match the query)
- Image paths for display

## Error Handling

### Asset Not Found

```bash
curl -X POST "http://localhost:8000/assets/nonexistent_asset/note" \
  -H "Content-Type: application/json" \
  -d '{"teacher_note": "Test"}'
```

**Response (404):**
```json
{
  "detail": "Asset nonexistent_asset not found"
}
```

### Invalid Request Body

```bash
curl -X POST "http://localhost:8000/assets/my_document_page12_img0/note" \
  -H "Content-Type: application/json" \
  -d '{"wrong_field": "value"}'
```

**Response (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "teacher_note"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Notes

1. **Asset IDs**: Format is `{doc_id}_page{page_no}_img{img_idx}`. The doc_id is typically the PDF filename without extension.

2. **Empty Notes**: Assets without teacher notes are NOT embedded and will NOT appear in search results.

3. **Vector Database**: Teacher notes are automatically embedded and stored in ChromaDB when added via the API.

4. **Image Paths**: Image paths are relative to the application's AppData directory.

5. **Bounding Box**: The bbox field contains `[x0, y0, x1, y1]` coordinates in PDF space.
