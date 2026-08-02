from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from src.config import CHROMA_DB_DIR, EMBEDDING_MODEL
from src.document_parser import parse_pdf

def get_embeddings():
    """Loads the local Hugging Face embedding model."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

def build_vector_store(pdf_path: str):
    """Builds a local ChromaDB using HuggingFace embeddings."""
    docs = parse_pdf(pdf_path)
    embeddings = get_embeddings()
    
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(CHROMA_DB_DIR)
    )
    return vectorstore

def get_retriever():
    """Returns the retriever interface."""
    embeddings = get_embeddings()
    vectorstore = Chroma(
        persist_directory=str(CHROMA_DB_DIR), 
        embedding_function=embeddings
    )
    return vectorstore.as_retriever(search_kwargs={"k": 3})