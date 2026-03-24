# PDF Figure Assets Management System

## 1. Overview

This document describes the PDF Figure Assets Management System, a comprehensive solution for extracting, managing, and utilizing images from PDF documents in an educational context. The system enables teachers to annotate extracted figures with educational notes, which are then integrated into a Retrieval-Augmented Generation (RAG) system for enhanced question-answering capabilities.

## 2. System Architecture

### 2.1 Core Components

The system consists of the following key components:

1. **Figure Extractor Module** (`app/core/pdf_vector_db/figure_extractor.py`)
   - Extracts images from PDF pages using PyMuPDF
   - Filters meaningless images (solid colors, too small, unusual shapes)
   - Saves images to organized directory structure

2. **Asset Manager** (`app/core/storage/asset_manager.py`)
   - Manages CRUD operations for asset records
   - Handles database persistence
   - Provides query interfaces

3. **Database Schema** (`app/core/storage/models.py`)
   - `Asset` table with fields: `asset_id`, `doc_id`, `page_no`, `bbox`, `type`, `image_path`, `teacher_note`, `created_at`, `updated_at`

4. **API Layer** (`app/api/assets_api.py`)
   - RESTful endpoints for asset management
   - Integration with embedding generation

5. **UI Interface** (`app/view/pdf_vector_db_interface.py`)
   - Visual asset management interface
   - Image preview and annotation tools
   - Batch operations support

### 2.2 Data Flow

```
PDF Document
    ↓
[Figure Extractor] → Extract Images → Filter Meaningless Images
    ↓
[File System] → Save to assets/{doc_id}/page_{page_no}/img_{idx}.png
    ↓
[Asset Manager] → Create Database Records
    ↓
[Teacher UI] → Add Teacher Notes
    ↓
[Embedding Generator] → Generate Embeddings for Notes
    ↓
[ChromaDB] → Store Vector Embeddings
    ↓
[RAG System] → Retrieve Relevant Figures in Q&A
```

## 3. Key Features

### 3.1 Automatic Image Extraction

When a PDF is imported into the vector database system, the system automatically:

1. **Scans each page** for embedded images using PyMuPDF
2. **Extracts image data** preserving original quality
3. **Organizes images** into a hierarchical directory structure:
   ```
   assets/
   └── {doc_id}/
       └── page_{page_no}/
           ├── img_0.png
           ├── img_1.png
           └── ...
   ```
4. **Stores metadata** in SQLite database with page numbers and bounding boxes

### 3.2 Intelligent Image Filtering

To ensure only meaningful images are stored, the system implements a multi-criteria filtering mechanism:

#### Filtering Criteria:

1. **Size Filtering**
   - Minimum dimensions: 50×50 pixels
   - Filters out decorative elements and icons

2. **Aspect Ratio Filtering**
   - Maximum aspect ratio: 20:1
   - Filters out extremely elongated shapes (likely decorative lines)

3. **Color Complexity Analysis**
   - Minimum unique colors: 10
   - Maximum dominant color ratio: 95%
   - Uses PIL (Pillow) for color analysis

4. **Solid Color Detection**
   - Checks average brightness and standard deviation
   - Filters pure white/black images with low variance (< 10)

#### Implementation Details:

```python
def is_meaningful_image(image_bytes: bytes, 
                       min_width: int = 50, 
                       min_height: int = 50, 
                       max_color_ratio: float = 0.95, 
                       min_unique_colors: int = 10) -> bool:
    """
    Analyzes image characteristics to determine if it's meaningful.
    Returns False for solid colors, too small, or unusual shapes.
    """
    # Image analysis using PIL
    # - Size validation
    # - Aspect ratio check
    # - Color diversity analysis
    # - Brightness variance check
```

### 3.3 Teacher Annotation System

Teachers can add educational notes to extracted figures:

1. **Visual Selection**: Browse extracted images by document and page
2. **Image Preview**: View images before annotation
3. **Note Input**: Add descriptive notes explaining the figure's content
4. **Automatic Embedding**: Notes are automatically embedded into the vector database
5. **RAG Integration**: Annotated figures are retrieved during Q&A queries

### 3.4 Database Schema

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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_asset_doc_id ON assets(doc_id);
CREATE INDEX idx_asset_page_no ON assets(page_no);
CREATE INDEX idx_asset_doc_page ON assets(doc_id, page_no);
```

### 3.5 RAG Integration

The system integrates teacher notes into the RAG pipeline:

1. **Embedding Generation**: Teacher notes are embedded using the same embedding model as text chunks
2. **Metadata Storage**: Notes are stored in ChromaDB with metadata:
   - `source: "asset_note"`
   - `asset_id`, `doc_id`, `page_no`
   - `image_path` for reference
3. **Retrieval**: During Q&A queries, the system retrieves both:
   - Relevant text chunks from PDF pages
   - Relevant figure notes based on semantic similarity
4. **Response Format**: Query responses include:
   - Text-based answers
   - Relevant page references
   - Related figures array with image paths and notes

## 4. Technical Implementation

### 4.1 Image Extraction Process

```python
def extract_figures_from_pdf(pdf_path: Path, doc_id: str, assets_base_dir: Path) -> List[AssetCreate]:
    """
    Extracts all images from PDF pages.
    
    Process:
    1. Open PDF with PyMuPDF
    2. Iterate through each page
    3. Extract image data using get_images()
    4. Filter meaningless images
    5. Save to organized directory structure
    6. Create Asset records with metadata
    """
```

### 4.2 Image Filtering Algorithm

The filtering process uses PIL (Pillow) for image analysis:

1. **Load Image**: Convert bytes to PIL Image object
2. **Size Check**: Validate width and height
3. **Aspect Ratio**: Calculate and validate ratio
4. **Color Analysis**: 
   - Resize to 100×100 for performance
   - Count unique colors
   - Calculate dominant color ratio
5. **Brightness Analysis**: 
   - Convert to grayscale
   - Calculate mean and standard deviation
   - Detect pure white/black images

### 4.3 API Endpoints

#### POST `/assets/{asset_id}/note`
Add or update teacher note for an asset.

**Request Body:**
```json
{
    "teacher_note": "This diagram shows the neural network architecture..."
}
```

**Response:**
```json
{
    "success": true,
    "asset_id": "doc1_page5_img0",
    "message": "Note updated and embedded successfully"
}
```

#### GET `/documents/{doc_id}/assets`
Retrieve all assets for a document.

**Response:**
```json
{
    "assets": [
        {
            "asset_id": "doc1_page5_img0",
            "page_no": 5,
            "image_path": "assets/doc1/page_5/img_0.png",
            "teacher_note": "Neural network architecture diagram",
            "bbox": [100, 200, 500, 600]
        }
    ]
}
```

### 4.4 UI Components

The user interface provides:

1. **Document Selection**: Dropdown to select PDF documents
2. **Image List**: Tree widget showing extracted images with page numbers
3. **Image Preview**: Large preview area for selected images
4. **Note Editor**: Text area for adding teacher notes
5. **Batch Operations**: 
   - Delete selected images
   - Sync existing images to database
   - Debug database state

## 5. Usage Workflow

### 5.1 For Teachers

1. **Import PDF**: Upload PDF through the PDF Vector Database interface
2. **Automatic Extraction**: System automatically extracts and filters images
3. **Review Images**: Browse extracted images by document
4. **Add Notes**: 
   - Select an image
   - Preview the image
   - Add educational note in the text area
   - Click "Save Note"
5. **Verify Integration**: Notes are automatically embedded and available in Q&A

### 5.2 For Students

1. **Ask Questions**: Use the Q&A interface to ask questions
2. **Receive Answers**: Answers include:
   - Text-based explanations
   - Relevant page references
   - Related figures (if applicable)
3. **View Figures**: Click on figure references to view annotated images

## 6. Performance Considerations

### 6.1 Image Filtering Performance

- **Resizing**: Images are resized to 100×100 for color analysis to reduce computation
- **Lazy Loading**: Images are only analyzed when extracted, not during display
- **Caching**: Filtered results are cached in database to avoid re-analysis

### 6.2 Storage Optimization

- **Directory Structure**: Hierarchical organization prevents directory bloat
- **File Naming**: Consistent naming convention enables efficient lookup
- **Database Indexing**: Multiple indexes on `doc_id` and `page_no` for fast queries

## 7. Error Handling

The system includes comprehensive error handling:

1. **Missing Dependencies**: Graceful degradation if PIL is not installed
2. **Invalid Images**: Corrupted images are skipped with logging
3. **Database Errors**: Transaction rollback on failures
4. **File System Errors**: Permission errors are caught and reported

## 8. Future Enhancements

Potential improvements for future versions:

1. **OCR Integration**: Extract text from images for better searchability
2. **Image Classification**: Automatic categorization of figure types
3. **Batch Annotation**: Bulk editing of teacher notes
4. **Export Functionality**: Export annotated figures as educational materials
5. **Version Control**: Track changes to teacher notes over time

## 9. Dependencies

- **PyMuPDF (fitz)**: PDF parsing and image extraction
- **Pillow (PIL)**: Image analysis and filtering
- **SQLAlchemy**: Database ORM
- **ChromaDB**: Vector database for embeddings
- **FastAPI**: REST API framework

## 10. Conclusion

The PDF Figure Assets Management System provides a comprehensive solution for managing educational figures extracted from PDF documents. By combining automatic extraction, intelligent filtering, teacher annotation, and RAG integration, the system enhances the educational value of PDF-based learning materials and improves the quality of AI-powered question-answering systems.
