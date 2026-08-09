import os
from pypdf import PdfReader
import io
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from src.config import DATA_DIR  # Assuming you have a config file for directories

def get_chroma_db():
    """Initializes and returns the ChromaDB connection."""
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    db_path = os.path.join(DATA_DIR, "chroma_db")
    os.makedirs(db_path, exist_ok=True)
    return Chroma(persist_directory=db_path, embedding_function=embeddings)

async def process_and_store_multiple_pdfs(files):
    """
    Reads multiple PDFs from FastAPI, splits them into chunks, 
    tags them with the EXACT filename as metadata, and stores them in ChromaDB.
    """
    vector_db = get_chroma_db()
    
    all_chunks = []
    all_metadatas = []
    
    # Text splitter config
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    
    # Loop through every file uploaded
    for file in files:
        # Read the file content from memory
        content = await file.read()
        pdf_file_obj = io.BytesIO(content)
        pdf_reader = PdfReader(pdf_file_obj)
        
        # Extract text
        raw_text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                raw_text += extracted + "\n"
                
        # Split text into chunks
        chunks = text_splitter.split_text(raw_text)
        
        # MAGIC STEP: Tag every single chunk with the filename it came from
        metadatas = [{"source": file.filename} for _ in chunks]
        
        all_chunks.extend(chunks)
        all_metadatas.extend(metadatas)
        
    # Store everything in the vector database at once
    if all_chunks:
        vector_db.add_texts(texts=all_chunks, metadatas=all_metadatas)
        print(f"Successfully added {len(all_chunks)} chunks across {len(files)} files to ChromaDB.")

# --- THE MISSING FUNCTION IS BACK ---
def get_retriever():
    """Returns the retriever for the LangGraph agent to use when searching."""
    vector_db = get_chroma_db()
    # "k=3" means it will retrieve the top 3 most relevant paragraphs when searching
    return vector_db.as_retriever(search_kwargs={"k": 3})