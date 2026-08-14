"""
SmartResolve AI - FastAPI Backend REST Service
Provides high-performance RESTful endpoints for autonomous support ticket triage.
Interactive Swagger API documentation available at: http://localhost:8000/docs
"""

import os
from typing import List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.models import TicketInput, TriageOutput, BatchSummary
from src.agent import SupportTicketAgent
from src.router import CONFIDENCE_THRESHOLD

app = FastAPI(
    title="SmartResolve AI - Backend REST API",
    description="Autonomous Support Ticket Triage, Urgency Classification & Routing Engine API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agent
agent = SupportTicketAgent(confidence_threshold=CONFIDENCE_THRESHOLD)


@app.get("/", tags=["Health & Info"])
def root():
    """Root status and API overview."""
    return {
        "service": "SmartResolve AI Backend API",
        "status": "online",
        "version": "1.0.0",
        "engine_mode": "LLM Connected" if agent.is_llm_available else "Heuristic NLP Mode (Offline/No Key)",
        "confidence_threshold": agent.confidence_threshold,
        "swagger_docs": "http://localhost:8000/docs",
        "redoc_docs": "http://localhost:8000/redoc"
    }


@app.get("/health", tags=["Health & Info"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "is_llm_available": agent.is_llm_available,
        "threshold": agent.confidence_threshold
    }


@app.post("/api/v1/triage", response_model=TriageOutput, tags=["Triage Operations"])
def triage_single_ticket(
    ticket: TicketInput,
    threshold: float = Query(default=CONFIDENCE_THRESHOLD, ge=0.0, le=1.0, description="Override confidence threshold")
):
    """
    Triage a single support ticket.
    Returns classified category, urgency, confidence score, assigned team, explainable reason, and recommended action.
    """
    try:
        custom_agent = SupportTicketAgent(confidence_threshold=threshold) if threshold != agent.confidence_threshold else agent
        result = custom_agent.triage(ticket)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage execution failed: {str(e)}")


@app.post("/api/v1/triage/batch", tags=["Triage Operations"])
def triage_batch_tickets(
    tickets: List[TicketInput],
    threshold: float = Query(default=CONFIDENCE_THRESHOLD, ge=0.0, le=1.0, description="Override confidence threshold")
):
    """
    Batch triage multiple support tickets.
    Returns a list of structured triage outputs alongside aggregate KPI metrics.
    """
    if not tickets:
        raise HTTPException(status_code=400, detail="Ticket list cannot be empty.")

    try:
        custom_agent = SupportTicketAgent(confidence_threshold=threshold) if threshold != agent.confidence_threshold else agent
        results, summary = custom_agent.triage_batch(tickets)
        return {
            "summary": summary.model_dump(),
            "results": [r.model_dump() for r in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch triage execution failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
