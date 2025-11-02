from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from services.claim_store import list_claims, get_claim, reassign_claim, queues_summary


router = APIRouter(prefix="/api", tags=["Claims"])


@router.get("/claims")
async def api_list_claims(
    queue: Optional[str] = Query(None, description="Filter by queue/team name"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
    offset: Optional[int] = Query(None, description="Offset for pagination"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    search: Optional[str] = Query(None, description="Search in claim number, name, or email"),
):
    """List all claims with optional filtering"""
    claims = list_claims(queue=queue, limit=limit, offset=offset)
    
    # Additional filtering by severity if provided
    if severity:
        claims = [c for c in claims if (
            c.get("severity", "").lower() == severity.lower() or
            c.get("severity_level", "").lower() == severity.lower()
        )]
    
    # Search filtering if provided
    if search:
        search_lower = search.lower()
        claims = [c for c in claims if (
            search_lower in c.get("claim_number", "").lower() or
            search_lower in c.get("name", "").lower() or
            search_lower in c.get("claimant", "").lower() or
            search_lower in c.get("email", "").lower()
        )]
    
    return claims


@router.get("/claims/{claim_id}")
async def api_get_claim(claim_id: str):
    claim = get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


class ReassignRequest(BaseModel):
    queue: str
    assignee: Optional[str] = None
    note: Optional[str] = None


@router.post("/claims/{claim_id}/reassign")
async def api_reassign_claim(claim_id: str, req: ReassignRequest):
    updated = reassign_claim(claim_id, req.queue, req.assignee, req.note)
    if not updated:
        raise HTTPException(status_code=404, detail="Claim not found")
    return updated


@router.get("/queues")
async def api_list_queues():
    return queues_summary()
