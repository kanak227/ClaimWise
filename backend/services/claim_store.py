"""
Claim store backed by database persistence.
Used to back the Team Panel queues and claim list for the frontend.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import get_db_session
from .models import DBClaim


def _is_bad_number(v: Any) -> bool:
    """Return True if value is a non-finite number (nan/inf/-inf)."""
    return isinstance(v, float) and (math.isnan(v) or math.isinf(v))


def _sanitize(value: Any) -> Any:
    """Recursively sanitize a structure so the frontend never sees NaN/Infinity.

    Rules:
      - Replace NaN/Infinity with None
      - Leave ints/bools/strings untouched
      - Recurse into lists/dicts
    """
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [(_sanitize(v)) for v in value]
    if _is_bad_number(value):
        return None
    return value


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def add_claim(record: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update a claim record in the database."""
    claim_number = record.get("claim_number", "")
    claim_id = record.get("id") or claim_number or str(uuid.uuid4())
    
    db_claim = DBClaim(
        id=claim_id,
        claim_number=claim_number,
        claimant=record.get("claimant") or record.get("name") or "Unknown",
        policy_no=record.get("policy_no") or claim_number or "",
        loss_type=record.get("loss_type") or record.get("claim_type", "accident"),
        claim_type=record.get("claim_type", record.get("loss_type", "accident")),
        created_at=record.get("created_at") or _now_iso(),
        severity=record.get("severity") or record.get("severity_level") or "Low",
        severity_level=record.get("severity_level") or record.get("severity") or "Low",
        confidence=float(record.get("confidence", 0.9)),
        queue=record.get("queue") or record.get("routing_team") or record.get("final_team") or "Fast Track",
        routing_team=record.get("routing_team") or record.get("final_team") or record.get("queue") or "Fast Track",
        final_team=record.get("final_team") or record.get("routing_team") or record.get("queue") or "Fast Track",
        status=record.get("status") or "Processing",
        email=record.get("email"),
        description=record.get("description") or "",
        rationale=record.get("rationale") or "",
        assignee=record.get("assignee") or record.get("final_adjuster"),
        adjuster=record.get("adjuster") or record.get("final_adjuster") or record.get("assignee"),
        fraud_score=record.get("ml_scores", {}).get("fraud_score") if record.get("ml_scores") else None,
        complexity_score=record.get("ml_scores", {}).get("complexity_score") if record.get("ml_scores") else None,
    )
    
    db_claim.evidence = record.get("evidence") or []
    db_claim.ai_analysis = record.get("ai_analysis") or {}
    db_claim.sources = record.get("sources") or []
    db_claim.attachments = (
        record.get("attachments") if isinstance(record.get("attachments"), list) else
        ([{"filename": k, "url": v} for k, v in record.get("files", {}).items()] 
         if isinstance(record.get("files"), dict) else
         record.get("files") if isinstance(record.get("files"), list) else
         [])
    )
    db_claim.ml_scores = record.get("ml_scores") or {}
    db_claim.routing = record.get("routing") or {}
    db_claim.history = record.get("history") or []

    session = get_db_session()
    try:
        session.merge(db_claim)
        session.commit()
        return _sanitize(db_claim.to_dict())
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def list_claims(queue: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
    """List claims, optionally filtered by queue"""
    session = get_db_session()
    try:
        query = session.query(DBClaim)
        if queue:
            from sqlalchemy import func
            q_lower = queue.lower()
            query = query.filter(
                (func.lower(DBClaim.queue) == q_lower) |
                (func.lower(DBClaim.routing_team) == q_lower) |
                (func.lower(DBClaim.final_team) == q_lower)
            )
        
        query = query.order_by(DBClaim.created_at.desc())
        
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
            
        claims = query.all()
        return _sanitize([c.to_dict() for c in claims])
    finally:
        session.close()


def get_claim(claim_id: str) -> Optional[Dict[str, Any]]:
    """Get claim by ID or claim_number"""
    session = get_db_session()
    try:
        claim = session.query(DBClaim).filter(
            (DBClaim.id == claim_id) | (DBClaim.claim_number == claim_id)
        ).first()
        return _sanitize(claim.to_dict()) if claim else None
    finally:
        session.close()


def reassign_claim(claim_id: str, queue: str, assignee: Optional[str] = None, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Reassign claim to a different queue/team"""
    session = get_db_session()
    try:
        claim = session.query(DBClaim).filter(
            (DBClaim.id == claim_id) | (DBClaim.claim_number == claim_id)
        ).first()
        if claim:
            claim.queue = queue
            claim.routing_team = queue
            claim.final_team = queue
            if assignee:
                claim.assignee = assignee
                claim.adjuster = assignee
                
            # Append to history
            hist = list(claim.history)
            hist.append({
                "type": "reassign",
                "queue": queue,
                "assignee": assignee,
                "note": note,
                "at": _now_iso(),
            })
            claim.history = hist
            
            session.commit()
            return _sanitize(claim.to_dict())
        return None
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def queues_summary() -> List[Dict[str, Any]]:
    """Aggregate claims by queue for the Team Panel."""
    session = get_db_session()
    try:
        from sqlalchemy import func
        results = session.query(DBClaim.queue, func.count(DBClaim.id)).group_by(DBClaim.queue).all()
        
        counts: Dict[str, int] = {}
        for q, count in results:
            q_name = q or "Fast Track"
            counts[q_name] = counts.get(q_name, 0) + count
            
        result = []
        for name, count in sorted(counts.items(), key=lambda i: i[0]):
            result.append({
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "description": f"Queue for {name}",
                "claimCount": count,
                "averageProcessingTime": "--",
            })
        return result
    finally:
        session.close()


def clear_all_claims() -> int:
    """Clear all claims from the database."""
    session = get_db_session()
    try:
        count = session.query(DBClaim).delete()
        session.commit()
        return count
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
