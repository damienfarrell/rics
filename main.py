import fitz  # PyMuPDF
import os
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a single PDF file.
    """
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        text = ""
        
        # Extract text from each page
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
            text += "\n\n"  # Add spacing between pages
        
        doc.close()
        return text
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return ""

def extract_text_from_folder(folder_path, output_folder=None):
    """
    Extract text from all PDF files in a folder.
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"Folder '{folder_path}' does not exist.")
        return {}
    
    # Find all PDF files in the folder
    pdf_files = list(folder_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{folder_path}'")
        return {}
    
    print(f"Found {len(pdf_files)} PDF files to process...")
    
    extracted_texts = {}
    
    # Create output folder if specified
    if output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)
    
    # Process each PDF file
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_file))
        
        if text.strip():  # Only store non-empty text
            extracted_texts[pdf_file.name] = text
            
            # Save to text file if output folder is specified
            if output_folder:
                output_file = output_path / f"{pdf_file.stem}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"Saved text to: {output_file}")
        else:
            print(f"No text extracted from: {pdf_file.name}")
    
    return extracted_texts

if __name__ == "__main__":
    # Configuration
    data_folder = "data"
    output_folder = "extracted_texts"  # Optional: set to None if you don't want to save files
    
    # Extract text from all PDFs in the data folder
    results = extract_text_from_folder(data_folder, output_folder)
    
    # Print summary
    print("\n=== EXTRACTION SUMMARY ===")
    print(f"Successfully processed {len(results)} PDF files")
    
    # Optional: Print first 200 characters of each extracted text
    for filename, text in results.items():
        print(f"\n--- {filename} ---")
        print(f"Text length: {len(text)} characters")
        print(f"Preview: {text[:200]}...")
        print("-" * 50)
    
    # Optional: Save all texts to a single combined file
    if results:
        combined_file = "all_extracted_texts.txt"
        with open(combined_file, 'w', encoding='utf-8') as f:
            for filename, text in results.items():
                f.write(f"=== {filename} ===\n")
                f.write(text)
                f.write(f"\n{'='*50}\n\n")
        print(f"\nAll texts combined and saved to: {combined_file}")