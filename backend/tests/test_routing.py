import os
import pytest
import sys
from pathlib import Path

# Configure mock in-memory database for testing
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Add backend and project root to path
backend_path = Path(__file__).resolve().parent.parent
project_root = backend_path.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.routing_service import (
    match_rule_condition,
    normalize_rule_to_frontend,
    normalize_rule_to_backend,
    apply_routing_rules
)
from services.pathway_pipeline import PathwayClaimPipeline, HAS_PATHWAY


def test_rule_normalization():
    # Test converting frontend rule to backend representation
    fe_rule = {
        "id": "test-1",
        "name": "High Fraud",
        "enabled": True,
        "priority": 1,
        "attribute": "fraud",
        "operator": ">=",
        "amount": 0.8,
        "forward_to": "SIU (Fraud)"
    }
    
    be_rule = normalize_rule_to_backend(fe_rule)
    assert be_rule["condition_type"] == "fraud_threshold"
    assert be_rule["operator"] == ">="
    assert be_rule["threshold"] == 0.8
    assert be_rule["routing_team"] == "SIU (Fraud)"
    
    # Test converting backend rule to frontend representation
    be_rule_source = {
        "id": "test-2",
        "name": "High Severity Rule",
        "enabled": True,
        "priority": 2,
        "condition_type": "severity",
        "condition_value": "high",
        "routing_team": "Complex Claims",
        "adjuster": "Senior Adjuster"
    }
    
    fe_rule_out = normalize_rule_to_frontend(be_rule_source)
    assert fe_rule_out["attribute"] == "severity_level"
    assert fe_rule_out["operator"] == "="
    assert fe_rule_out["amount"] == 3.0
    assert fe_rule_out["forward_to"] == "Complex Claims"


def test_match_rule_condition_fraud():
    # Test fraud category matching
    rule = {
        "enabled": True,
        "condition_type": "fraud",
        "operator": "==",
        "condition_value": "high"
    }
    # Matches 'high'
    assert match_rule_condition(rule, "high", "low", "low", "accident", 0.8, 1.0, "Low") is True
    # Does not match 'low'
    assert match_rule_condition(rule, "low", "low", "low", "accident", 0.2, 1.0, "Low") is False

    # Test fraud threshold matching
    rule_threshold = {
        "enabled": True,
        "condition_type": "fraud_threshold",
        "operator": ">=",
        "threshold": 0.75
    }
    assert match_rule_condition(rule_threshold, "high", "low", "low", "accident", 0.8, 1.0, "Low") is True
    assert match_rule_condition(rule_threshold, "low", "low", "low", "accident", 0.5, 1.0, "Low") is False


def test_match_rule_condition_severity():
    rule = {
        "enabled": True,
        "condition_type": "severity",
        "operator": "==",
        "condition_value": "high"
    }
    assert match_rule_condition(rule, "low", "high", "low", "accident", 0.1, 1.0, "High") is True
    assert match_rule_condition(rule, "low", "low", "low", "accident", 0.1, 1.0, "Low") is False


def test_match_rule_condition_complexity():
    rule = {
        "enabled": True,
        "condition_type": "complexity",
        "operator": ">",
        "threshold": 3.0
    }
    assert match_rule_condition(rule, "low", "low", "high", "accident", 0.1, 4.0, "Low") is True
    assert match_rule_condition(rule, "low", "low", "low", "accident", 0.1, 2.0, "Low") is False


def test_match_rule_condition_claim_type():
    rule = {
        "enabled": True,
        "condition_type": "claim_type",
        "operator": "==",
        "condition_value": "health"
    }
    assert match_rule_condition(rule, "low", "low", "low", "health", 0.1, 1.0, "Low") is True
    assert match_rule_condition(rule, "low", "low", "low", "medical", 0.1, 1.0, "Low") is True
    assert match_rule_condition(rule, "low", "low", "low", "accident", 0.1, 1.0, "Low") is False


def test_match_rule_condition_combined():
    rule = {
        "enabled": True,
        "condition_type": "combined",
        "fraud_category": "high",
        "severity_category": "high"
    }
    assert match_rule_condition(rule, "high", "high", "low", "accident", 0.8, 1.0, "High") is True
    assert match_rule_condition(rule, "high", "low", "low", "accident", 0.8, 1.0, "Low") is False


def test_apply_routing_rules_fallback():
    # Test default fallback routing when no rules match
    ml_scores = {
        "fraud_score": 0.2,
        "complexity_score": 1.5,
        "severity_level": "Low",
        "claim_category": "accident"
    }
    
    result = apply_routing_rules(ml_scores)
    assert "Accident Dept - Low" in result["routing_team"] or "Fast Track" in result["routing_team"]
    
    # Test SIU fraud fallback
    ml_scores_fraud = {
        "fraud_score": 0.8,
        "complexity_score": 1.5,
        "severity_level": "Low",
        "claim_category": "accident"
    }
    result_fraud = apply_routing_rules(ml_scores_fraud)
    assert result_fraud["routing_team"] == "SIU (Fraud)"


@pytest.mark.skipif(not HAS_PATHWAY, reason="Pathway not installed")
def test_pathway_routing_alignment():
    # Ensure Pathway uses the same dynamic routing logic
    pipeline = PathwayClaimPipeline()
    
    # Set custom rule
    rule = {
        "id": "pw-test-1",
        "name": "Pathway Severity High Forward",
        "enabled": True,
        "priority": 1,
        "condition_type": "severity",
        "condition_value": "high",
        "routing_team": "Super Senior Team",
        "adjuster": "Super Senior Adjuster"
    }
    pipeline.update_rules([rule])
    
    claim = {"claim_number": "CLM-2026-1001"}
    scores = {
        "fraud_score": 0.1,
        "complexity_score": 2.0,
        "severity_level": "High",
        "claim_category": "accident"
    }
    
    result = pipeline.process_claim(claim, scores)
    assert result["routing_team"] == "Super Senior Team"
    assert result["adjuster"] == "Super Senior Adjuster"
    assert result["rule_applied"] is True
