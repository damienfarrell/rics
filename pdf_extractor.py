import os
import fitz  # PyMuPDF
from pathlib import Path
import logging
import json
from datetime import datetime
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MCPDocumentMetadata:
    """Streamlined metadata for MCP server usage."""
    document_id: str
    filename: str
    relative_path: str
    title: str
    author: Optional[str]
    document_type: str
    page_count: int
    keywords: List[str]
    has_images: bool
    has_tables: bool
    extraction_date: str


class MCPPDFExtractor:
    """Optimized PDF extractor for MCP server usage."""
    
    def __init__(self, chunk_size: int = 2000):
        self.chunk_size = chunk_size
        
    def generate_document_id(self, file_path: Path) -> str:
        """Generate a simple, readable document ID."""
        name_part = file_path.stem[:30].lower()
        name_part = re.sub(r'[^a-z0-9]', '_', name_part)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{name_part}_{timestamp}"
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords using simple frequency analysis."""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                     'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 
                     'was', 'were', 'been', 'be', 'have', 'has', 'had', 'will'}
        
        # Find capitalized words (likely important terms)
        words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
        
        # Count frequency
        word_freq = {}
        for word in words:
            if word.lower() not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]
    
    def classify_document_type(self, text_sample: str, filename: str) -> str:
        """Simple document classification based on content patterns."""
        text_lower = text_sample.lower()
        filename_lower = filename.lower()
        
        # Check filename patterns first
        patterns = {
            'invoice': ['invoice', 'receipt', 'bill'],
            'report': ['report', 'analysis', 'review'],
            'contract': ['contract', 'agreement'],
            'manual': ['manual', 'guide', 'documentation'],
            'presentation': ['presentation', 'slides']
        }
        
        for doc_type, keywords in patterns.items():
            if any(keyword in filename_lower for keyword in keywords):
                return doc_type
            if any(keyword in text_lower for keyword in keywords):
                return doc_type
        
        return 'document'
    
    def chunk_content(self, text: str) -> List[Dict]:
        """Split content into chunks for better MCP context handling."""
        # Split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = ""
        current_words = 0
        
        for para in paragraphs:
            para_words = len(para.split())
            
            # If adding this paragraph exceeds chunk size, save current chunk
            if current_words + para_words > self.chunk_size and current_chunk:
                chunks.append({
                    "chunk_id": len(chunks),
                    "text": current_chunk.strip(),
                    "word_count": current_words
                })
                current_chunk = para
                current_words = para_words
            else:
                current_chunk += "\n\n" + para if current_chunk else para
                current_words += para_words
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                "chunk_id": len(chunks),
                "text": current_chunk.strip(),
                "word_count": current_words
            })
        
        return chunks
    
    def extract_content(self, pdf_path: Path, relative_path: str) -> Dict:
        """Extract content optimized for MCP usage."""
        try:
            doc = fitz.open(pdf_path)
            
            # Extract all text
            full_text = ""
            has_images = False
            
            for page in doc:
                page_text = page.get_text()
                full_text += page_text + "\n\n"
                
                if page.get_images():
                    has_images = True
            
            # Clean up text
            full_text = re.sub(r'\n{3,}', '\n\n', full_text).strip()
            
            # Detect tables (simple pattern matching)
            has_tables = bool(re.search(r'[\|\+\-]{3,}', full_text))
            
            # Extract keywords from first 5000 chars
            keywords = self.extract_keywords(full_text[:5000])
            
            # Create metadata
            metadata = MCPDocumentMetadata(
                document_id=self.generate_document_id(pdf_path),
                filename=pdf_path.name,
                relative_path=str(relative_path),
                title=doc.metadata.get("title", "").strip() or pdf_path.stem,
                author=doc.metadata.get("author", "").strip() or None,
                document_type=self.classify_document_type(full_text[:1000], pdf_path.stem),
                page_count=len(doc),
                keywords=keywords,
                has_images=has_images,
                has_tables=has_tables,
                extraction_date=datetime.now().isoformat()
            )
            
            doc.close()
            
            # Chunk content
            chunks = self.chunk_content(full_text)
            
            # Create result
            return {
                "status": "success",
                "document_id": metadata.document_id,
                "metadata": asdict(metadata),
                "content": {
                    "chunks": chunks,
                    "chunk_count": len(chunks),
                    "total_words": sum(chunk["word_count"] for chunk in chunks)
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting {pdf_path}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file": str(pdf_path)
            }
    
    def save_extraction(self, result: Dict, output_dir: Path, relative_dir: Path) -> bool:
        """Save extraction result in MCP-friendly format."""
        try:
            # Create output directory
            output_path = output_dir / relative_dir
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save as JSON
            if result['status'] == 'success':
                filename = result['metadata']['filename']
                json_path = output_path / f"{Path(filename).stem}.json"
            else:
                json_path = output_path / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving extraction: {str(e)}")
            return False


def create_mcp_index(documents: List[Dict]) -> Dict:
    """Create an optimized index for MCP queries."""
    index = {
        "version": "3.0",
        "created_at": datetime.now().isoformat(),
        "document_count": len(documents),
        "documents": {},  # ID -> basic info mapping
        "by_type": {},    # Type -> list of IDs
        "by_folder": {},  # Folder -> list of IDs
        "keywords": {}    # Keyword -> list of IDs
    }
    
    for doc in documents:
        if doc.get("status") != "success":
            continue
            
        doc_id = doc["document_id"]
        metadata = doc["metadata"]
        
        # Store minimal info in main index
        index["documents"][doc_id] = {
            "filename": metadata["filename"],
            "path": metadata["relative_path"],
            "title": metadata["title"],
            "type": metadata["document_type"],
            "pages": metadata["page_count"]
        }
        
        # Index by type
        doc_type = metadata["document_type"]
        if doc_type not in index["by_type"]:
            index["by_type"][doc_type] = []
        index["by_type"][doc_type].append(doc_id)
        
        # Index by folder
        folder = str(Path(metadata["relative_path"]).parent)
        if folder == ".":
            folder = "root"
        if folder not in index["by_folder"]:
            index["by_folder"][folder] = []
        index["by_folder"][folder].append(doc_id)
        
        # Index by keywords
        for keyword in metadata["keywords"]:
            if keyword not in index["keywords"]:
                index["keywords"][keyword] = []
            index["keywords"][keyword].append(doc_id)
    
    return index


def process_pdfs_for_mcp(source_folder: str, output_folder: str):
    """Process PDFs optimized for MCP server usage."""
    source_path = Path(source_folder)
    output_path = Path(output_folder)
    
    if not source_path.exists():
        logger.error(f"Source folder '{source_folder}' does not exist!")
        return
    
    # Initialize extractor
    extractor = MCPPDFExtractor(chunk_size=2000)
    
    # Process results
    all_documents = []
    processed_count = 0
    failed_count = 0
    
    # Process all PDFs
    for pdf_file in source_path.rglob("*.pdf"):
        relative_path = pdf_file.relative_to(source_path)
        relative_dir = relative_path.parent
        
        logger.info(f"Processing: {relative_path}")
        
        # Extract content
        result = extractor.extract_content(pdf_file, relative_path)
        
        if result["status"] == "success":
            if extractor.save_extraction(result, output_path, relative_dir):
                processed_count += 1
                all_documents.append(result)
        else:
            failed_count += 1
            # Save error in errors folder
            extractor.save_extraction(result, output_path / "errors", relative_dir)
    
    # Create and save index
    if all_documents:
        index = create_mcp_index(all_documents)
        index_path = output_path / "mcp_index.json"
        
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created MCP index at: {index_path}")
    
    # Create simple folder map
    folder_map = {}
    for doc in all_documents:
        if doc.get("status") == "success":
            folder = str(Path(doc["metadata"]["relative_path"]).parent)
            if folder == ".":
                folder = "root"
            if folder not in folder_map:
                folder_map[folder] = {"count": 0, "types": {}}
            folder_map[folder]["count"] += 1
            
            doc_type = doc["metadata"]["document_type"]
            if doc_type not in folder_map[folder]["types"]:
                folder_map[folder]["types"][doc_type] = 0
            folder_map[folder]["types"][doc_type] += 1
    
    # Save folder map
    folder_map_path = output_path / "folder_map.json"
    with open(folder_map_path, 'w', encoding='utf-8') as f:
        json.dump(folder_map, f, indent=2)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("MCP PDF Extraction Complete!")
    logger.info(f"Successfully processed: {processed_count} documents")
    logger.info(f"Failed: {failed_count} documents")
    logger.info(f"Index saved to: {index_path}")
    logger.info("="*60)


def main():
    """Main function to run the MCP PDF extraction."""
    source_folder = "data"
    output_folder = "mcp_resources"
    
    logger.info("Starting MCP-optimized PDF extraction")
    process_pdfs_for_mcp(source_folder, output_folder)


if __name__ == "__main__":
    main()