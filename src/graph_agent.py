import time
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from src.vector_store import get_retriever
from src.excel_exporter import export_traceability_matrix
from src.config import LLM_MODEL

# 1. Define the State
class AgentState(TypedDict):
    requirements_to_check: List[Dict] 
    current_index: int
    analysis_results: List[Dict]
    final_report_path: str

# 2. Initialize Local LLM with Speed Limits
llm = ChatOllama(
    model=LLM_MODEL, 
    temperature=0,
    num_predict=128 # Limits response length so Llama 3 finishes fast
)
retriever = get_retriever()

# 3. Node Functions
def retrieve_and_analyze(state: AgentState):
    reqs = state["requirements_to_check"]
    idx = state.get("current_index", 0)
    results = state.get("analysis_results", [])
    
    if idx >= len(reqs):
        print("✅ All requirements processed.")
        return state 
        
    current_req = reqs[idx]
    print(f"\n🔄 [Step {idx+1}/{len(reqs)}] Analyzing: {current_req['req_id']} - {current_req['component']}...")
    
    query = f"Component: {current_req['component']}, Requirement: {current_req['description']}"
    
    # --- RAG TRACKING & METADATA INJECTION ---
    docs = retriever.invoke(query)
    rag_context_found = len(docs) > 0 
    
    # NEW: We now inject the exact filename from ChromaDB metadata into the text the AI reads!
    context_parts = []
    for doc in docs:
        source_file = doc.metadata.get("source", "Unknown Document")
        context_parts.append(f"Content: {doc.page_content}\nSource File: {source_file}")
    context = "\n\n".join(context_parts)
    
    # Analyze via Local LLM with Strict Engineering Rules
    # NEW: Added 'SOURCE' to both the rules and the output format
    # Analyze via Local LLM with Strict Engineering Rules
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict automotive E/E systems engineer validating hardware requirements.
        
        RULES FOR VALIDATION:
        1. EXACT METRIC MATCHING: You must evaluate the EXACT metric requested (e.g., Power, Temperature, Voltage, Protocol). Do NOT substitute one metric for another (e.g., do not evaluate voltage if the requirement asks for power).
        2. CONFLICT DETECTED: If the document explicitly states a value that violates the limit in the requirement (e.g., req says < 5W, but document says 8.5W), it is a CONFLICT.
        3. MISSING DATA: If the context does not explicitly mention the metric requested, it is a CONFLICT (e.g., Missing Spec).
        4. VALID: If the document's capabilities perfectly align with or support the requirement, it is VALID.
        5. SOURCE TRACKING: You must identify which 'Source File' provided the information used to make your decision.
        
        You MUST output your response in this exact format:
        STATUS: VALID (or CONFLICT)
        CATEGORY: If CONFLICT, provide a 2-3 word category (e.g., Power Mismatch, Voltage Mismatch). If VALID, output None.
        SOURCE: The exact name of the source file (e.g., document.pdf). If not found, output Unknown.
        REASON: Your short explanation here.
        
        Do not output any other text."""),
        ("user", "Context: {context}\n\nRequirement: {requirement}")
    ])
    
    chain = prompt | llm
    
    print("🤖 Waiting for local Llama 3 response...")
    
    # --- LATENCY TRACKING ---
    start_time = time.time()
    response = chain.invoke({"context": context, "requirement": query}).content
    end_time = time.time()
    
    execution_time = round(end_time - start_time, 2)
    print(f"📝 Raw Response:\n{response.strip()}")
    
    # --- BULLETPROOF PARSING LOGIC ---
    response_upper = response.upper()
    
    # Smart Status Detection
    if "STATUS: CONFLICT" in response_upper:
        status = "CONFLICT"
    elif "STATUS: VALID" in response_upper:
        status = "VALID"
    elif "NO CONFLICT" in response_upper:
        status = "VALID"
    elif "CONFLICT" in response_upper:
        status = "CONFLICT"
    elif "VALID" in response_upper:
        status = "VALID"
    else:
        status = "UNKNOWN"

    # Smart Category Extraction
    error_category = "None"
    for line in response.split('\n'):
        if line.upper().startswith("CATEGORY:"):
            error_category = line[9:].strip()
            break
            
    # NEW: Smart Source Extraction
    source_document = "Unknown"
    for line in response.split('\n'):
        if line.upper().startswith("SOURCE:"):
            source_document = line[7:].strip()
            break
            
    # Smart Reason Extraction
    notes = response
    if "REASON:" in response_upper:
        start_idx = response_upper.find("REASON:") + 7
        notes = response[start_idx:].strip()
    
    # Clean up any leftover status, category, or source text in the notes
    notes = notes.replace("STATUS: CONFLICT", "").replace("STATUS: VALID", "").strip()
    clean_notes = []
    for line in notes.split('\n'):
        if not (line.upper().startswith("CATEGORY:") or line.upper().startswith("SOURCE:")):
            clean_notes.append(line)
    notes = "\n".join(clean_notes).strip()
        
    if notes.startswith("-") or notes.startswith(":"):
        notes = notes[1:].strip()
        
    # --- FINAL RESULT PAYLOAD ---
    result = {
        "req_id": current_req.get("req_id", f"REQ-{idx}"),
        "component": current_req.get("component"),
        "status": status,
        "reasoning": notes,
        "latency_seconds": execution_time,       
        "rag_context_found": rag_context_found,  
        "error_category": error_category,         
        "source_document": source_document       # NEW: Adding source document to the output!
    }
    
    results.append(result)
    return {"analysis_results": results, "current_index": idx + 1}

def generate_report(state: AgentState):
    print("\n📊 Generating Excel Traceability Matrix Report...")
    results = state["analysis_results"]
    filepath = export_traceability_matrix(results)
    print(f"🎉 Excel saved at: {filepath}")
    return {"final_report_path": filepath}

# 4. Routing Logic
def check_continue(state: AgentState):
    if state["current_index"] < len(state["requirements_to_check"]):
        return "continue"
    return "end"

# 5. Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("analyze_node", retrieve_and_analyze)
workflow.add_node("report_node", generate_report)

workflow.set_entry_point("analyze_node")
workflow.add_conditional_edges(
    "analyze_node", check_continue, {"continue": "analyze_node", "end": "report_node"}
)
workflow.add_edge("report_node", END)

traceability_agent = workflow.compile()