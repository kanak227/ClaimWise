"""
Dynamic Routing Rules Service
Manages routing rules and applies them to route claims to teams
Now integrated with Pathway for reactive routing
"""
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# In-memory storage for routing rules
_routing_rules: List[Dict[str, Any]] = []

# File path for persistence (optional)
RULES_FILE = Path(__file__).parent.parent / "routing_rules.json"

# Import Pathway pipeline if available
try:
    from .pathway_pipeline import get_pathway_pipeline
    PATHWAY_AVAILABLE = True
except ImportError:
    PATHWAY_AVAILABLE = False
    logger.info("Pathway not available, using standard routing")


def _load_rules_from_file():
    """Load rules from JSON file if it exists"""
    global _routing_rules
    if RULES_FILE.exists():
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                _routing_rules = json.load(f)
            logger.info(f"Loaded {len(_routing_rules)} routing rules from file")
        except Exception as e:
            logger.warning(f"Failed to load rules from file: {e}")
            _routing_rules = []
    else:
        _routing_rules = []


def _save_rules_to_file():
    """Save rules to JSON file"""
    try:
        RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(_routing_rules, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(_routing_rules)} routing rules to file")
    except Exception as e:
        logger.warning(f"Failed to save rules to file: {e}")


# Load rules on module import
_load_rules_from_file()


def get_score_category(score: float, thresholds: Dict[str, float]) -> str:
    """
    Categorize score as low/mid/high based on thresholds
    
    Args:
        score: The score value
        thresholds: Dict with 'low_max', 'mid_max', 'high_max' keys
    
    Returns:
        'low', 'mid', or 'high'
    """
    low_max = thresholds.get('low_max', 0.33)
    mid_max = thresholds.get('mid_max', 0.67)
    
    if score <= low_max:
        return 'low'
    elif score <= mid_max:
        return 'mid'
    else:
        return 'high'


def get_severity_category(severity: str) -> str:
    """Map severity level to category"""
    severity_lower = severity.lower() if severity else "low"
    if severity_lower == "high":
        return "high"
    elif severity_lower == "medium":
        return "mid"
    else:
        return "low"


def get_complexity_category(complexity: float) -> str:
    """Map complexity score to category"""
    if complexity <= 2.0:
        return "low"
    elif complexity <= 3.5:
        return "mid"
    else:
        return "high"


def apply_routing_rules(ml_scores: Dict[str, Any], claim_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Apply routing rules: First by claim type (Health/Accident), then by severity/complexity (Low/Mid/High)
    
    Args:
        ml_scores: ML scoring results with fraud_score, complexity_score, severity_level, claim_category
    
    Returns:
        Dict with routing_team, adjuster, and routing_reasons formatted as: 
        "Complexity score is X and Severity score is Y so routed to this team"
    """
    fraud_score = ml_scores.get("fraud_score", 0.0)
    complexity_score = ml_scores.get("complexity_score", 1.0)
    severity_level = ml_scores.get("severity_level", "Low")
    claim_category = ml_scores.get("claim_category", "accident")
    claim_type = claim_data.get("claim_type", "accident") if claim_data else claim_category
    
    # Map claim type
    is_health = claim_type == "medical" or claim_category == "health"
    dept_name = "Health Dept" if is_health else "Accident Dept"
    
    # Categorize scores
    fraud_category = get_score_category(fraud_score, {"low_max": 0.33, "mid_max": 0.67, "high_max": 1.0})
    severity_category = get_severity_category(severity_level)
    complexity_category = get_complexity_category(complexity_score)
    
    # Determine level based on severity and complexity (higher takes precedence)
    # High: severity=high OR complexity>=3.5
    # Mid: severity=mid OR (complexity>=2 and complexity<3.5)
    # Low: everything else
    if severity_category == "high" or complexity_category == "high":
        level = "High"
    elif severity_category == "mid" or complexity_category == "mid":
        level = "Mid"
    else:
        level = "Low"
    
    # Check for high fraud first (overrides everything)
    if fraud_score >= 0.6:
        routing_team = "SIU (Fraud)"
        adjuster = "SIU Investigator"
        routing_reason = f"Fraud score is {(fraud_score * 100).toFixed(1)}% so routed to this team"
    else:
        # Route by department and level
        routing_team = f"{dept_name} - {level}"
        if level == "High":
            adjuster = "Senior Adjuster"
        elif level == "Mid":
            adjuster = "Standard Adjuster"
        else:
            adjuster = "Junior Adjuster"
        
        # Format routing reason
        routing_reason = f"Complexity score is {complexity_score:.1f} and Severity score is {severity_level} so routed to this team"
    
    result = {
        "routing_team": routing_team,
        "adjuster": adjuster,
        "routing_reasons": [routing_reason],
        "routing_reason": routing_reason,  # Single reason string for compatibility
        "rule_applied": True
    }
    
    # If Pathway is available, use it for reactive routing
    if PATHWAY_AVAILABLE and claim_data:
        pathway_pipeline = get_pathway_pipeline()
        if pathway_pipeline:
            try:
                pathway_result = pathway_pipeline.process_claim(claim_data, ml_scores)
                # Use Pathway result (which may have reactive updates)
                result.update({
                    "routing_team": pathway_result.get("routing_team", routing_team),
                    "adjuster": pathway_result.get("adjuster", adjuster),
                    "matched_rule_id": pathway_result.get("matched_rule_id"),
                    "routing_reason": pathway_result.get("routing_reason", routing_reason),
                    "routing_reasons": [pathway_result.get("routing_reason", routing_reason)],
                    "rules_version": pathway_result.get("rules_version", 0),
                    "pathway_processed": True,
                })
                logger.debug("Claim routed via Pathway pipeline")
            except Exception as e:
                logger.warning(f"Pathway routing failed, using fallback: {e}")
    
    return result


def get_all_rules() -> List[Dict[str, Any]]:
    """Get all routing rules"""
    return _routing_rules.copy()


def get_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific rule by ID"""
    for rule in _routing_rules:
        if rule.get("id") == rule_id:
            return rule.copy()
    return None


def create_rule(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new routing rule"""
    rule_id = str(uuid.uuid4())
    rule = {
        "id": rule_id,
        "name": rule_data.get("name", ""),
        "description": rule_data.get("description", ""),
        "enabled": rule_data.get("enabled", True),
        "priority": rule_data.get("priority", len(_routing_rules)),
        "condition_type": rule_data.get("condition_type"),  # fraud, severity, complexity, claim_type, fraud_threshold, combined
        "condition_value": rule_data.get("condition_value"),  # low, mid, high, accident, health
        "claim_type": rule_data.get("claim_type"),  # accident, health, or None for all
        "routing_team": rule_data.get("routing_team", "Fast Track"),
        "adjuster": rule_data.get("adjuster", "Standard Adjuster"),
        "operator": rule_data.get("operator"),  # For fraud_threshold: >=, >, <=, <
        "threshold": rule_data.get("threshold"),  # For fraud_threshold
        "fraud_category": rule_data.get("fraud_category"),  # For combined conditions
        "severity_category": rule_data.get("severity_category"),  # For combined conditions
        "complexity_category": rule_data.get("complexity_category"),  # For combined conditions
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    
    _routing_rules.append(rule)
    _save_rules_to_file()
    
    # Update Pathway pipeline if available
    if PATHWAY_AVAILABLE:
        pathway_pipeline = get_pathway_pipeline()
        if pathway_pipeline:
            pathway_pipeline.update_rules(_routing_rules)
            logger.info(f"Updated Pathway pipeline with new rule: {rule_id}")
    
    logger.info(f"Created routing rule: {rule_id}")
    return rule


def update_rule(rule_id: str, rule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing routing rule"""
    for i, rule in enumerate(_routing_rules):
        if rule.get("id") == rule_id:
            # Update fields
            for key, value in rule_data.items():
                if key not in ["id", "created_at"]:
                    rule[key] = value
            rule["updated_at"] = datetime.now().isoformat()
            _save_rules_to_file()
            
            # Update Pathway pipeline if available (triggers reactive rerouting)
            if PATHWAY_AVAILABLE:
                pathway_pipeline = get_pathway_pipeline()
                if pathway_pipeline:
                    pathway_pipeline.update_rules(_routing_rules)
                    logger.info(f"Pathway pipeline updated - rules will trigger reactive rerouting")
                    # Optionally trigger rerouting of existing claims
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
                            # Update stored claims
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
            
            logger.info(f"Updated routing rule: {rule_id}")
            return rule.copy()
    return None


def delete_rule(rule_id: str) -> bool:
    """Delete a routing rule"""
    global _routing_rules
    initial_count = len(_routing_rules)
    _routing_rules = [r for r in _routing_rules if r.get("id") != rule_id]
    
    if len(_routing_rules) < initial_count:
        _save_rules_to_file()
        
        # Update Pathway pipeline if available (triggers reactive rerouting)
        if PATHWAY_AVAILABLE:
            pathway_pipeline = get_pathway_pipeline()
            if pathway_pipeline:
                pathway_pipeline.update_rules(_routing_rules)
                logger.info(f"Pathway pipeline updated after rule deletion")
        
        logger.info(f"Deleted routing rule: {rule_id}")
        return True
    return False


def initialize_default_rules():
    """Initialize default routing rules if none exist"""
    if len(_routing_rules) > 0:
        return
    
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
    
    logger.info("Initialized default routing rules")


# Initialize default rules if empty
if len(_routing_rules) == 0:
    initialize_default_rules()

# Initialize Pathway pipeline with current rules if available
if PATHWAY_AVAILABLE:
    try:
        pathway_pipeline = get_pathway_pipeline()
        if pathway_pipeline and len(_routing_rules) > 0:
            pathway_pipeline.update_rules(_routing_rules)
            logger.info(f"Initialized Pathway pipeline with {len(_routing_rules)} rules")
    except Exception as e:
        logger.warning(f"Failed to initialize Pathway with rules: {e}")

