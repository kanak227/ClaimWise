"""
Routing Rules API endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from services.routing_service import (
    get_all_rules,
    get_rule,
    create_rule,
    update_rule,
    delete_rule,
    apply_routing_rules
)
from services.pathway_pipeline import get_pathway_pipeline

router = APIRouter(prefix="/routing", tags=["Routing"])


class RuleCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    priority: Optional[int] = None
    condition_type: str  # fraud, severity, complexity, claim_type, fraud_threshold, combined
    condition_value: Optional[str] = None  # low, mid, high, accident, health
    claim_type: Optional[str] = None  # accident, health, or None for all
    routing_team: str
    adjuster: str
    operator: Optional[str] = None  # For fraud_threshold: >=, >, <=, <
    threshold: Optional[float] = None  # For fraud_threshold
    fraud_category: Optional[str] = None  # For combined conditions
    severity_category: Optional[str] = None  # For combined conditions
    complexity_category: Optional[str] = None  # For combined conditions


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    condition_type: Optional[str] = None
    condition_value: Optional[str] = None
    claim_type: Optional[str] = None
    routing_team: Optional[str] = None
    adjuster: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    fraud_category: Optional[str] = None
    severity_category: Optional[str] = None
    complexity_category: Optional[str] = None


class RoutingRequest(BaseModel):
    fraud_score: float
    complexity_score: float
    severity_level: str
    claim_category: str
    insurance_type: Optional[str] = "vehicle"


@router.get("/rules")
async def list_rules():
    """Get all routing rules"""
    return {"rules": get_all_rules()}


@router.get("/rules/{rule_id}")
async def get_rule_by_id(rule_id: str):
    """Get a specific routing rule"""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("/rules")
async def create_routing_rule(rule: RuleCreate):
    """Create a new routing rule"""
    try:
        rule_data = rule.model_dump(exclude_none=True)
        new_rule = create_rule(rule_data)
        return new_rule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_routing_rule(rule_id: str, rule: RuleUpdate):
    """Update an existing routing rule"""
    rule_data = rule.model_dump(exclude_none=True)
    updated_rule = update_rule(rule_id, rule_data)
    if not updated_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated_rule


@router.delete("/rules/{rule_id}")
async def delete_routing_rule(rule_id: str):
    """Delete a routing rule"""
    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted successfully"}


@router.post("/apply")
async def apply_routing(request: RoutingRequest):
    """Test routing rules against provided scores"""
    ml_scores = {
        "fraud_score": request.fraud_score,
        "complexity_score": request.complexity_score,
        "severity_level": request.severity_level,
        "claim_category": request.claim_category,
        "insurance_type": request.insurance_type,
    }
    
    claim_data = {
        "claim_number": f"test-{request.claim_category}",
        "analysis": {},
    }
    
    result = apply_routing_rules(ml_scores, claim_data=claim_data)
    return result


@router.post("/reroute")
async def reroute_claims(claims: List[Dict]):
    """Reroute existing claims when rules change (Pathway reactive feature)"""
    from services.pathway_pipeline import get_pathway_pipeline
    from services.claim_store import get_claim, reassign_claim
    
    pathway_pipeline = get_pathway_pipeline()
    if not pathway_pipeline:
        raise HTTPException(status_code=503, detail="Pathway pipeline not available")
    
    rerouted = pathway_pipeline.reroute_claims(claims)
    
    # Update stored claims with new routing
    updated_claims = []
    for rerouted_claim in rerouted:
        claim_id = rerouted_claim.get("claim_number") or rerouted_claim.get("claim_id")
        if claim_id:
            # Try to find claim by ID or claim_number
            stored_claim = get_claim(claim_id)
            if stored_claim:
                # Update routing in stored claim
                new_team = rerouted_claim.get("routing_team", "Fast Track")
                new_adjuster = rerouted_claim.get("adjuster", "Standard Adjuster")
                updated = reassign_claim(claim_id, new_team, new_adjuster, "Rerouted via Pathway")
                if updated:
                    updated_claims.append(updated)
    
    return {
        "rerouted_claims": rerouted,
        "updated_claims": updated_claims,
        "count": len(rerouted)
    }


@router.post("/reroute-all")
async def reroute_all_claims():
    """Reroute all existing claims based on current rules (Pathway reactive feature)"""
    from services.pathway_pipeline import get_pathway_pipeline
    from services.claim_store import list_claims, get_claim, reassign_claim
    
    pathway_pipeline = get_pathway_pipeline()
    if not pathway_pipeline:
        raise HTTPException(status_code=503, detail="Pathway pipeline not available")
    
    # Get all claims
    all_claims = list_claims()
    
    # Prepare claims for rerouting with ML scores
    claims_for_rerouting = []
    for claim in all_claims:
        ml_scores = claim.get("ml_scores", {})
        claims_for_rerouting.append({
            "claim_id": claim.get("id") or claim.get("claim_number"),
            "claim_number": claim.get("claim_number"),
            "fraud_score": ml_scores.get("fraud_score", 0.0),
            "complexity_score": ml_scores.get("complexity_score", 1.0),
            "severity_level": ml_scores.get("severity_level", "Low"),
            "claim_category": ml_scores.get("claim_category", claim.get("claim_type", "accident")),
        })
    
    # Reroute through Pathway
    rerouted = pathway_pipeline.reroute_claims(claims_for_rerouting)
    
    # Update stored claims
    updated_count = 0
    for rerouted_claim in rerouted:
        claim_id = rerouted_claim.get("claim_number") or rerouted_claim.get("claim_id")
        if claim_id:
            stored_claim = get_claim(claim_id)
            if stored_claim:
                new_team = rerouted_claim.get("routing_team", "Fast Track")
                new_adjuster = rerouted_claim.get("adjuster", "Standard Adjuster")
                updated = reassign_claim(claim_id, new_team, new_adjuster, "Bulk rerouted via Pathway")
                if updated:
                    updated_count += 1
    
    return {
        "message": f"Rerouted {updated_count} claims",
        "rerouted_count": len(rerouted),
        "updated_count": updated_count
    }


@router.get("/attributes")
async def get_rule_attributes():
    """Get available attributes for rule creation"""
    return {
        "condition_types": [
            "fraud",
            "severity",
            "complexity",
            "claim_type",
            "fraud_threshold",
            "combined"
        ],
        "condition_values": ["low", "mid", "high", "accident", "health"],
        "claim_types": ["accident", "health"],
        "operators": [">=", ">", "<=", "<"],
        "teams": [
            "Fast Track",
            "Standard Review",
            "Complex Claims",
            "SIU (Fraud)",
            "Litigation",
            "Subrogation",
            "Total Loss",
            "Bodily Injury"
        ]
    }

