from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "dataset"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    'damage_difference',
    'injury_mismatch',
    'date_difference_days',
    'location_match',
    'vehicle_match',
    'rc_match',
    'dl_match',
    'patient_match',
    'hospital_match',
    'fraud_inconsistency_score',
    'severity_numeric',
    'complexity_score',
    'category_id'
]

FRAUD_WEIGHTS = {
    "damage_difference": 0.18,
    "injury_mismatch": 0.12,
    "date_difference_days": 0.15,
    "location_match": 0.09,
    "vehicle_match": 0.09,
    "rc_match": 0.10,
    "dl_match": 0.10,
    "patient_match": 0.08,
    "hospital_match": 0.08,
    "fraud_inconsistency_score": 0.01,
}
