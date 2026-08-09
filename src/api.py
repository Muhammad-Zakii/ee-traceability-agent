from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from src.graph_agent import traceability_agent

# Import your new vector store processing function
from src.vector_store import process_and_store_multiple_pdfs

app = FastAPI(title="E/E Traceability API")

class ValidationRequest(BaseModel):
    requirements: List[Dict]

# --- NEW ENDPOINT: Multi-PDF Upload ---
@app.post("/upload-pdfs")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    try:
        # Pass the list of uploaded files directly to your processing logic
        await process_and_store_multiple_pdfs(files)
        return {"status": "success", "message": f"Successfully ingested {len(files)} documents into ChromaDB."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- EXISTING ENDPOINT: Validation ---
@app.post("/validate")
async def validate_requirements(request: ValidationRequest):
    initial_state = {
        "requirements_to_check": request.requirements,
        "current_index": 0,
        "analysis_results": [],
        "final_report_path": ""
    }
    
    # Run LangGraph workflow
    final_state = traceability_agent.invoke(initial_state)
    
    return {
        "status": "success",
        "report_path": final_state["final_report_path"],
        "results": final_state["analysis_results"]
    }