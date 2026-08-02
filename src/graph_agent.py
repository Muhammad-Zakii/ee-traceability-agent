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
    
    # Retrieve context
    docs = retriever.invoke(query)
    context = "\n".join([doc.page_content for doc in docs])
    
    # Analyze via Local LLM with Strict Engineering Rules
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict automotive E/E systems engineer validating hardware requirements.
        
        RULES FOR VALIDATION:
        1. VOLTAGE: If the requirement asks for a specific voltage (e.g., 48V) and the context specifies a different voltage (e.g., 12V), it is a CONFLICT.
        2. MISSING DATA: If the context does not explicitly support the requirement, it is a CONFLICT.
        3. ALIGNMENT: If the capabilities perfectly match, it is VALID.
        
        You MUST output your response in this exact format:
        STATUS: VALID (or CONFLICT)
        REASON: Your short explanation here.
        
        Do not output any other text."""),
        ("user", "Context: {context}\n\nRequirement: {requirement}")
    ])
    
    chain = prompt | llm
    
    print("🤖 Waiting for local Llama 3 response...")
    response = chain.invoke({"context": context, "requirement": query}).content
    print(f"📝 Raw Response: {response.strip()}")
    
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
        
    # Smart Reason Extraction
    notes = response
    if "REASON:" in response_upper:
        start_idx = response_upper.find("REASON:") + 7
        notes = response[start_idx:].strip()
    
    # Clean up any leftover status text in the notes
    notes = notes.replace("STATUS: CONFLICT", "").replace("STATUS: VALID", "").strip()
    if notes.startswith("-") or notes.startswith(":"):
        notes = notes[1:].strip()
        
    result = {
        "req_id": current_req.get("req_id", f"REQ-{idx}"),
        "component": current_req.get("component"),
        "status": status,
        "notes": notes
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