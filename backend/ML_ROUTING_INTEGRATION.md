# ML & Dynamic Routing Integration

This document describes the ML fraud detection and dynamic routing system integrated into the backend.

## Overview

The system integrates ML models from `ml/fraud_detection_system/` with the backend to:
1. Score claims using fraud detection models (fraud, complexity, severity)
2. Route claims dynamically based on configurable rules
3. Allow rules to be managed via API endpoints
4. Automatically reroute claims when rules change

## Architecture

### Components

1. **ML Service** (`services/ml_service.py`)
   - Integrates with fraud detection models
   - Scores claims: fraud_score, complexity_score, severity_level
   - Detects claim category (accident/health)
   - Uses triage module for initial routing suggestions

2. **Routing Service** (`services/routing_service.py`)
   - Manages dynamic routing rules
   - Applies rules based on scores and claim type
   - Stores rules in memory and persists to JSON file
   - Supports rule priority ordering

3. **Routing API** (`routers/routing.py`)
   - GET `/routing/rules` - List all rules
   - GET `/routing/rules/{id}` - Get specific rule
   - POST `/routing/rules` - Create new rule
   - PUT `/routing/rules/{id}` - Update rule
   - DELETE `/routing/rules/{id}` - Delete rule
   - POST `/routing/apply` - Test routing with scores
   - GET `/routing/attributes` - Get available rule attributes

4. **Upload Endpoint Integration** (`routers/upload.py`)
   - Now includes ML scoring after OCR
   - Applies routing rules automatically
   - Returns complete analysis with routing

## Flow

1. **File Upload** → OCR Analysis → ML Scoring → Routing Rules → Final Team Assignment

2. When a file is uploaded:
   - OCR extracts text and entities
   - ML service scores the claim (fraud, complexity, severity)
   - Routing service applies dynamic rules
   - Returns routing team and adjuster

3. **Dynamic Rules**:
   - Rules are evaluated in priority order
   - First matching rule wins
   - Rules can be enabled/disabled
   - Rules persist to `routing_rules.json`

## Rule Structure

```json
{
  "id": "uuid",
  "name": "Rule Name",
  "description": "Description",
  "enabled": true,
  "priority": 1,
  "condition_type": "fraud|severity|complexity|claim_type|fraud_threshold|combined",
  "condition_value": "low|mid|high|accident|health",
  "claim_type": "accident|health|null",
  "routing_team": "SIU (Fraud)",
  "adjuster": "SIU Investigator",
  "operator": ">=|>|<=|<",
  "threshold": 0.6,
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

## Rule Types

### 1. Category-based (fraud, severity, complexity)
- `condition_type`: "fraud", "severity", or "complexity"
- `condition_value`: "low", "mid", or "high"
- Matches when score category matches

### 2. Claim Type
- `condition_type`: "claim_type"
- `condition_value`: "accident" or "health"
- Matches when claim category matches

### 3. Fraud Threshold
- `condition_type`: "fraud_threshold"
- `operator`: ">=", ">", "<=", "<"
- `threshold`: numeric value (0.0-1.0)
- Matches when fraud_score operator threshold

### 4. Combined Conditions
- `condition_type`: "combined"
- Can specify multiple: `fraud_category`, `severity_category`, `complexity_category`
- All specified conditions must match

## Default Teams

- **Fast Track** - Low risk, simple claims
- **Standard Review** - Medium risk claims
- **Complex Claims** - High severity/complexity
- **SIU (Fraud)** - High fraud risk
- **Litigation** - Potential legal issues
- **Subrogation** - Recovery opportunities
- **Total Loss** - Total loss cases
- **Bodily Injury** - Injury-related claims

## Score Categories

### Fraud Score (0.0 - 1.0)
- **Low**: ≤ 0.33
- **Mid**: 0.34 - 0.67
- **High**: ≥ 0.68

### Severity Level
- **Low**: Low severity
- **Mid**: Medium severity
- **High**: High severity

### Complexity Score
- **Low**: ≤ 2.0
- **Mid**: 2.1 - 3.5
- **High**: ≥ 3.6

## API Usage Examples

### Upload with ML Scoring
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "claim_number=CLM-2025-001" \
  -F "file=@document.pdf"
```

Response includes:
```json
{
  "status": "uploaded",
  "ml_scores": {
    "fraud_score": 0.45,
    "complexity_score": 2.5,
    "severity_level": "Medium",
    "claim_category": "accident"
  },
  "routing": {
    "routing_team": "Standard Review",
    "adjuster": "Standard Adjuster",
    "routing_reasons": ["Rule: fraud=mid"]
  },
  "final_team": "Standard Review",
  "final_adjuster": "Standard Adjuster"
}
```

### Create Routing Rule
```bash
curl -X POST "http://localhost:8000/routing/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Fraud - All",
    "condition_type": "fraud_threshold",
    "operator": ">=",
    "threshold": 0.6,
    "routing_team": "SIU (Fraud)",
    "adjuster": "SIU Investigator",
    "priority": 1
  }'
```

### List All Rules
```bash
curl "http://localhost:8000/routing/rules"
```

### Update Rule
```bash
curl -X PUT "http://localhost:8000/routing/rules/{rule_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

## Frontend Integration

The frontend can:
1. Display routing rules via `/routing/rules`
2. Create/update/delete rules
3. See routing results for claims
4. When rules change, new uploads automatically use new routing

## Rerouting

When a rule is changed:
- The change is immediately saved
- Next claim upload will use the new rule
- Existing claims are not automatically rerouted (requires manual reassignment)

To reroute existing claims:
1. Fetch claim data
2. Re-run routing via `/routing/apply` with claim's scores
3. Update claim's team assignment

## Model Requirements

Models should be placed in:
- `ml/fraud_detection_system/models/fraud_model.pkl`
- `ml/fraud_detection_system/models/severity_model.pkl`
- `ml/fraud_detection_system/models/complexity_model.pkl`

If models are missing, the system falls back to heuristic scoring.

## Dependencies

See `requirements.txt` for ML dependencies:
- pandas>=2.0.0
- numpy>=1.26.0
- scikit-learn>=1.4.0
- joblib>=1.3.0

## File Structure

```
backend/
├── services/
│   ├── ml_service.py          # ML integration
│   └── routing_service.py     # Routing rules engine
├── routers/
│   ├── upload.py             # Updated with ML/routing
│   └── routing.py            # Routing API endpoints
└── routing_rules.json        # Persistent rule storage
```

