# PDF Figure Assets Feature

This document describes the figure assets feature that allows extracting images from PDFs, storing them with teacher notes, and retrieving them during Q&A queries.

## Overview

The figure assets feature enables:
1. **Image Extraction**: Automatically extract all images from PDF pages during ingestion
2. **Asset Storage**: Store image metadata (page number, bounding box, file path) in SQL database
3. **Teacher Notes**: Allow teachers to add notes to images
4. **Vector Search**: Embed teacher notes and make them searchable via ChromaDB
5. **Q&A Integration**: Include relevant figures in Q&A responses

## Architecture

### Components

1. **Figure Extractor** (`app/core/pdf_vector_db/figure_extractor.py`)
   - Extracts images from PDF pages using PyMuPDF
   - Saves images as PNG files
   - Returns asset metadata

2. **Asset Manager** (`app/core/storage/asset_manager.py`)
   - Manages Asset database records
   - CRUD operations for assets

3. **Assets API** (`app/api/assets_api.py`)
   - FastAPI endpoints for managing assets
   - Endpoints for adding teacher notes and retrieving assets

4. **Database Model** (`app/core/storage/models.py`)
   - `Asset` model with fields: asset_id, doc_id, page_no, bbox, type, image_path, teacher_note

## Usage

### 1. PDF Ingestion with Image Extraction

When ingesting a PDF, images are automatically extracted:

```python
from app.thread.pdf_vector_db_thread import PDFVectorizationThread

thread = PDFVectorizationThread(
    pdf_path="path/to/document.pdf",
    vector_store_path="path/to/vector_db",
    extract_figures=True  # Default: True
)
thread.start()
```

Images are saved to: `AppData/assets/{doc_id}/page_{page_no}/img_{idx}.png`

### 2. Adding Teacher Notes via API

Start the API server:

```bash
cd app/api
python assets_api.py
# Server runs on http://0.0.0.0:8000
```

Add a teacher note to an asset:

```bash
curl -X POST "http://localhost:8000/assets/{asset_id}/note" \
  -H "Content-Type: application/json" \
  -d '{"teacher_note": "This diagram shows the process flow"}'
```

Example:
```bash
curl -X POST "http://localhost:8000/assets/document_page12_img0/note" \
  -H "Content-Type: application/json" \
  -d '{"teacher_note": "This diagram illustrates the neural network architecture"}'
```

### 3. Retrieving Assets for a Document

```bash
curl "http://localhost:8000/documents/{doc_id}/assets"
```

Example:
```bash
curl "http://localhost:8000/documents/my_document/assets"
```

Response:
```json
[
  {
    "asset_id": "my_document_page12_img0",
    "doc_id": "my_document",
    "page_no": 12,
    "bbox": [100.0, 200.0, 400.0, 500.0],
    "type": "figure",
    "image_path": "/path/to/assets/my_document/page_12/img_0.png",
    "teacher_note": "This diagram illustrates the neural network architecture",
    "created_at": "2025-01-27T10:00:00",
    "updated_at": "2025-01-27T10:05:00"
  }
]
```

### 4. Q&A with Figure Notes

When asking questions, the system automatically:
1. Searches both text pages and figure notes in ChromaDB
2. Includes relevant figures in the response
3. Adds figure information to the context prompt

Example question: "What does the neural network diagram show?"

The system will:
- Find relevant text pages
- Find relevant figure notes (if any match the query)
- Include both in the LLM context
- Return answer with figure references

## Database Schema

### Asset Table

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id VARCHAR(100) UNIQUE NOT NULL,
    doc_id VARCHAR(200) NOT NULL,
    page_no INTEGER NOT NULL,
    bbox JSON NOT NULL,  -- [x0, y0, x1, y1]
    type VARCHAR(50) DEFAULT 'figure',
    image_path VARCHAR(500) NOT NULL,
    teacher_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_asset_doc_id ON assets(doc_id);
CREATE INDEX idx_asset_page_no ON assets(page_no);
CREATE INDEX idx_asset_doc_page ON assets(doc_id, page_no);
```

## Vector Database Integration

Teacher notes are embedded and stored in ChromaDB (same collection as PDF pages):

- **ID Format**: `asset:{asset_id}`
- **Document**: Teacher note text
- **Metadata**:
  ```json
  {
    "doc_id": "document_name",
    "page_no": 12,
    "asset_id": "document_page12_img0",
    "type": "figure",
    "source": "asset_note"
  }
  ```

## Important Notes

1. **No OCR/Auto-captioning**: Images are extracted but not automatically analyzed. Only teacher notes are embedded.

2. **Empty Notes**: Assets without teacher notes are NOT embedded and will NOT appear in search results.

3. **Image Storage**: Images are stored as PNG files in `AppData/assets/` directory.

4. **Bounding Box**: Bbox format is `[x0, y0, x1, y1]` in PDF coordinates.

5. **Asset ID Format**: `{doc_id}_page{page_no}_img{img_idx}`

## Example Workflow

1. **Ingest PDF**:
   ```python
   # PDF is processed, images extracted automatically
   ```

2. **Teacher Reviews PDF**:
   - Views extracted images
   - Adds notes via API or UI

3. **Student Asks Question**:
   - System searches text + figure notes
   - Returns answer with relevant figures

4. **Response Includes**:
   - Text pages with relevant content
   - Figure notes that match the query
   - Image paths for display

## Troubleshooting

### Images Not Extracted
- Check if PyMuPDF is installed: `pip install pymupdf`
- Verify PDF contains images (some PDFs embed images as objects)

### Teacher Notes Not Appearing in Search
- Ensure teacher note was added via API
- Check that note is not empty
- Verify embedding was generated (check logs)

### API Not Starting
- Install FastAPI and uvicorn: `pip install fastapi uvicorn`
- Check port 8000 is available

## Future Enhancements

- UI for adding teacher notes (currently API-only)
- Batch note import
- Image preview in Q&A responses
- Support for other asset types (tables, formulas)
