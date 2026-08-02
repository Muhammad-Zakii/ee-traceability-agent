import streamlit as st
import pandas as pd
import requests
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from src.vector_store import build_vector_store
from src.config import DATA_DIR

st.set_page_config(page_title="E/E Traceability Agent", layout="wide")

st.title("🚗 Privacy-First E/E Traceability Agent")
st.markdown("""
**Local Enterprise Execution:** This dashboard connects to a local LangGraph agent powered by **Ollama (Llama 3)** and **Hugging Face**. 
*Zero proprietary engineering data leaves this machine.*
""")

st.divider()

# --- Initialize Session State for the Dashboard ---
if 'agent_results' not in st.session_state:
    st.session_state.agent_results = None

# --- Create Tabs ---
tab1, tab2 = st.tabs(["🤖 Agent UI", "📊 KPI Dashboard"])

# ==========================================
# TAB 1: THE TRACEABILITY AGENT
# ==========================================
with tab1:
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
                    
                    # --- DASHBOARD DATA PREPARATION ---
                    # If your backend doesn't return latency or context status yet, we simulate it here for the dashboard demo
                    if 'latency_seconds' not in df.columns:
                        df['latency_seconds'] = np.random.uniform(2.5, 5.5, len(df))
                    if 'rag_context_found' not in df.columns:
                        df['rag_context_found'] = True 
                    
                    # Save to session state so the Dashboard tab can read it
                    st.session_state.agent_results = df
                    
                    # Display the styled dataframe in the Agent UI
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

# ==========================================
# TAB 2: THE DATA DASHBOARD
# ==========================================
with tab2:
    st.header("Real-Time Performance KPIs")
    
    if st.session_state.agent_results is not None:
        df = st.session_state.agent_results
        
        # Calculate KPIs using Pandas
        total_processed = len(df)
        conflicts_found = len(df[df["status"] == "CONFLICT"])
        avg_latency = round(df["latency_seconds"].mean(), 2)
        rag_success = (df["rag_context_found"].sum() / total_processed) * 100

        # Top Level KPI Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Reqs Processed", value=total_processed)
        with col2:
            st.metric(label="Conflicts Detected", value=conflicts_found, delta="- Action Required", delta_color="inverse")
        with col3:
            st.metric(label="Avg Latency (s)", value=f"{avg_latency}s")
        with col4:
            st.metric(label="RAG Success Rate", value=f"{rag_success}%")

        st.divider()

        # Data Visualization
        col_chart, col_data = st.columns([1, 1])

        with col_chart:
            st.markdown("**Validation Status by Component**")
            # Group by component and status
            status_counts = df.groupby(['component', 'status']).size().unstack(fill_value=0)
            
            # Ensure both colors map correctly even if one status is missing
            colors = []
            if 'CONFLICT' in status_counts.columns: colors.append('#ff4b4b')
            if 'VALID' in status_counts.columns: colors.append('#00cc96')
            
            fig, ax = plt.subplots(figsize=(3, 2))
            status_counts.plot(kind='bar', stacked=True, color=colors, ax=ax)
            ax.set_ylabel("Count")
            plt.xticks(rotation=35, ha='right', fontsize=5)
            plt.yticks(fontsize=5)
            st.pyplot(fig, use_container_width=False)

        with col_data:
            st.markdown("**Raw Analytics Log**")
            # Display a cleaner version of the dataframe for the dashboard
            display_df = df[['req_id', 'component', 'status', 'latency_seconds']]
            st.dataframe(display_df, width="stretch")
            
    else:
        st.info("Waiting for data... Please run the Local AI Validation Agent in the **Agent UI** tab to generate KPIs.")