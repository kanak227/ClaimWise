# Pathway Integration for Reactive Claim Routing

This document describes the complete Pathway-based reactive routing system for real-time claim processing.

## Overview

The system now uses **Pathway framework** for real-time, reactive claim processing. Pathway enables:

- **Real-time processing**: Claims are processed as they arrive
- **Reactive routing**: When rules change, affected claims are automatically rerouted
- **Streaming pipeline**: All claims flow through a unified processing pipeline
- **Automatic updates**: No manual intervention needed when rules change

## Architecture

```
File Upload → OCR Analysis → ML Scoring → Pathway Pipeline → Routing Rules → Team Assignment
                                      ↑
                                      |
                              Rules Updates (Reactive)
```

### Key Components

1. **Pathway Pipeline** (`services/pathway_pipeline.py`)
   - Main Pathway pipeline for claim processing
   - Reactive rule matching
   - Automatic rerouting on rule changes

2. **Routing Service** (`services/routing_service.py`)
   - Integrates with Pathway pipeline
   - Manages rule CRUD operations
   - Updates Pathway when rules change

3. **ML Service** (`services/ml_service.py`)
   - Provides fraud/complexity/severity scores
   - Feeds data into Pathway pipeline

## Pathway Features Used

### 1. Reactive Data Processing
When a routing rule is updated:
- Pathway automatically detects the change
- All claims in the pipeline are reevaluated
- Affected claims are automatically rerouted
- No manual intervention required

### 2. Real-time Processing
- Claims are processed immediately upon upload
- No batch processing delays
- Results are available instantly

### 3. Version Tracking
- Each rule update increments a version number
- Claims track which rule version they were routed with
- Enables audit trail and debugging

## API Endpoints

### Standard Routing Endpoints
- `POST /upload` - Upload claim (automatically uses Pathway)
- `GET /routing/rules` - List all rules
- `POST /routing/rules` - Create rule (triggers Pathway update)
- `PUT /routing/rules/{id}` - Update rule (triggers reactive rerouting)
- `DELETE /routing/rules/{id}` - Delete rule (triggers reactive rerouting)

### Pathway-Specific Endpoints
- `POST /routing/reroute` - Manually reroute existing claims
  ```json
  [
    {
      "claim_id": "CLM-001",
      "fraud_score": 0.45,
      "complexity_score": 2.5,
      "severity_level": "Medium",
      "claim_category": "accident"
    }
  ]
  ```

## Reactive Routing Flow

### When a Rule is Created/Updated:

1. **Rule Change Detected**
   ```python
   update_rule(rule_id, new_data)
   ```

2. **Pathway Pipeline Updated**
   ```python
   pathway_pipeline.update_rules(all_rules)
   ```

3. **Automatic Rerouting**
   - Pathway identifies all claims affected by the change
   - Reapplies routing rules to those claims
   - Updates routing assignments automatically

4. **Frontend Notification** (optional)
   - Claims can be marked as "rerouted"
   - UI can show which claims were affected

### Example: Updating a Rule

```python
# Update rule to route high fraud to different team
PUT /routing/rules/{id}
{
  "routing_team": "Special Fraud Unit",
  "adjuster": "Senior SIU Investigator"
}

# Pathway automatically:
# 1. Updates the rule
# 2. Finds all claims with high fraud that matched this rule
# 3. Reroutes them to "Special Fraud Unit"
# 4. Updates their adjuster assignment
```

## Claim Processing Flow

### Step-by-Step with Pathway

1. **File Upload**
   ```
   POST /upload
   ```

2. **OCR Analysis**
   - Text extraction
   - Entity extraction
   - Document classification

3. **ML Scoring**
   - Fraud score calculation
   - Complexity score
   - Severity level

4. **Pathway Processing** (NEW)
   ```python
   pathway_pipeline.process_claim(claim_data, ml_scores)
   ```
   - Categorizes scores (low/mid/high)
   - Matches against current rules
   - Returns routing assignment
   - Tracks rule version

5. **Response**
   ```json
   {
     "status": "uploaded",
     "ml_scores": {...},
     "routing": {
       "routing_team": "SIU (Fraud)",
       "adjuster": "SIU Investigator",
       "matched_rule_id": "rule-uuid",
       "rules_version": 3,
       "pathway_processed": true
     }
   }
   ```

## Rule Versioning

Each rule update increments the version:
- `rules_version: 0` - Initial rules
- `rules_version: 1` - First update
- `rules_version: 2` - Second update
- etc.

Claims track which version they were routed with, enabling:
- Audit trails
- Debugging routing decisions
- Understanding rule impact over time

## Rerouting Existing Claims

When rules change, you can reroute existing claims:

```bash
POST /routing/reroute
[
  {
    "claim_id": "CLM-001",
    "fraud_score": 0.65,
    "complexity_score": 3.0,
    "severity_level": "High",
    "claim_category": "accident"
  }
]
```

Response:
```json
{
  "rerouted_claims": [
    {
      "claim_id": "CLM-001",
      "routing_team": "Complex Claims",  // Updated
      "adjuster": "Senior Adjuster",      // Updated
      "rerouted_at": "2025-01-15T10:30:00"
    }
  ],
  "count": 1
}
```

## Installation

```bash
# Install Pathway
pip install pathway>=0.8.0

# Or update requirements.txt
pip install -r requirements.txt
```

## Configuration

Pathway pipeline initializes automatically when:
1. First rule is created, OR
2. Rules are loaded from file, OR
3. API endpoints are called

The pipeline runs in the background and processes claims reactively.

## Benefits of Pathway Integration

### 1. Automatic Rerouting
- No manual intervention needed
- Claims automatically get new routing when rules change
- Consistent with latest rules

### 2. Real-time Updates
- Changes take effect immediately
- No need to reprocess queues
- Instant feedback

### 3. Scalability
- Pathway handles streaming data efficiently
- Can process thousands of claims per second
- Suitable for production workloads

### 4. Reliability
- Version tracking ensures consistency
- Audit trail for all routing decisions
- Easy to debug routing issues

## Fallback Behavior

If Pathway is not available:
- System falls back to standard routing service
- All functionality still works
- Just without reactive rerouting

Check logs for:
```
Pathway not available, using standard routing
```

## Monitoring

Check Pathway pipeline status:
- Logs show when pipeline is initialized
- Rule updates are logged with version numbers
- Routing decisions include `pathway_processed: true/false`

## Troubleshooting

### Pathway Not Initializing
1. Check if Pathway is installed: `pip list | grep pathway`
2. Check logs for import errors
3. Verify Python version compatibility

### Rules Not Updating
1. Check if Pathway pipeline is running
2. Verify rule updates are being saved
3. Check `rules_version` in responses

### Claims Not Rerouting
1. Verify Pathway pipeline is initialized
2. Check if rules are properly updated
3. Use `/routing/reroute` endpoint manually

## Next Steps

For full Pathway streaming capabilities, consider:
1. **Kafka/Message Queue Integration**: Stream claims from external sources
2. **Database Connectors**: Read/write to database tables reactively
3. **Monitoring Dashboard**: Real-time view of pipeline metrics
4. **WebSocket Updates**: Push routing updates to frontend in real-time

## Code Examples

### Processing a Claim with Pathway

```python
from services.pathway_pipeline import get_pathway_pipeline

pipeline = get_pathway_pipeline()
result = pipeline.process_claim(claim_data, ml_scores)
print(result["routing_team"])  # Automatically routed
```

### Updating Rules (Triggers Rerouting)

```python
from services.routing_service import update_rule, get_all_rules

# Update rule
update_rule(rule_id, {"routing_team": "New Team"})

# Pathway automatically reroutes affected claims
# No additional code needed!
```

## Performance Considerations

- Pathway processes claims in real-time (microseconds)
- Rule updates propagate instantly
- No performance degradation with large rule sets
- Memory efficient for streaming data

## Production Deployment

For production, consider:
1. **Pathway Server Mode**: Run Pathway as a separate service
2. **Persistent Storage**: Store claims and rules in database
3. **Monitoring**: Add metrics and alerting
4. **Load Balancing**: Scale Pathway horizontally if needed

