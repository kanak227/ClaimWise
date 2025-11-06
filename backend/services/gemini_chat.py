import os
import asyncio
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are ClaimWise's helpful insurance claim assistant. "
    "Answer clearly and concisely. Ground every assessment in the provided claim context. "
    "When explaining fraud risk, cite explicit evidence from field comparisons and document analysis—"
    "for example, mismatched IDs, large damage deltas, inconsistent dates/locations, or missing documents. "
    "Do not invent details. If something is unknown or not present in context, state it plainly. "
    "Prefer short bullet points for reasons."
)


def _render_context(ctx: Dict[str, Any]) -> str:
    """Format a compact context block for prompting."""
    parts: List[str] = []
    parts.append(f"Claim ID: {ctx.get('claim_number') or ctx.get('id')}")
    parts.append(f"Claimant: {ctx.get('claimant')} <{ctx.get('email')}>")
    parts.append(f"Policy: {ctx.get('policy_number')}")
    parts.append(f"Loss Type: {ctx.get('loss_type')}")
    parts.append(f"Severity: {ctx.get('severity')}")
    parts.append(f"Queue: {ctx.get('queue')} | Status: {ctx.get('status')}")

    analyses = ctx.get("analyses") or {}
    if analyses:
        # Surface key extracted fields if present
        ex = []
        for doc_type, analysis in (analyses or {}).items():
            extraction = (analysis or {}).get("extraction") or {}
            if extraction:
                keys = list(extraction.keys())[:6]
                if keys:
                    ex.append(f"- {doc_type}: " + ", ".join(keys))
        if ex:
            parts.append("Extracted fields: \n" + "\n".join(ex))

    ml = ctx.get("ml_scores") or {}
    if any(v is not None for v in ml.values()):
        # Basic scores
        score_bits = []
        for k in ["fraud_score", "complexity_score", "severity_level", "litigation_score", "subrogation_score"]:
            if ml.get(k) is not None:
                score_bits.append(f"{k}={ml.get(k)}")
        if score_bits:
            parts.append("ML Scores: " + ", ".join(score_bits))

        # Evidence extraction from features
        feats = ml.get("features") or {}
        evidence: List[str] = []

        try:
            damage_diff = feats.get("damage_difference")
            if isinstance(damage_diff, (int, float)) and damage_diff is not None and damage_diff != 0:
                evidence.append(f"Damage estimate difference across docs: {damage_diff}")

            inj_mismatch = feats.get("injury_mismatch")
            if isinstance(inj_mismatch, (int, float)) and inj_mismatch > 0:
                evidence.append("Injury details mismatch between sources")

            date_diff = feats.get("date_difference_days")
            if isinstance(date_diff, (int, float)) and date_diff and abs(float(date_diff)) > 0:
                evidence.append(f"Incident date inconsistency: ~{int(abs(float(date_diff)))} days")

            for key, label in [
                ("location_match", "Location"),
                ("vehicle_match", "Vehicle"),
                ("rc_match", "RC"),
                ("dl_match", "DL"),
                ("patient_match", "Patient"),
                ("hospital_match", "Hospital"),
            ]:
                val = feats.get(key)
                if isinstance(val, (int, float)):
                    if float(val) == 0.0:
                        evidence.append(f"{label} details do not match across documents")

            inc = feats.get("fraud_inconsistency_score")
            if isinstance(inc, (int, float)) and inc and inc > 0:
                evidence.append(f"Inconsistency signal score: {inc}")
        except Exception:
            # Do not fail context rendering on malformed features
            pass

        if evidence:
            parts.append("Evidence:\n- " + "\n- ".join(evidence[:8]))
    return "\n".join(parts)


async def chat_with_gemini(
    message: str,
    history: Optional[List[Dict[str, str]]],
    claim_context: Dict[str, Any],
) -> str:
    """Call Gemini to answer with claim-aware context.

    Falls back to an offline answer if GEMINI_API_KEY is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Returning fallback answer.")
        ctx = _render_context(claim_context)
        return (
            "[Local answer] I don't have external model access here. "
            "Based on the claim context I have: \n\n" + ctx + "\n\n" +
            f"Your question: {message}\n"
        )

    try:
        # Lazy import to avoid import errors if not installed
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        # Prefer explicit override if provided
        override = os.getenv("GEMINI_MODEL", "").strip()
        candidates: List[str] = []
        if override:
            candidates.append(override)
        try:
            # Discover available models and capabilities dynamically (API may be v1 or v1beta)
            models = genai.list_models()  # returns iterable of model objects
            # Filter models that support generateContent
            for m in models:
                caps = getattr(m, "supported_generation_methods", None) or []
                name = getattr(m, "name", "")
                # names are like "models/gemini-2.0-flash"; we want the tail id
                tail = name.split("/")[-1] if name else ""
                if "generateContent" in caps and tail:
                    candidates.append(tail)
        except Exception as e:
            logger.warning("Failed to list models; falling back to known IDs: %s", e)
            candidates.extend([
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-2.0-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ])
        # Deduplicate while preserving order
        seen = set()
        candidates = [x for x in candidates if not (x in seen or seen.add(x))]

        # Construct messages: a system-style preamble + claim context + history + user message
        ctx_block = _render_context(claim_context)
        preface = (
            f"System: {SYSTEM_PROMPT}\n\n" \
            f"Claim Context:\n{ctx_block}\n\n"
        )

        # Convert history (if any) to a single text block; SDK chat history formats vary
        hist_text = ""
        for m in (history or []):
            role = m.get("role", "user")
            content = m.get("content", "")
            hist_text += f"{role.title()}: {content}\n"

        prompt = preface + hist_text + f"User: {message}\nAssistant:"

        last_err: Optional[Exception] = None
        for name in candidates:
            try:
                client = genai.GenerativeModel(name)
                resp = await asyncio.to_thread(client.generate_content, prompt)
                text = (getattr(resp, "text", None) or "").strip()
                if text:
                    return text
            except Exception as e:
                last_err = e
                logger.warning("Gemini model '%s' failed: %s", name, e)
                continue
        if last_err:
            raise last_err
        return "(No response)"
    except Exception as e:
        logger.exception("Gemini chat failed: %s", e)
        return (
            "We couldn't reach the LLM right now. "
            "Please try again later."
        )
