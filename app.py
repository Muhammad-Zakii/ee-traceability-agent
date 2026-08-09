import streamlit as st
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

st.set_page_config(page_title="E/E Traceability Agent", layout="wide")

st.title("🚗 Privacy-First E/E Traceability Agent")
st.markdown("""
**Local Enterprise Execution:** This dashboard connects to a local LangGraph agent powered by **Ollama (Llama 3)** and **Hugging Face**. 
*Zero proprietary engineering data leaves this machine.*
""")

st.divider()

if 'agent_results' not in st.session_state:
    st.session_state.agent_results = None

tab1, tab2 = st.tabs(["🤖 Agent UI", "📊 KPI Dashboard"])

# ==========================================
# TAB 1: THE TRACEABILITY AGENT
# ==========================================
with tab1:
    st.header("1. Ingest Technical Specifications (PDFs)")
    
    # MAGIC LINE: accept_multiple_files=True
    uploaded_pdfs = st.file_uploader("Upload Supplier Manuals (PDF)", type="pdf", accept_multiple_files=True)

    if st.button("Process PDFs to Local Vector DB"):
        if uploaded_pdfs:
            with st.spinner(f"Sending {len(uploaded_pdfs)} documents to the backend for processing..."):
                try:
                    # Prepare multiple files to send to FastAPI
                    files_to_send = [("files", (file.name, file.getvalue(), "application/pdf")) for file in uploaded_pdfs]
                    
                    # Hit the new FastAPI endpoint
                    response = requests.post("http://localhost:8000/upload-pdfs", files=files_to_send)
                    
                    if response.status_code == 200:
                        st.success(f"✅ {len(uploaded_pdfs)} Knowledge Base documents successfully embedded into ChromaDB!")
                    else:
                        st.error(f"Backend Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Connection failed. Is the FastAPI server running on port 8000?")
        else:
            st.warning("Please upload at least one PDF.")

    st.divider()

    st.header("2. Validate Requirements via LangGraph")
    st.write("Simulating requirements input (JSON payload sent to backend):")

    mock_requirements = [
        # --- TELEMATICS & GATEWAY ECU (Tests sample_specs.pdf) ---
        {"req_id": "REQ-001", "component": "ECU_Gateway", "description": "Maximum current draw under peak conditions must not exceed 15A."}, # VALID
        {"req_id": "REQ-002", "component": "ECU_Gateway", "description": "Must support 48V nominal operating voltage for hybrid networks."}, # CONFLICT (Doc says 12V)
        {"req_id": "REQ-003", "component": "Telematics_Unit", "description": "Sleep mode current consumption must be under 5 mA."}, # VALID
        {"req_id": "REQ-004", "component": "Telematics_Unit", "description": "Requires continuous normal operation during extreme voltage drops down to 6V."}, # CONFLICT (Doc says 9V drop tolerance)

        # --- BATTERY MANAGEMENT SYSTEM (Tests Bosch_BMS_Controller_v2.pdf) ---
        {"req_id": "REQ-005", "component": "Battery_Management", "description": "Must support 400V nominal high-voltage architectures."}, # VALID
        {"req_id": "REQ-006", "component": "Battery_Management", "description": "Operating temperature limit must support up to 65°C."}, # CONFLICT (Doc says 75°C max)
        {"req_id": "REQ-007", "component": "Battery_Management", "description": "Must utilize FlexRay protocol for primary vehicle network communication."}, # CONFLICT (Doc says CAN 2.0B)

        # --- ADAS RADAR SENSOR (Tests Continental_ADAS_Radar_Sensor.pdf) ---
        {"req_id": "REQ-008", "component": "Radar_Sensor", "description": "High-speed CAN FD communication protocols are required."}, # VALID
        {"req_id": "REQ-009", "component": "Radar_Sensor", "description": "Sensor must survive maximum ambient temperatures of 120°C."}, # VALID (Doc says up to 125°C)
        {"req_id": "REQ-010", "component": "Radar_Sensor", "description": "Maximum active power consumption must be strictly under 5W."} # CONFLICT (Doc says 8.5W)
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
                    st.success(f"Excel Report generated at: `{data.get('report_path', 'Local Directory')}`")
                    
                    df = pd.DataFrame(data['results'])
                    st.session_state.agent_results = df
                    
                    def color_status(val):
                        if val == 'VALID': return 'color: green; font-weight: bold'
                        elif val == 'CONFLICT': return 'color: red; font-weight: bold'
                        return 'color: orange'
                    
                    if 'status' in df.columns:
                        st.dataframe(df.style.map(color_status, subset=['status']), use_container_width=True)
                    else:
                        st.dataframe(df, use_container_width=True)
                else:
                    st.error(f"API call failed: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                st.error("Connection failed. Please ensure FastAPI server is running.")

# ==========================================
# TAB 2: THE DATA DASHBOARD (STRICT LLM DATA ONLY)
# ==========================================
with tab2:
    st.header("Real-Time Performance KPIs")
    
    if st.session_state.agent_results is not None:
        df = st.session_state.agent_results
        
        total_processed = len(df)
        
        # Safely calculate KPIs based on columns provided by the API
        conflicts_found = len(df[df["status"] == "CONFLICT"]) if 'status' in df.columns else 0
        
        if 'latency_seconds' in df.columns:
            avg_latency = round(pd.to_numeric(df["latency_seconds"], errors='coerce').mean(), 2)
        else:
            avg_latency = 0.0
            
        if 'rag_context_found' in df.columns:
            # Convert string "TRUE" to boolean if necessary, then calculate success rate
            rag_success = (df['rag_context_found'].astype(str).str.upper() == 'TRUE').sum()
            rag_success_pct = round((rag_success / total_processed) * 100, 1) if total_processed > 0 else 0
        else:
            rag_success_pct = "N/A"

        # Top Level KPI Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Reqs Processed", value=total_processed)
        with col2:
            st.metric(label="Conflicts Detected", value=conflicts_found, delta="- Action Required", delta_color="inverse")
        with col3:
            st.metric(label="Avg Latency (s)", value=f"{avg_latency}s")
        with col4:
            st.metric(label="RAG Success Rate", value=f"{rag_success_pct}%")

        st.divider()

        # Row 1: Existing Visualizations
        col_chart, col_data = st.columns([1, 1])

        with col_chart:
            st.markdown("**Validation Status by Component**")
            if 'component' in df.columns and 'status' in df.columns:
                status_counts = df.groupby(['component', 'status']).size().unstack(fill_value=0)
                
                colors = []
                if 'CONFLICT' in status_counts.columns: colors.append('#ff4b4b')
                if 'VALID' in status_counts.columns: colors.append('#00cc96')
                
                if not status_counts.empty:
                    fig, ax = plt.subplots(figsize=(3, 2))
                    status_counts.plot(kind='bar', stacked=True, color=colors, ax=ax)
                    ax.set_ylabel("Count")
                    plt.xticks(rotation=35, ha='right', fontsize=5)
                    plt.yticks(fontsize=5)
                    st.pyplot(fig, use_container_width=False)
                    plt.close(fig)  # <--- FIX 1: Closes memory leak for bar chart
                else:
                    st.info("No status data available.")

        with col_data:
            st.markdown("**Raw Analytics Log**")
            # Only display columns that actually exist in the API payload
            # FIX 2: Added 'source_document' so it shows up on the frontend!
            display_cols = [col for col in ['req_id', 'component', 'status', 'source_document', 'latency_seconds'] if col in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, width="stretch")

        st.divider()

        # Row 2: PARETO DIAGRAM (Only renders if LLM provides error_category)
        st.subheader("Pareto Analysis: Top Causes of Validation Failures")
        st.markdown("Prioritizing E/E requirement mismatches according to the 80/20 rule.")

        if 'status' in df.columns and 'error_category' in df.columns:
            conflicts_df = df[df["status"] == "CONFLICT"].copy()
            
            if not conflicts_df.empty:
                # Aggregate the error frequencies directly from LLM output
                pareto_data = conflicts_df['error_category'].value_counts().reset_index()
                pareto_data.columns = ['Error Type', 'Frequency']
                
                if not pareto_data.empty and pareto_data['Frequency'].sum() > 0:
                    # Calculate cumulative percentage
                    pareto_data['Cumulative Percentage'] = pareto_data['Frequency'].cumsum() / pareto_data['Frequency'].sum() * 100
                    
                    fig2, ax1 = plt.subplots(figsize=(10, 4))
                    
                    ax1.bar(pareto_data['Error Type'], pareto_data['Frequency'], color='tab:blue')
                    ax1.set_xlabel('Type of Requirement Error (Generated by LLM)', fontweight='bold')
                    ax1.set_ylabel('Number of Errors', color='tab:blue', fontweight='bold')
                    ax1.tick_params(axis='y', labelcolor='tab:blue')
                    
                    ax2 = ax1.twinx()
                    ax2.plot(pareto_data['Error Type'], pareto_data['Cumulative Percentage'], color='tab:red', marker='D', ms=5)
                    ax2.set_ylabel('Cumulative Percentage', color='tab:red', fontweight='bold')
                    ax2.yaxis.set_major_formatter(PercentFormatter())
                    ax2.tick_params(axis='y', labelcolor='tab:red')
                    
                    ax2.axhline(80, color='gray', linestyle='dashed', alpha=0.7)
                    
                    st.pyplot(fig2)
                    plt.close(fig2)  # <--- FIX 1: Closes memory leak for Pareto chart
            else:
                st.success("No conflicts detected by the LLM! All requirements are valid.")
        else:
            st.warning("⚠️ The backend did not return an 'error_category' column. The Pareto Chart requires this field to render.")
            
    else:
        st.info("Waiting for data... Please run the Local AI Validation Agent in the **Agent UI** tab to generate KPIs.")