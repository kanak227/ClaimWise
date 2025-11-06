from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict, Any

from services.claim_store import get_claim
from services.gemini_chat import chat_with_gemini


router = APIRouter(prefix="/api", tags=["Chat"])


Role = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


@router.post("/claims/{claim_id}/chat")
async def chat_claim(claim_id: str, req: ChatRequest):
    claim = get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Build a compact context from the claim to ground the model
    context: Dict[str, Any] = {
        "id": claim.get("id") or claim.get("claim_number") or claim_id,
        "claim_number": claim.get("claim_number") or claim.get("id") or claim_id,
        "claimant": claim.get("claimant") or claim.get("name"),
        "email": claim.get("email"),
        "policy_number": claim.get("policyNumber") or claim.get("policy_no"),
        "loss_type": claim.get("loss_type"),
        "severity": claim.get("severity") or claim.get("severity_level"),
        "queue": claim.get("queue"),
        "status": claim.get("status"),
        "created_at": claim.get("created_at"),
        # Selected extracts useful for Q&A
        "analyses": (claim.get("analyses") or {}),
        "ml_scores": claim.get("ml_scores") or {
            "fraud_score": claim.get("fraud_score"),
            "complexity_score": claim.get("complexity_score"),
            "severity_level": claim.get("severity_level"),
        },
    }

    answer = await chat_with_gemini(
        message=req.message,
        history=[m.model_dump() for m in (req.history or [])],
        claim_context=context,
    )
    return {"answer": answer}
