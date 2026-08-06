import os
from pathlib import Path

# Try importing parsers. They will be available once the background pip install completes.
try:
    import pdfplumber
    import docx
except ImportError:
    pass

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100):
    """
    Splits text into chunks of `chunk_size` characters with `overlap`.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from PDF, DOCX, or TXT files.
    """
    ext = Path(file_path).suffix.lower()
    
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
            
    elif ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is not installed. Run 'pip install pdfplumber'.")
        
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text
        
    elif ext == ".docx":
        try:
            import docx
        except ImportError:
            raise ImportError("python-docx is not installed. Run 'pip install python-docx'.")
            
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
        
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .txt, .pdf, and .docx are supported.")

def ingest_file_to_chroma(file_path: str, long_term_memory_instance):
    """
    Extracts text, chunks it, and stores it in the provided LongTermMemory (ChromaDB) instance.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    print(f"[RAG] Extracting text from {file_path}...")
    full_text = extract_text_from_file(file_path)
    
    if not full_text.strip():
        raise ValueError(f"No text could be extracted from {file_path}.")
        
    print(f"[RAG] Chunking text...")
    chunks = chunk_text(full_text)
    
    print(f"[RAG] Storing {len(chunks)} chunks into ChromaDB...")
    filename = os.path.basename(file_path)
    
    for i, chunk in enumerate(chunks):
        metadata = {
            "source": filename,
            "chunk_index": i,
            "type": "rag_document"
        }
        # Provide a unique doc_id for each chunk
        doc_id = f"{filename}_chunk_{i}"
        long_term_memory_instance.store_memory(document=chunk, metadata=metadata, doc_id=doc_id)
        
    return f"Successfully ingested {filename} ({len(chunks)} chunks) into memory."
