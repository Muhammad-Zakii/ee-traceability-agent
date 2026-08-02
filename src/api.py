from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from src.graph_agent import traceability_agent

app = FastAPI(title="E/E Traceability API")

class ValidationRequest(BaseModel):
    requirements: List[Dict]

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