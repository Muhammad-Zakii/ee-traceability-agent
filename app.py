import streamlit as st
import pandas as pd
import requests
import os
from src.vector_store import build_vector_store
from src.config import DATA_DIR

st.set_page_config(page_title="E/E Traceability Agent", layout="wide")

st.title("🚗 Privacy-First E/E Traceability Agent")
st.markdown("""
**Local Enterprise Execution:** This dashboard connects to a local LangGraph agent powered by **Ollama (Llama 3)** and **Hugging Face**. 
*Zero proprietary engineering data leaves this machine.*
""")

st.divider()

# 1. Knowledge Base Building
st.header("1. Ingest Technical Specification (PDF)")
uploaded_pdf = st.file_uploader("Upload PDF Spec (e.g., E/E Component Manual)", type="pdf")

if uploaded_pdf and st.button("Process PDF to Local Vector DB"):
    pdf_path = DATA_DIR / "uploaded_spec.pdf"
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    with open(pdf_path, "wb") as f:
        f.write(uploaded_pdf.getbuffer())
    
    with st.spinner("Embedding documents locally via Hugging Face into ChromaDB..."):
        build_vector_store(str(pdf_path))
        st.success("Knowledge Base successfully updated locally!")

st.divider()

# 2. Validation Trigger
st.header("2. Validate Requirements via LangGraph")
st.write("Simulating requirements input (normally ingested via bulk Excel imports):")

# Mock requirements for demo
mock_requirements = [
    {"req_id": "REQ-001", "component": "ECU_Gateway", "description": "Must support 48V operating voltage."},
    {"req_id": "REQ-002", "component": "Infotainment_Display", "description": "Maximum power draw should not exceed 15A."}
]
st.json(mock_requirements)

if st.button("Run Local AI Validation Agent"):
    with st.spinner("Running LangGraph Agent Workflow via local Llama 3..."):
        try:
            response = requests.post(
                "http://localhost:8000/validate", 
                json={"requirements": mock_requirements}
            )
            
            if response.status_code == 200:
                data = response.json()
                st.success(f"Excel Report automatically generated and saved at: `{data['report_path']}`")
                
                df = pd.DataFrame(data['results'])
                
                def color_status(val):
                    if val == 'VALID':
                        return 'color: green; font-weight: bold'
                    elif val == 'CONFLICT':
                        return 'color: red; font-weight: bold'
                    return 'color: orange'
                
                st.dataframe(df.style.map(color_status, subset=['status']), use_container_width=True)
            else:
                st.error(f"API call failed with status code {response.status_code}.")
                
        except requests.exceptions.ConnectionError:
            st.error("Connection failed. Please ensure the FastAPI server is running on http://localhost:8000 (run `uvicorn src.api:app --reload`).")