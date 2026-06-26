"""
Dynamic Routing Rules Service
Manages routing rules and applies them to route claims to teams
Now integrated with Pathway for reactive routing
"""
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .db import get_db_session
from .models import DBRule

logger = logging.getLogger(__name__)

# Import Pathway pipeline if available
try:
    from .pathway_pipeline import get_pathway_pipeline
    PATHWAY_AVAILABLE = True
except ImportError:
    PATHWAY_AVAILABLE = False
    logger.info("Pathway not available, using standard routing")


def load_rules_from_db() -> List[Dict[str, Any]]:
    """Load active rules from the database."""
    session = get_db_session()
    try:
        rules = session.query(DBRule).order_by(DBRule.priority.asc()).all()
        return [r.to_dict() for r in rules]
    except Exception as e:
        logger.warning(f"Failed to load rules from database: {e}")
        return []
    finally:
        session.close()


def normalize_rule_to_frontend(rule: dict) -> dict:
    """Ensure rule has both backend fields and frontend-compatible fields."""
    r = rule.copy()
    
    # Map backend -> frontend fields if missing
    if "attribute" not in r:
        cond_type = r.get("condition_type")
        if cond_type == "fraud_threshold":
            r["attribute"] = "fraud_score"
        elif cond_type == "fraud":
            r["attribute"] = "fraud_score"
        elif cond_type == "severity":
            r["attribute"] = "severity_level"
        elif cond_type == "complexity":
            r["attribute"] = "complexity_score"
        elif cond_type == "claim_type":
            r["attribute"] = "claim_category"
        else:
            r["attribute"] = cond_type or "fraud_score"
            
    if "operator" not in r or r["operator"] is None:
        r["operator"] = "="
        
    if "amount" not in r:
        if r.get("threshold") is not None:
            r["amount"] = r["threshold"]
        elif r.get("condition_value") is not None:
            val = r.get("condition_value")
            if val in ("low", "mid", "high"):
                mapping = {"low": 1.0, "mid": 2.0, "high": 3.0, "health": 1.0, "accident": 2.0}
                r["amount"] = mapping.get(str(val).lower(), 0.0)
            else:
                r["amount"] = 0.0
        else:
            r["amount"] = 0.0
            
    if "forward_to" not in r:
        r["forward_to"] = r.get("routing_team", "Fast Track")
        
    return r


def normalize_rule_to_backend(rule_data: dict) -> dict:
    """Map frontend fields to backend fields."""
    r = rule_data.copy()
    
    # Map frontend -> backend fields
    attr = r.get("attribute")
    if attr:
        if attr in ("fraud_score", "fraud"):
            r["condition_type"] = "fraud_threshold"
            r["threshold"] = r.get("amount", 0.0)
            r["operator"] = r.get("operator", ">=")
        elif attr in ("confidence_score", "confidence"):
            r["condition_type"] = "fraud_threshold"
            op = r.get("operator", "<")
            amt = r.get("amount", 0.5)
            r["threshold"] = 1.0 - amt
            if op == "<": r["operator"] = ">"
            elif op == "<=": r["operator"] = ">="
            elif op == ">": r["operator"] = "<"
            elif op == ">=": r["operator"] = "<="
            else: r["operator"] = ">"
        elif attr in ("severity_level", "severity"):
            r["condition_type"] = "severity"
            amt = r.get("amount", 0.0)
            if amt >= 3.0: r["condition_value"] = "high"
            elif amt >= 2.0: r["condition_value"] = "mid"
            else: r["condition_value"] = "low"
        elif attr in ("complexity_score", "complexity"):
            r["condition_type"] = "complexity"
            amt = r.get("amount", 0.0)
            r["threshold"] = amt
            if amt >= 3.0: r["condition_value"] = "high"
            elif amt >= 2.0: r["condition_value"] = "mid"
            else: r["condition_value"] = "low"
        elif attr in ("claim_category", "claim_type"):
            r["condition_type"] = "claim_type"
            amt = r.get("amount", 0.0)
            r["condition_value"] = "health" if amt == 1.0 else "accident"
            
    if "forward_to" in r:
        r["routing_team"] = r["forward_to"]
        
    if "priority" not in r:
        r["priority"] = 50
        
    if "adjuster" not in r:
        team = r.get("routing_team", "").lower()
        if "siu" in team or "fraud" in team:
            r["adjuster"] = "SIU Investigator"
        elif "complex" in team or "high" in team:
            r["adjuster"] = "Senior Adjuster"
        elif "standard" in team or "medium" in team:
            r["adjuster"] = "Standard Adjuster"
        else:
            r["adjuster"] = "Junior Adjuster"
            
    if not r.get("name"):
        r["name"] = f"Rule for {r.get('attribute', 'unknown')}"
    if not r.get("description"):
        r["description"] = f"Forward {r.get('attribute', 'unknown')} {r.get('operator', '=')} {r.get('amount', 0)} to {r.get('forward_to', 'Fast Track')}"
        
    return r


def get_score_category(score: float, thresholds: Dict[str, float]) -> str:
    """Categorize score as low/mid/high based on thresholds."""
    low_max = thresholds.get('low_max', 0.33)
    mid_max = thresholds.get('mid_max', 0.67)
    
    if score <= low_max:
        return 'low'
    elif score <= mid_max:
        return 'mid'
    else:
        return 'high'


def get_severity_category(severity: str) -> str:
    """Map severity level to category."""
    severity_lower = severity.lower() if severity else "low"
    if severity_lower == "high":
        return "high"
    elif severity_lower == "medium":
        return "mid"
    else:
        return "low"


def get_complexity_category(complexity: float) -> str:
    """Map complexity score to category."""
    if complexity <= 2.0:
        return "low"
    elif complexity <= 3.5:
        return "mid"
    else:
        return "high"


def match_rule_condition(
    rule: Dict[str, Any], fraud_cat: str, sev_cat: str, comp_cat: str,
    claim_type: str, fraud_score: float, complexity_score: float, severity_level: str
) -> bool:
    """Check if a claim matches a rule's condition."""
    if not rule.get("enabled", True):
        return False
        
    cond_type = rule.get("condition_type") or rule.get("attribute")
    if not cond_type:
        return False
        
    op = rule.get("operator", "=")
    threshold = rule.get("threshold")
    if threshold is None:
        threshold = rule.get("amount")
        
    def eval_num(val, op, thresh):
        try:
            val = float(val)
            thresh = float(thresh)
            if op == ">": return val > thresh
            if op == ">=": return val >= thresh
            if op == "<": return val < thresh
            if op == "<=": return val <= thresh
            if op in ("=", "=="): return val == thresh
            if op in ("!=", "<>"): return val != thresh
        except (ValueError, TypeError):
            pass
        return False

    if cond_type in ("fraud", "fraud_threshold", "fraud_score"):
        cond_val = rule.get("condition_value")
        if cond_val:
            if op in ("=", "=="):
                return fraud_cat == cond_val.lower()
            if op == "!=":
                return fraud_cat != cond_val.lower()
        if threshold is not None:
            return eval_num(fraud_score, op, threshold)
        return False
        
    elif cond_type in ("confidence_score", "confidence"):
        val = 1.0 - fraud_score
        if threshold is not None:
            return eval_num(val, op, threshold)
        return False
        
    elif cond_type in ("severity", "severity_score", "severity_level"):
        cond_val = rule.get("condition_value")
        if cond_val:
            if op in ("=", "=="):
                return sev_cat == cond_val.lower()
            if op == "!=":
                return sev_cat != cond_val.lower()
        if threshold is not None:
            t = float(threshold)
            if t <= 1.0:
                val_scaled = {"low": 0.2, "mid": 0.5, "high": 0.9}.get(sev_cat, 0.2)
                return eval_num(val_scaled, op, t)
            else:
                sev_num = {"low": 1.0, "mid": 2.0, "high": 3.0}.get(sev_cat, 1.0)
                return eval_num(sev_num, op, t)
        return False
        
    elif cond_type in ("complexity", "complexity_score"):
        cond_val = rule.get("condition_value")
        if cond_val:
            if op in ("=", "=="):
                return comp_cat == cond_val.lower()
            if op == "!=":
                return comp_cat != cond_val.lower()
        if threshold is not None:
            return eval_num(complexity_score, op, threshold)
        return False
        
    elif cond_type in ("claim_type", "claim_category"):
        val = claim_type
        if val == "medical": val = "health"
        cond_val = rule.get("condition_value") or rule.get("claim_type")
        if not cond_val and threshold is not None:
            cond_val = str(rule.get("amount") or "")
        if cond_val:
            cond_val_norm = "health" if cond_val.lower() in ("health", "medical") else "accident"
            if op in ("=", "=="):
                return val == cond_val_norm
            if op == "!=":
                return val != cond_val_norm
        return False
        
    elif cond_type == "combined":
        fraud_cond = rule.get("fraud_category")
        sev_cond = rule.get("severity_category")
        comp_cond = rule.get("complexity_category")
        
        match = True
        if fraud_cond and fraud_cat != fraud_cond.lower():
            match = False
        if sev_cond and sev_cat != sev_cond.lower():
            match = False
        if comp_cond and comp_cat != comp_cond.lower():
            match = False
        return match
        
    return False


def apply_routing_rules(ml_scores: Dict[str, Any], claim_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Apply routing rules: First by claim type (Health/Accident), then by severity/complexity (Low/Mid/High)"""
    fraud_score = ml_scores.get("fraud_score", 0.0)
    complexity_score = ml_scores.get("complexity_score", 1.0)
    severity_level = ml_scores.get("severity_level", "Low")
    claim_category = ml_scores.get("claim_category", "accident")
    claim_type = claim_data.get("claim_type", "accident") if claim_data else claim_category
    
    # Map claim type
    is_health = claim_type == "medical" or claim_category == "health" or claim_category == "medical"
    dept_name = "Health Dept" if is_health else "Accident Dept"
    
    # Categorize scores
    fraud_category = get_score_category(fraud_score, {"low_max": 0.33, "mid_max": 0.67, "high_max": 1.0})
    severity_category = get_severity_category(severity_level)
    complexity_category = get_complexity_category(complexity_score)
    
    # Load rules from DB
    routing_rules = load_rules_from_db()
    sorted_rules = sorted(routing_rules, key=lambda r: r.get("priority", 999))
    
    # Try to match rules first
    for rule in sorted_rules:
        if rule.get("enabled", True):
            if match_rule_condition(
                rule, fraud_category, severity_category, complexity_category,
                claim_type, fraud_score, complexity_score, severity_level
            ):
                routing_team = rule.get("routing_team") or rule.get("forward_to")
                adjuster = rule.get("adjuster")
                if routing_team:
                    if not adjuster:
                        if "siu" in routing_team.lower() or "fraud" in routing_team.lower():
                            adjuster = "SIU Investigator"
                        elif "complex" in routing_team.lower() or "high" in routing_team.lower():
                            adjuster = "Senior Adjuster"
                        elif "standard" in routing_team.lower() or "medium" in routing_team.lower():
                            adjuster = "Standard Adjuster"
                        else:
                            adjuster = "Junior Adjuster"
                    
                    reason = rule.get("description") or rule.get("name") or f"Routed by rule: {rule.get('id')}"
                    result = {
                        "routing_team": routing_team,
                        "adjuster": adjuster,
                        "routing_reasons": [reason],
                        "routing_reason": reason,
                        "matched_rule_id": rule.get("id"),
                        "rule_applied": True
                    }
                    
                    # Pathway pipeline check
                    if PATHWAY_AVAILABLE and claim_data:
                        pathway_pipeline = get_pathway_pipeline()
                        if pathway_pipeline:
                            try:
                                pathway_result = pathway_pipeline.process_claim(claim_data, ml_scores)
                                result.update({
                                    "routing_team": pathway_result.get("routing_team", routing_team),
                                    "adjuster": pathway_result.get("adjuster", adjuster),
                                    "matched_rule_id": pathway_result.get("matched_rule_id", rule.get("id")),
                                    "routing_reason": pathway_result.get("routing_reason", reason),
                                    "routing_reasons": [pathway_result.get("routing_reason", reason)],
                                    "rules_version": pathway_result.get("rules_version", 0),
                                    "pathway_processed": True,
                                })
                            except Exception as e:
                                logger.warning(f"Pathway routing failed: {e}")
                    return result

    # Default fallback routing logic
    if severity_category == "high" or complexity_category == "high":
        level = "High"
    elif severity_category == "mid" or complexity_category == "mid":
        level = "Mid"
    else:
        level = "Low"
    
    if fraud_score >= 0.6:
        routing_team = "SIU (Fraud)"
        adjuster = "SIU Investigator"
        routing_reason = f"Fraud score is {(fraud_score * 100):.1f}% so routed to this team"
    else:
        routing_team = f"{dept_name} - {level}"
        if level == "High":
            adjuster = "Senior Adjuster"
        elif level == "Mid":
            adjuster = "Standard Adjuster"
        else:
            adjuster = "Junior Adjuster"
        
        routing_reason = f"Complexity score is {complexity_score:.1f} and Severity score is {severity_level} so routed to this team"
    
    result = {
        "routing_team": routing_team,
        "adjuster": adjuster,
        "routing_reasons": [routing_reason],
        "routing_reason": routing_reason,
        "rule_applied": False
    }
    
    if PATHWAY_AVAILABLE and claim_data:
        pathway_pipeline = get_pathway_pipeline()
        if pathway_pipeline:
            try:
                pathway_result = pathway_pipeline.process_claim(claim_data, ml_scores)
                result.update({
                    "routing_team": pathway_result.get("routing_team", routing_team),
                    "adjuster": pathway_result.get("adjuster", adjuster),
                    "matched_rule_id": pathway_result.get("matched_rule_id"),
                    "routing_reason": pathway_result.get("routing_reason", routing_reason),
                    "routing_reasons": [pathway_result.get("routing_reason", routing_reason)],
                    "rules_version": pathway_result.get("rules_version", 0),
                    "pathway_processed": True,
                })
            except Exception as e:
                logger.warning(f"Pathway routing failed, using fallback: {e}")
    
    return result


def get_all_rules() -> List[Dict[str, Any]]:
    """Get all routing rules"""
    rules = load_rules_from_db()
    return [normalize_rule_to_frontend(r) for r in rules]


def get_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific rule by ID"""
    session = get_db_session()
    try:
        rule = session.query(DBRule).filter(DBRule.id == rule_id).first()
        return normalize_rule_to_frontend(rule.to_dict()) if rule else None
    finally:
        session.close()


def create_rule(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new routing rule"""
    rule_id = str(uuid.uuid4())
    backend_data = normalize_rule_to_backend(rule_data)
    
    db_rule = DBRule(
        id=rule_id,
        name=backend_data.get("name", ""),
        description=backend_data.get("description", ""),
        enabled=backend_data.get("enabled", True),
        priority=backend_data.get("priority", 50),
        condition_type=backend_data.get("condition_type"),
        condition_value=backend_data.get("condition_value"),
        claim_type=backend_data.get("claim_type"),
        routing_team=backend_data.get("routing_team", "Fast Track"),
        adjuster=backend_data.get("adjuster", "Standard Adjuster"),
        operator=backend_data.get("operator"),
        threshold=backend_data.get("threshold"),
        fraud_category=backend_data.get("fraud_category"),
        severity_category=backend_data.get("severity_category"),
        complexity_category=backend_data.get("complexity_category"),
        attribute=backend_data.get("attribute"),
        amount=backend_data.get("amount"),
        forward_to=backend_data.get("forward_to"),
        created_at=datetime.utcnow().isoformat() + "Z",
        updated_at=datetime.utcnow().isoformat() + "Z",
    )
    
    session = get_db_session()
    try:
        session.add(db_rule)
        session.commit()
        
        # Fetch updated rules to sync Pathway
        all_rules = [r.to_dict() for r in session.query(DBRule).all()]
        if PATHWAY_AVAILABLE:
            pathway_pipeline = get_pathway_pipeline()
            if pathway_pipeline:
                pathway_pipeline.update_rules(all_rules)
                logger.info(f"Updated Pathway pipeline with new rule: {rule_id}")
                
        return normalize_rule_to_frontend(db_rule.to_dict())
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def update_rule(rule_id: str, rule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing routing rule"""
    session = get_db_session()
    try:
        db_rule = session.query(DBRule).filter(DBRule.id == rule_id).first()
        if not db_rule:
            return None
            
        backend_data = normalize_rule_to_backend(rule_data)
        for key, value in backend_data.items():
            if key not in ["id", "created_at"]:
                setattr(db_rule, key, value)
        db_rule.updated_at = datetime.utcnow().isoformat() + "Z"
        session.commit()
        
        # Sync with Pathway
        all_rules = [r.to_dict() for r in session.query(DBRule).all()]
        if PATHWAY_AVAILABLE:
            pathway_pipeline = get_pathway_pipeline()
            if pathway_pipeline:
                pathway_pipeline.update_rules(all_rules)
                logger.info(f"Pathway pipeline updated - rules will trigger reactive rerouting")
                try:
                    from .claim_store import list_claims, get_claim, reassign_claim
                    all_claims = list_claims()
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
                    
                    if claims_for_rerouting:
                        rerouted = pathway_pipeline.reroute_claims(claims_for_rerouting)
                        for rerouted_claim in rerouted:
                            claim_id = rerouted_claim.get("claim_number") or rerouted_claim.get("claim_id")
                            if claim_id:
                                stored_claim = get_claim(claim_id)
                                if stored_claim:
                                    new_team = rerouted_claim.get("routing_team", "Fast Track")
                                    new_adjuster = rerouted_claim.get("adjuster", "Standard Adjuster")
                                    reassign_claim(claim_id, new_team, new_adjuster, f"Auto-rerouted after rule update: {rule_id}")
                        logger.info(f"Auto-rerouted {len(rerouted)} claims after rule update")
                except Exception as e:
                    logger.warning(f"Failed to auto-reroute claims after rule update: {e}")
                    
        return normalize_rule_to_frontend(db_rule.to_dict())
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_rule(rule_id: str) -> bool:
    """Delete a routing rule"""
    session = get_db_session()
    try:
        db_rule = session.query(DBRule).filter(DBRule.id == rule_id).first()
        if not db_rule:
            return False
            
        session.delete(db_rule)
        session.commit()
        
        # Sync with Pathway
        all_rules = [r.to_dict() for r in session.query(DBRule).all()]
        if PATHWAY_AVAILABLE:
            pathway_pipeline = get_pathway_pipeline()
            if pathway_pipeline:
                pathway_pipeline.update_rules(all_rules)
                logger.info(f"Pathway pipeline updated after rule deletion")
                
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def initialize_default_rules():
    """Initialize default routing rules if none exist in DB"""
    session = get_db_session()
    try:
        if session.query(DBRule).count() > 0:
            return
    finally:
        session.close()
        
    default_rules = [
        {
            "name": "High Fraud - All Categories",
            "description": "Route high fraud claims to SIU team",
            "enabled": True,
            "priority": 1,
            "condition_type": "fraud_threshold",
            "operator": ">=",
            "threshold": 0.6,
            "routing_team": "SIU (Fraud)",
            "adjuster": "SIU Investigator",
        },
        {
            "name": "High Fraud - Vehicle",
            "description": "Route high fraud vehicle claims",
            "enabled": True,
            "priority": 2,
            "condition_type": "fraud",
            "condition_value": "high",
            "claim_type": "accident",
            "routing_team": "SIU (Fraud)",
            "adjuster": "SIU Investigator",
        },
        {
            "name": "High Fraud - Health",
            "description": "Route high fraud health claims",
            "enabled": True,
            "priority": 2,
            "condition_type": "fraud",
            "condition_value": "high",
            "claim_type": "health",
            "routing_team": "SIU (Fraud)",
            "adjuster": "SIU Investigator",
        },
        {
            "name": "High Severity - Vehicle",
            "description": "Route high severity vehicle claims to Complex Claims",
            "enabled": True,
            "priority": 10,
            "condition_type": "severity",
            "condition_value": "high",
            "claim_type": "accident",
            "routing_team": "Complex Claims",
            "adjuster": "Senior Adjuster",
        },
        {
            "name": "High Severity - Health",
            "description": "Route high severity health claims to Complex Claims",
            "enabled": True,
            "priority": 10,
            "condition_type": "severity",
            "condition_value": "high",
            "claim_type": "health",
            "routing_team": "Complex Claims",
            "adjuster": "Senior Adjuster",
        },
        {
            "name": "High Complexity - Vehicle",
            "description": "Route high complexity vehicle claims",
            "enabled": True,
            "priority": 15,
            "condition_type": "complexity",
            "condition_value": "high",
            "claim_type": "accident",
            "routing_team": "Complex Claims",
            "adjuster": "Senior Adjuster",
        },
        {
            "name": "High Complexity - Health",
            "description": "Route high complexity health claims",
            "enabled": True,
            "priority": 15,
            "condition_type": "complexity",
            "condition_value": "high",
            "claim_type": "health",
            "routing_team": "Complex Claims",
            "adjuster": "Senior Adjuster",
        },
        {
            "name": "Mid Fraud - Vehicle",
            "description": "Route mid fraud vehicle claims",
            "enabled": True,
            "priority": 20,
            "condition_type": "fraud",
            "condition_value": "mid",
            "claim_type": "accident",
            "routing_team": "Standard Review",
            "adjuster": "Standard Adjuster",
        },
        {
            "name": "Mid Fraud - Health",
            "description": "Route mid fraud health claims",
            "enabled": True,
            "priority": 20,
            "condition_type": "fraud",
            "condition_value": "mid",
            "claim_type": "health",
            "routing_team": "Standard Review",
            "adjuster": "Standard Adjuster",
        },
        {
            "name": "Low Risk - Default",
            "description": "Default routing for low risk claims",
            "enabled": True,
            "priority": 100,
            "condition_type": "fraud",
            "condition_value": "low",
            "routing_team": "Fast Track",
            "adjuster": "Standard Adjuster",
        },
    ]
    
    for rule_data in default_rules:
        create_rule(rule_data)
    
    logger.info("Initialized default routing rules in database")


def init_routing_service():
    """Startup initialization of database routing rules and synchronization with Pathway pipeline."""
    initialize_default_rules()
    if PATHWAY_AVAILABLE:
        try:
            pathway_pipeline = get_pathway_pipeline()
            if pathway_pipeline:
                rules = load_rules_from_db()
                if rules:
                    pathway_pipeline.update_rules(rules)
                    logger.info(f"Initialized Pathway pipeline with {len(rules)} rules from database")
        except Exception as e:
            logger.warning(f"Failed to initialize Pathway with rules: {e}")
