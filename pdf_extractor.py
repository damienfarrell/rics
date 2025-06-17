import os
import fitz  # PyMuPDF
from pathlib import Path
import logging
import json
from datetime import datetime
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFExtractor:
    def __init__(self, preserve_layout=True, extract_images=False):
        self.preserve_layout = preserve_layout
        self.extract_images = extract_images
    
    def extract_metadata(self, doc):
        """Extract PDF metadata."""
        metadata = doc.metadata
        return {
            "title": metadata.get("title", "").strip() or None,
            "author": metadata.get("author", "").strip() or None,
            "subject": metadata.get("subject", "").strip() or None,
            "keywords": metadata.get("keywords", "").strip() or None,
            "creator": metadata.get("creator", "").strip() or None,
            "producer": metadata.get("producer", "").strip() or None,
            "creation_date": self._format_date(metadata.get("creationDate")),
            "modification_date": self._format_date(metadata.get("modDate")),
            "page_count": len(doc),
        }
    
    def _format_date(self, date_str):
        """Format PDF date string to ISO format."""
        if not date_str:
            return None
        try:
            # PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
            if date_str.startswith("D:"):
                date_str = date_str[2:]
            # Extract just the date portion
            date_part = date_str[:14]
            if len(date_part) >= 8:
                dt = datetime.strptime(date_part[:8], "%Y%m%d")
                return dt.isoformat()
        except:
            pass
        return None
    
    def extract_text_with_structure(self, pdf_path):
        """Extract text from PDF with structure preservation."""
        try:
            doc = fitz.open(pdf_path)
            
            # Extract metadata
            metadata = self.extract_metadata(doc)
            
            # Extract text from each page
            pages = []
            full_text = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get page dimensions
                page_rect = page.rect
                page_info = {
                    "page_number": page_num + 1,
                    "width": page_rect.width,
                    "height": page_rect.height,
                }
                
                if self.preserve_layout:
                    # Extract with layout preservation
                    text_page = page.get_textpage()
                    blocks = page.get_text("dict")
                    
                    page_text = []
                    page_structure = []
                    
                    for block in blocks["blocks"]:
                        if block["type"] == 0:  # Text block
                            block_text = []
                            for line in block["lines"]:
                                line_text = ""
                                for span in line["spans"]:
                                    line_text += span["text"]
                                if line_text.strip():
                                    block_text.append(line_text)
                                    
                                    # Store structure info
                                    page_structure.append({
                                        "type": "text",
                                        "content": line_text.strip(),
                                        "font_size": span.get("size", 0),
                                        "font_name": span.get("font", ""),
                                        "bbox": line["bbox"],  # Bounding box
                                    })
                            
                            if block_text:
                                page_text.extend(block_text)
                    
                    page_content = "\n".join(page_text)
                    page_info["structured_content"] = page_structure
                    
                else:
                    # Simple text extraction
                    page_content = page.get_text()
                
                page_info["text"] = page_content
                pages.append(page_info)
                full_text.append(f"\n--- Page {page_num + 1} ---\n{page_content}")
            
            doc.close()
            
            # Create structured output
            result = {
                "status": "success",
                "source_file": str(pdf_path),
                "extraction_date": datetime.now().isoformat(),
                "metadata": metadata,
                "extraction_settings": {
                    "preserve_layout": self.preserve_layout,
                    "extract_images": self.extract_images,
                },
                "content": {
                    "full_text": "\n".join(full_text),
                    "pages": pages if self.preserve_layout else None,
                },
                "statistics": {
                    "total_pages": len(pages),
                    "total_characters": sum(len(p["text"]) for p in pages),
                    "total_words": sum(len(p["text"].split()) for p in pages),
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            return {
                "status": "error",
                "source_file": str(pdf_path),
                "error": str(e),
                "extraction_date": datetime.now().isoformat(),
            }
    
    def save_extraction(self, result, output_path):
        """Save extraction result in structured format."""
        try:
            # Save as JSON for structured data
            json_path = output_path.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Also save plain text version for easy reading
            if result["status"] == "success":
                txt_path = output_path.with_suffix('.txt')
                with open(txt_path, 'w', encoding='utf-8') as f:
                    # Write metadata header
                    f.write("=" * 80 + "\n")
                    f.write(f"PDF: {Path(result['source_file']).name}\n")
                    if result['metadata']['title']:
                        f.write(f"Title: {result['metadata']['title']}\n")
                    if result['metadata']['author']:
                        f.write(f"Author: {result['metadata']['author']}\n")
                    f.write(f"Pages: {result['metadata']['page_count']}\n")
                    f.write(f"Extracted: {result['extraction_date']}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    # Write content
                    f.write(result['content']['full_text'])
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving extraction result: {str(e)}")
            return False

def process_pdfs(source_folder, destination_folder, preserve_layout=True):
    """Process all PDFs in source folder with improved extraction."""
    # Create destination folder if it doesn't exist
    Path(destination_folder).mkdir(parents=True, exist_ok=True)
    
    # Initialize extractor
    extractor = PDFExtractor(preserve_layout=preserve_layout)
    
    # Track statistics
    processed_count = 0
    error_count = 0
    total_pages = 0
    
    # Walk through all files in source folder and subfolders
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.lower().endswith('.pdf'):
                # Get full path of the PDF
                pdf_path = Path(root) / file
                
                # Create relative path structure in destination
                relative_path = Path(root).relative_to(source_folder)
                dest_subfolder = Path(destination_folder) / relative_path
                dest_subfolder.mkdir(parents=True, exist_ok=True)
                
                # Create output path (without extension)
                output_path = dest_subfolder / Path(file).stem
                
                logger.info(f"Processing: {pdf_path}")
                
                # Extract text with structure
                result = extractor.extract_text_with_structure(pdf_path)
                
                if result["status"] == "success":
                    if extractor.save_extraction(result, output_path):
                        processed_count += 1
                        total_pages += result["metadata"]["page_count"]
                        logger.info(f"Saved to: {output_path}.json and {output_path}.txt")
                    else:
                        error_count += 1
                else:
                    error_count += 1
                    # Save error information
                    error_path = output_path.with_suffix('.error.json')
                    with open(error_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
    
    # Print summary
    logger.info(f"\nProcessing complete!")
    logger.info(f"Successfully processed: {processed_count} PDFs")
    logger.info(f"Total pages extracted: {total_pages}")
    logger.info(f"Errors encountered: {error_count} PDFs")
    
    # Save processing summary
    summary = {
        "processing_date": datetime.now().isoformat(),
        "source_folder": str(source_folder),
        "destination_folder": str(destination_folder),
        "statistics": {
            "processed_pdfs": processed_count,
            "failed_pdfs": error_count,
            "total_pages": total_pages,
        }
    }
    
    summary_path = Path(destination_folder) / "_extraction_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

def main():
    """Main function to run the PDF extraction script."""
    # Define source and destination folders
    source_folder = "data"
    destination_folder = "mcp_resources"  # Changed to match MCP server directory
    
    # Check if source folder exists
    if not os.path.exists(source_folder):
        logger.error(f"Source folder '{source_folder}' does not exist!")
        return
    
    # Process PDFs with layout preservation
    logger.info(f"Starting PDF extraction from '{source_folder}' to '{destination_folder}'")
    process_pdfs(source_folder, destination_folder, preserve_layout=True)

if __name__ == "__main__":
    main()