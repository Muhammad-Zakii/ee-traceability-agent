import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def parse_pdf(file_path: str):
    """Extracts and chunks text from engineering PDFs."""
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100
    )
    docs = text_splitter.split_documents(documents)
    return docs

def parse_excel_requirements(file_path: str):
    """Reads input requirements from Excel for validation."""
    df = pd.read_excel(file_path)
    # Convert dataframe rows to a list of dictionaries
    requirements = df.to_dict(orient="records")
    return requirements