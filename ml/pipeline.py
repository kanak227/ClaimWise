from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pandas as pd
except ImportError:
    pd = None

from .config import FRAUD_WEIGHTS

logger = logging.getLogger(__name__)


# -----------------------------
# PDF text extraction
# -----------------------------

def extract_text_from_pdf(path: Path) -> str:
    if not fitz:
        logger.warning("PyMuPDF (fitz) is not installed, returning empty text")
        return ""
    text_parts: List[str] = []
    try:
        with fitz.open(path) as doc:
            for page in doc:
                text_parts.append(page.get_text("text"))
    except Exception as e:
        text_parts.append(f"<EXTRACT_ERROR: {e}>")
    return "\n".join(t for t in text_parts if t)


# -----------------------------
# Field parsing helpers
# -----------------------------

DATE_PAT = re.compile(r"(\b\d{4}[-/.]\d{2}[-/.]\d{2}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b)")
MONEY_PAT = re.compile(r"(?:[$₹]|i)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+)")
PR_PAT = re.compile(r"\bPR[- ]?(\d{4,6})\b", re.IGNORECASE)
CLAIM_PAT = re.compile(r"\bCLM[- ]?(\d{4})[- ]?(\d{2})?[- ]?(\d{4})\b", re.IGNORECASE)
REG_LINE_PAT = re.compile(r"registration\s*:\s*([^\n\r]+)", re.IGNORECASE)
LOC_LINE_PAT = re.compile(r"location\s*:\s*([^\n\r]+)", re.IGNORECASE)
INJURY_LINE_PAT = re.compile(r"injuries?\s*reported\s*:\s*(true|false|yes|no)", re.IGNORECASE)
POLICY_PAT = re.compile(r"policy\s*(?:no|number)\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE)
RCNO_PAT = re.compile(r"rc\s*no\s*:\s*([A-Za-z0-9- ]+)", re.IGNORECASE)
DLNO_PAT = re.compile(r"dl\s*no\s*:\s*([A-Za-z0-9- ]+)", re.IGNORECASE)
PATIENT_PAT = re.compile(r"patient\s*id\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE)
HOSPITAL_CODE_PAT = re.compile(r"hospital\s*code\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE)


def to_float_money(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        s2 = s.replace(",", "").replace("₹", "").replace("$", "")
        s2 = s2.lstrip("i").strip()
        return float(s2)
    except Exception:
        return None


def parse_date_any(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def normalize_claim_id(claim: Optional[str]) -> Optional[str]:
    if not claim:
        return None
    m = CLAIM_PAT.search(claim)
    if not m:
        return None
    y = m.group(1)
    maybe_mm = m.group(2)
    nnnn = m.group(3)
    return f"CLM-{y}-{nnnn}"


def extract_fields_from_text(text: str, source: str) -> Dict:
    d: Dict = {"source": source}

    # claim id
    m = CLAIM_PAT.search(text)
    if m:
        claim_full = f"CLM-{m.group(1)}-{m.group(2)+'-' if m.group(2) else ''}{m.group(3)}"
        d["claim_id"] = claim_full
        d["claim_short_id"] = normalize_claim_id(claim_full)

    # police report
    m = PR_PAT.search(text)
    if m:
        d["police_report_no"] = f"PR-{m.group(1)}"

    # policy number
    m = POLICY_PAT.search(text)
    if m:
        d["policy_number"] = m.group(1)

    # RC / DL numbers
    m = RCNO_PAT.search(text)
    if m:
        d["rc_no"] = m.group(1).strip()
    m = DLNO_PAT.search(text)
    if m:
        d["dl_no"] = m.group(1).strip()

    # Patient / Hospital for health
    m = PATIENT_PAT.search(text)
    if m:
        d["patient_id"] = m.group(1).strip()
    m = HOSPITAL_CODE_PAT.search(text)
    if m:
        d["hospital_code"] = m.group(1).strip()

    # dates
    m_inc = re.search(r"incident\s*date\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_inc:
        m_date = DATE_PAT.search(m_inc.group(1))
        if m_date:
            d["incident_date"] = m_date.group(1)
            
    m_loss = re.search(r"loss\s*date\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_loss:
        m_date = DATE_PAT.search(m_loss.group(1))
        if m_date:
            d["loss_date"] = m_date.group(1)
            
    dates = DATE_PAT.findall(text)
    if dates:
        d.setdefault("incident_date", dates[0])
        if len(dates) > 1:
            d.setdefault("loss_date", dates[1])

    # location
    m = LOC_LINE_PAT.search(text)
    if m:
        d["location"] = m.group(1).strip()

    # vehicle registration
    m = REG_LINE_PAT.search(text)
    if m:
        d["vehicle_registration"] = m.group(1).strip()

    # injuries
    m = INJURY_LINE_PAT.search(text)
    if m:
        val = m.group(1).lower()
        d["injuries_reported"] = 1 if val in ("true", "yes", "1") else 0

    # estimated damage / cost extraction
    cost = None
    for key in ("estimated damage cost", "estimated damage", "damage estimate", "damage cost", 
                "total amount", "total cost", "bill amount", "charges", "amount due", 
                "claim amount", "settlement amount"):
        idx = text.lower().find(key)
        if idx != -1:
            tail = text[idx: idx + 150]
            mm = MONEY_PAT.search(tail)
            if mm:
                cost = to_float_money(mm.group(1))
                if cost and cost > 0:
                    break
    
    if cost is None or cost == 0:
        all_amounts = MONEY_PAT.findall(text)
        money_values = []
        for amt_str in all_amounts[:10]:
            val = to_float_money(amt_str)
            if val and val > 100:
                money_values.append(val)
        if money_values:
            cost = max(money_values)
    
    if cost is not None and cost > 0:
        d["estimated_damage_cost"] = cost
        if source == "hospital":
            d["total_amount"] = cost

    if re.search(r"total\s*loss\s*:\s*(true|yes|1)", text, re.IGNORECASE):
        d["total_loss_flag"] = 1
    elif re.search(r"total\s*loss\s*:\s*(false|no|0)", text, re.IGNORECASE):
        d["total_loss_flag"] = 0
    
    severity_keywords_high = ["critical", "severe", "major", "catastrophic", "totaled", "write-off", 
                              "life-threatening", "hospitalized", "surgery", "fracture", "broken"]
    severity_keywords_med = ["moderate", "significant", "substantial", "serious", "injury", "damaged"]
    
    text_lower = text.lower()
    high_severity_count = sum(1 for kw in severity_keywords_high if kw in text_lower)
    med_severity_count = sum(1 for kw in severity_keywords_med if kw in text_lower)
    
    if high_severity_count >= 2:
        d["text_severity_indicator"] = "high"
    elif high_severity_count >= 1 or med_severity_count >= 2:
        d["text_severity_indicator"] = "medium"
    elif med_severity_count >= 1:
        d["text_severity_indicator"] = "low"
    else:
        d["text_severity_indicator"] = None

    return d


# -----------------------------
# Heuristics & Feature engineering
# -----------------------------

def fraud_score(row: Dict) -> float:
    weights = FRAUD_WEIGHTS
    total = (
        weights["damage_difference"] * float(row.get("damage_difference", 0.0))
        + weights["injury_mismatch"] * float(row.get("injury_mismatch", 0.0))
        + weights["date_difference_days"] * min(abs(float(row.get("date_difference_days", 0.0))) / 10.0, 1.0)
        + weights["location_match"] * (1.0 - float(row.get("location_match", 0.0)))
        + weights["vehicle_match"] * (1.0 - float(row.get("vehicle_match", 0.0)))
        + weights["rc_match"] * (1.0 - float(row.get("rc_match", 0.0)))
        + weights["dl_match"] * (1.0 - float(row.get("dl_match", 0.0)))
        + weights["patient_match"] * (1.0 - float(row.get("patient_match", 1.0)))
        + weights["hospital_match"] * (1.0 - float(row.get("hospital_match", 1.0)))
        + weights["fraud_inconsistency_score"] * float(row.get("fraud_inconsistency_score", 0.0))
    )
    return round(min(total, 1.0), 3)


def fraud_label_from_score(score: float) -> int:
    return 1 if score > 0.5 else 0


def severity_to_numeric(level: str | None) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3}
    if not level:
        return 0
    return mapping.get(str(level).strip().lower(), 0)


def token_overlap(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    A = {t.strip().lower() for t in re.split(r"[^A-Za-z0-9]+", a) if t}
    B = {t.strip().lower() for t in re.split(r"[^A-Za-z0-9]+", b) if t}
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def build_features(
    ac: pd.Series | Dict,
    pr: Optional[pd.Series | Dict],
    lr: Optional[pd.Series | Dict],
    rc: Optional[pd.Series | Dict] = None,
    dl: Optional[pd.Series | Dict] = None,
    hospital: Optional[pd.Series | Dict] = None
) -> Dict:
    def get(s: Optional[pd.Series | Dict], key: str, default=None):
        if s is None:
            return default
        if hasattr(s, "get"):
            return s.get(key, default)
        return default

    acord_cost = ac.get("estimated_damage_cost")
    loss_cost = get(lr, "estimated_damage_cost")
    if acord_cost and loss_cost:
        damage_diff = abs(acord_cost - loss_cost) / max(acord_cost, 1)
    else:
        damage_diff = 0.0

    inj_mismatch = 0
    if ac.get("injuries_reported") is not None and get(lr, "injuries_reported") is not None:
        inj_mismatch = 1 if int(ac.get("injuries_reported")) != int(get(lr, "injuries_reported")) else 0
    elif ac.get("injuries_reported") is not None and get(pr, "injuries_reported") is not None:
        inj_mismatch = 1 if int(ac.get("injuries_reported")) != int(get(pr, "injuries_reported")) else 0

    d1 = parse_date_any(ac.get("incident_date"))
    d2 = parse_date_any(get(lr, "loss_date")) or parse_date_any(get(pr, "incident_date"))
    date_diff_days = abs((d1 - d2).days) if (d1 and d2) else 0

    loc_match = max(
        token_overlap(ac.get("location"), get(pr, "location")),
        token_overlap(ac.get("location"), get(lr, "location")),
    )
    veh_match = 1.0 if (ac.get("vehicle_registration") and (
        ac.get("vehicle_registration") == get(pr, "vehicle_registration") or ac.get("vehicle_registration") == get(lr, "vehicle_registration")
    )) else 0.0

    def consistent_value(values: List[Optional[str]]) -> float:
        vals = [str(v).strip() for v in values if v not in (None, "", float('nan'))]
        if len(vals) < 2:
            return 1.0
        return 1.0 if len(set(vals)) == 1 else 0.0

    rc_match = consistent_value([
        ac.get("rc_no"), get(pr, "rc_no"), get(lr, "rc_no"), get(rc, "rc_no")
    ])
    dl_match = consistent_value([
        ac.get("dl_no"), get(pr, "dl_no"), get(lr, "dl_no"), get(dl, "dl_no")
    ])

    patient_match = consistent_value([
        ac.get("patient_id"), get(hospital, "patient_id")
    ])
    hospital_match = consistent_value([
        ac.get("hospital_code"), get(hospital, "hospital_code")
    ])

    inconsistency = (damage_diff + inj_mismatch + min(date_diff_days/10, 1) + (1-loc_match) + (1-veh_match)) / 5.0

    severity_score = 0
    max_cost = max(loss_cost or 0, acord_cost or 0, get(hospital, "total_amount") or 0)
    if max_cost > 200000:
        severity_score += 4
    elif max_cost > 100000:
        severity_score += 3
    elif max_cost > 50000:
        severity_score += 2
    elif max_cost > 20000:
        severity_score += 1
    
    injuries_reported = (
        1 if ac.get("injuries_reported") == 1 else
        1 if get(lr, "injuries_reported") == 1 else
        1 if get(pr, "injuries_reported") == 1 else 0
    )
    if injuries_reported:
        severity_score += 3
        
    if get(lr, "total_loss_flag") == 1:
        severity_score += 3
        
    severity_level = "Low"
    if severity_score >= 7:
        severity_level = "High"
    elif severity_score >= 4:
        severity_level = "Medium"
        
    word_counts = []
    for d in (ac, pr, lr, rc, dl, hospital):
        if d is not None:
            raw_t = d.get("raw_text") or ""
            word_counts.append(len(raw_t.split()))
    avg_words = sum(word_counts) / max(len(word_counts), 1)
    
    complexity_score = 1.0
    if avg_words > 1000:
        complexity_score += 2.0
    elif avg_words > 500:
        complexity_score += 1.0
        
    docs_present = sum(1 for d in (ac, pr, lr, rc, dl, hospital) if d is not None)
    if docs_present > 4:
        complexity_score += 1.5
    elif docs_present > 2:
        complexity_score += 0.5
        
    if severity_level == "High":
        complexity_score += 1.0
    elif severity_level == "Medium":
        complexity_score += 0.5
        
    return {
        "damage_difference": damage_diff,
        "injury_mismatch": inj_mismatch,
        "date_difference_days": date_diff_days,
        "location_match": loc_match,
        "vehicle_match": veh_match,
        "rc_match": rc_match,
        "dl_match": dl_match,
        "patient_match": patient_match,
        "hospital_match": hospital_match,
        "fraud_inconsistency_score": inconsistency,
        "severity_score": float(severity_score),
        "severity_level": severity_level,
        "complexity_score": complexity_score
    }


# -----------------------------
# Triage Agent
# -----------------------------

def _bool(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return 1 if int(v) == 1 else 0
    except Exception:
        s = str(v).strip().lower()
        if s in ("true", "yes", "1"): return 1
        if s in ("false", "no", "0"): return 0
    return None


def _text_has(text: Optional[str], patterns: List[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(p.lower() in t for p in patterns)


def _combine_texts(ac_text: Optional[str], pr_text: Optional[str], lr_text: Optional[str]) -> str:
    return "\n".join([t for t in (ac_text or "", pr_text or "", lr_text or "") if t])


def assess_litigation(ac: Dict, pr: Dict, lr: Dict, feats: Dict, texts: Tuple[Optional[str], Optional[str], Optional[str]]) -> Tuple[float, bool, List[str]]:
    ac_text, pr_text, lr_text = texts
    reasons = []
    score = 0.0

    injuries = _bool(ac.get("injuries_reported")) or _bool(pr.get("injuries_reported")) or _bool(lr.get("injuries_reported")) or 0
    if injuries:
        score += 0.25
        reasons.append("Injuries reported")

    if feats.get("severity_level") == "High" or float(feats.get("complexity_score", 0)) >= 3:
        score += 0.25
        reasons.append("High severity/complexity")

    if pr.get("police_report_no"):
        score += 0.15
        reasons.append("Police report present")

    text_all = _combine_texts(ac_text, pr_text, lr_text)
    if _text_has(text_all, ["attorney", "legal", "lawsuit", "notice of claim"]):
        score += 0.35
        reasons.append("Legal keywords present")

    flag = score >= 0.5
    return round(min(score, 1.0), 3), flag, reasons


def assess_subrogation(ac: Dict, pr: Dict, lr: Dict, feats: Dict, texts: Tuple[Optional[str], Optional[str], Optional[str]]) -> Tuple[float, bool, List[str]]:
    ac_text, pr_text, lr_text = texts
    reasons = []
    score = 0.0

    text_all = _combine_texts(ac_text, pr_text, lr_text)
    if _text_has(text_all, ["rear collision", "rear-end", "rear end"]):
        score += 0.35
        reasons.append("Rear-end scenario")

    if pr.get("police_report_no"):
        score += 0.15
        reasons.append("Police report present")

    if float(feats.get("damage_difference", 0)) < 0.15 and feats.get("severity_level") in ("Medium", "High"):
        score += 0.25
        reasons.append("Significant damage, consistent")

    if float(feats.get("location_match", 0)) >= 0.7 and float(feats.get("vehicle_match", 0)) == 1.0:
        score += 0.25
        reasons.append("Good doc alignment")

    flag = score >= 0.5
    return round(min(score, 1.0), 3), flag, reasons


def choose_routing(feats: Dict, fraud_risk: float, fraud_label: Optional[int], litigation_flag: bool, subro_flag: bool, ac: Dict, pr: Dict, lr: Dict) -> Tuple[str, str, List[str]]:
    reasons: List[str] = []
    team = "Fast Track"
    adjuster = "Standard Adjuster"

    total_loss = _bool(lr.get("total_loss_flag")) == 1
    injuries = _bool(ac.get("injuries_reported")) or _bool(pr.get("injuries_reported")) or _bool(lr.get("injuries_reported"))

    if fraud_label == 1 or fraud_risk >= 0.6:
        team = "SIU (Fraud)"
        adjuster = "SIU Investigator"
        reasons.append("High fraud risk")
        return team, adjuster, reasons

    if litigation_flag:
        team = "Litigation"
        adjuster = "Senior BI Adjuster"
        reasons.append("Potential litigation")
        return team, adjuster, reasons

    if subro_flag:
        team = "Subrogation"
        adjuster = "Subrogation Specialist"
        reasons.append("Potential recovery opportunity")
        return team, adjuster, reasons

    if total_loss:
        team = "Total Loss"
        adjuster = "Total Loss Adjuster"
        reasons.append("Total loss flagged")
        return team, adjuster, reasons

    if feats.get("severity_level") == "High" or float(feats.get("complexity_score", 0)) >= 3:
        team = "Complex Claims"
        adjuster = "Senior Adjuster"
        reasons.append("High severity/complexity")
        return team, adjuster, reasons

    if injuries:
        team = "Bodily Injury"
        adjuster = "BI Adjuster"
        reasons.append("Injuries reported")
        return team, adjuster, reasons

    return team, adjuster, reasons


def triage(ac: Dict, pr: Dict, lr: Dict, feats: Dict, texts: Tuple[Optional[str], Optional[str], Optional[str]]) -> Dict:
    f_score = fraud_score(feats)
    f_label = 1 if f_score > 0.5 else 0

    lit_score, lit_flag, lit_reasons = assess_litigation(ac, pr, lr, feats, texts)
    subro_score, subro_flag, subro_reasons = assess_subrogation(ac, pr, lr, feats, texts)

    team, adjuster, route_reasons = choose_routing(feats, f_score, f_label, lit_flag, subro_flag, ac, pr, lr)

    return {
        "fraud_score": f_score,
        "fraud_label": f_label,
        "severity_level": feats.get("severity_level"),
        "complexity_score": feats.get("complexity_score"),
        "litigation_score": lit_score,
        "litigation_flag": lit_flag,
        "subrogation_score": subro_score,
        "subrogation_flag": subro_flag,
        "routing_team": team,
        "adjuster": adjuster,
        "reasons": route_reasons,
        "litigation_reasons": lit_reasons,
        "subrogation_reasons": subro_reasons,
    }
