from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import FileResponse
from typing import Optional, Dict
import logging
from services.file_service import save_uploaded_file
from services.ocr_service import analyze_claim_document
from services.ml_service import score_claim_multi_file
from services.routing_service import apply_routing_rules
from services.claim_store import add_claim
from pathlib import Path
import random
import re
import mimetypes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/")
async def upload_claim_file(
    claim_number: str = Form(..., description="Claim number used as filename"),
    claim_type: str = Form(..., description="Claim type: 'medical' or 'accident'"),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    # Medical files
    acord: Optional[UploadFile] = File(None),
    loss: Optional[UploadFile] = File(None),
    hospital: Optional[UploadFile] = File(None),
    # Accident files
    fir: Optional[UploadFile] = File(None),
    rc: Optional[UploadFile] = File(None),
    dl: Optional[UploadFile] = File(None),
):
    """
    Upload claim with multiple files based on claim type.
    Medical: acord, loss, hospital
    Accident: acord, loss, fir, rc, dl
    """
    try:
        if not claim_number or not claim_number.strip():
            raise HTTPException(status_code=400, detail="claim_number is required")
        
        if claim_type not in ["medical", "accident"]:
            raise HTTPException(status_code=400, detail="claim_type must be 'medical' or 'accident'")

        # Validate required files based on claim type
        if claim_type == "medical":
            if not acord or not loss or not hospital:
                raise HTTPException(
                    status_code=400,
                    detail="Medical claims require: acord, loss, and hospital files"
                )
            files = {
                "acord": acord,
                "loss": loss,
                "hospital": hospital,
            }
        elif claim_type == "accident":
            if not acord or not loss or not fir or not rc or not dl:
                raise HTTPException(
                    status_code=400,
                    detail="Accident claims require: acord, loss, fir, rc, and dl files"
                )
            files = {
                "acord": acord,
                "loss": loss,
                "fir": fir,
                "rc": rc,
                "dl": dl,
            }
        
        # Save all files
        saved_files = {}
        file_urls = {}
        analyses = {}
        
        logger.info(f"Processing {claim_type} claim: {claim_number}")
        
        for file_type, file_obj in files.items():
            if file_obj:
                try:
                    saved_path, public_url = await save_uploaded_file(file_obj, f"{claim_number}_{file_type}")
                    saved_files[file_type] = saved_path
                    file_urls[file_type] = public_url
                    # Analyze each document
                    logger.info(f"Analyzing {file_type} document...")
                    analyses[file_type] = analyze_claim_document(saved_path)
                    logger.info(f"Analysis complete for {file_type}")
                except Exception as e:
                    logger.error(f"Error processing {file_type} file: {e}", exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error processing {file_type} file: {str(e)}"
                    )
        
        # ML Scoring with multiple files
        logger.info("Running ML scoring...")
        try:
            ml_scores = score_claim_multi_file(analyses, claim_type, saved_files)
            logger.info(f"ML scores: fraud={ml_scores.get('fraud_score')}, complexity={ml_scores.get('complexity_score')}")
        except Exception as e:
            logger.error(f"Error in ML scoring: {e}", exc_info=True)
            # Return default scores if ML fails
            ml_scores = {
                "fraud_score": 0.0,
                "complexity_score": 1.0,
                "severity_level": "Low",
                "claim_category": claim_type,
                "insurance_type": "vehicle" if claim_type == "accident" else "health",
                "error": str(e)
            }
        
        # Prepare claim data for Pathway pipeline
        claim_data = {
            "claim_number": claim_number,
            "claim_type": claim_type,
            "name": name,
            "email": email,
            "files": saved_files,
            "file_urls": file_urls,
            "analyses": analyses,
        }
        
        # Apply Dynamic Routing Rules (with Pathway if available)
        logger.info("Applying routing rules...")
        try:
            # Ensure claim_type is in claim_data for routing
            claim_data["claim_type"] = claim_type
            routing_result = apply_routing_rules(ml_scores, claim_data=claim_data)
        except Exception as e:
            logger.error(f"Error in routing: {e}", exc_info=True)
            # Default routing if routing fails
            routing_result = {
                "routing_team": "Fast Track",
                "adjuster": "Standard Adjuster",
                "routing_reasons": ["Default routing due to error"],
                "error": str(e)
            }
        
        # Convert file_urls dict to attachments array format
        attachments_array = [
            {"filename": f"{file_type.upper()}.pdf", "url": url, "type": file_type}
            for file_type, url in file_urls.items()
            if url
        ]
        
        # Persist claim for Team Panel/queues
        claim_record = {
            "claim_number": claim_number,
            "claim_type": claim_type,
            "name": name,
            "email": email,
            "files": file_urls,
            "attachments": attachments_array,  # Also store as array for frontend compatibility
            "analyses": analyses,
            "severity": ml_scores.get("severity_level", "Low"),
            "severity_level": ml_scores.get("severity_level", "Low"),  # Ensure both fields
            "confidence": 1.0 - float(ml_scores.get("fraud_score", 0.0)),
            "routing_team": routing_result.get("routing_team", "Fast Track"),
            "final_adjuster": routing_result.get("adjuster", "Standard Adjuster"),
            "final_team": routing_result.get("routing_team", "Fast Track"),  # Alias for compatibility
            "queue": routing_result.get("routing_team", "Fast Track"),  # Store as queue too
            "ml_scores": {
                "fraud_score": ml_scores.get("fraud_score", 0.0),
                "complexity_score": ml_scores.get("complexity_score", 1.0),
                "severity_level": ml_scores.get("severity_level", "Low"),
                "fraud_label": ml_scores.get("fraud_label", 0),
                "claim_category": ml_scores.get("claim_category", claim_type),
                "litigation_score": ml_scores.get("litigation_score", 0.0),
                "litigation_flag": ml_scores.get("litigation_flag", False),
                "litigation_reasons": ml_scores.get("litigation_reasons", []),
                "subrogation_score": ml_scores.get("subrogation_score", 0.0),
                "subrogation_flag": ml_scores.get("subrogation_flag", False),
                "subrogation_reasons": ml_scores.get("subrogation_reasons", []),
                "features": ml_scores.get("features", {}),
            },
            "routing": routing_result,
            "status": "Processing",
        }
        stored = add_claim(claim_record)

        # Combine results
        logger.info(f"Claim {claim_number} processed successfully. Team: {routing_result.get('routing_team')}")
        return {
            "id": stored.get("id"),
            "status": "uploaded",
            "claim_number": claim_number,
            "claim_type": claim_type,
            "files": file_urls,
            "attachments": attachments_array,  # Include attachments array in response
            "analyses": {k: {"insurance_type": v.get("insurance_type"), "document_type": v.get("document_type")} for k, v in analyses.items()},
            "ml_scores": ml_scores,
            "routing": routing_result,
            "final_team": routing_result.get("routing_team", "Fast Track"),
            "final_adjuster": routing_result.get("adjuster", "Standard Adjuster"),
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/auto")
async def auto_upload_sample(
    claim_type: Optional[str] = Query(None, description="'medical' or 'accident'; random if not provided"),
    name: Optional[str] = Query("Auto Sample", description="Optional name to attach"),
    email: Optional[str] = Query("sample@demo.local", description="Optional email to attach"),
):
    """Create a sample claim by auto-selecting matching documents from the dataset.

    Picks a random index and selects the corresponding required docs from ml/dataset/* folders.
    """
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent
        dataset = base_dir / "ml" / "dataset"

        # Choose claim type if not provided
        ct = claim_type if claim_type in ("medical", "accident") else random.choice(["medical", "accident"])

        def choose_accident() -> Dict[str, str]:
            acc = dataset / "accident"
            acord_dir = acc / "accord_form_100"
            acord_files = sorted([p for p in acord_dir.glob("*.pdf")])
            if not acord_files:
                raise HTTPException(status_code=500, detail="No accident samples found")
            f = random.choice(acord_files)
            # Extract CLM id base e.g., CLM-2025-0001-ACC_SAFE
            m = re.search(r"(CLM-\d{4}-\d{4}-ACC_(SAFE|RISK))_acord\.pdf$", f.name)
            if not m:
                raise HTTPException(status_code=500, detail=f"Unexpected filename format: {f.name}")
            clm_base = m.group(1)

            loss = acc / "loss_reports_100" / f"{clm_base}_loss.pdf"
            rc = acc / "rc_documents_100" / f"{clm_base}_rc.pdf"
            dl = acc / "dl_documents_100" / f"{clm_base}_dl.pdf"
            # police file contains CLM base embedded
            police_dir = acc / "police_reports_100"
            police = None
            for p in police_dir.glob("*.pdf"):
                if clm_base in p.name and p.name.endswith("_police.pdf"):
                    police = p
                    break
            if police is None:
                raise HTTPException(status_code=500, detail=f"Matching police report not found for {clm_base}")

            files = {
                "acord": str(f),
                "loss": str(loss),
                "fir": str(police),
                "rc": str(rc),
                "dl": str(dl),
            }
            for k, v in files.items():
                if not Path(v).exists():
                    raise HTTPException(status_code=500, detail=f"Missing {k} document for {clm_base}")
            return files

        def choose_medical() -> Dict[str, str]:
            hea = dataset / "health"
            acord_dir = hea / "accord_form_100"
            acord_files = sorted([p for p in acord_dir.glob("*.pdf")])
            if not acord_files:
                raise HTTPException(status_code=500, detail="No medical samples found")
            f = random.choice(acord_files)
            # Extract CLM id base e.g., CLM-2025-0001-HEA_SAFE
            m = re.search(r"(CLM-\d{4}-\d{4}-HEA_(SAFE|RISK))_acord\.pdf$", f.name)
            if not m:
                raise HTTPException(status_code=500, detail=f"Unexpected filename format: {f.name}")
            clm_base = m.group(1)

            loss = hea / "loss_reports_100" / f"{clm_base}_loss.pdf"
            hospital = hea / "hospital_bills_100" / f"{clm_base}_hospital.pdf"
            files = {
                "acord": str(f),
                "loss": str(loss),
                "hospital": str(hospital),
            }
            for k, v in files.items():
                if not Path(v).exists():
                    raise HTTPException(status_code=500, detail=f"Missing {k} document for {clm_base}")
            return files

        selected_files = choose_accident() if ct == "accident" else choose_medical()

        # Analyze docs
        analyses = {}
        for key, path in selected_files.items():
            analyses[key] = analyze_claim_document(path)

        # ML scoring
        ml_scores = score_claim_multi_file(analyses, ct, selected_files)

        # Prepare routing
        claim_data = {
            "claim_type": ct,
        }
        routing_result = apply_routing_rules(ml_scores, claim_data=claim_data)

        # Claim number from base
        # Prefer claim id from acord filename
        base_name = Path(selected_files.get("acord", "")).name
        claim_number_match = re.search(r"(CLM-\d{4}-\d{4}-[A-Z]{3}_(SAFE|RISK))_acord\.pdf$", base_name)
        claim_number = claim_number_match.group(1) if claim_number_match else f"CLM-{random.randint(100000,999999)}"

        # Build attachments (non-public dataset paths; for display only)
        attachments_array = []
        for doc_type, p in selected_files.items():
            attachments_array.append({"filename": f"{doc_type.upper()}.pdf", "url": p, "type": doc_type})

        record = {
            "claim_number": claim_number,
            "claim_type": ct,
            "name": name,
            "email": email,
            "files": selected_files,
            "attachments": attachments_array,
            "analyses": analyses,
            "severity": ml_scores.get("severity_level", "Low"),
            "severity_level": ml_scores.get("severity_level", "Low"),
            "confidence": 1.0 - float(ml_scores.get("fraud_score", 0.0)),
            "routing_team": routing_result.get("routing_team", "Fast Track"),
            "final_adjuster": routing_result.get("adjuster", "Standard Adjuster"),
            "final_team": routing_result.get("routing_team", "Fast Track"),
            "queue": routing_result.get("routing_team", "Fast Track"),
            "ml_scores": {
                "fraud_score": ml_scores.get("fraud_score", 0.0),
                "complexity_score": ml_scores.get("complexity_score", 1.0),
                "severity_level": ml_scores.get("severity_level", "Low"),
                "fraud_label": ml_scores.get("fraud_label", 0),
                "claim_category": ml_scores.get("claim_category", ct),
                "litigation_score": ml_scores.get("litigation_score", 0.0),
                "litigation_flag": ml_scores.get("litigation_flag", False),
                "litigation_reasons": ml_scores.get("litigation_reasons", []),
                "subrogation_score": ml_scores.get("subrogation_score", 0.0),
                "subrogation_flag": ml_scores.get("subrogation_flag", False),
                "subrogation_reasons": ml_scores.get("subrogation_reasons", []),
                "features": ml_scores.get("features", {}),
            },
            "routing": routing_result,
            "status": "Processing",
        }

        stored = add_claim(record)

        return {
            "id": stored.get("id"),
            "status": "uploaded",
            "claim_number": claim_number,
            "claim_type": ct,
            "files": selected_files,
            "attachments": attachments_array,
            "analyses": {k: {"insurance_type": v.get("insurance_type"), "document_type": v.get("document_type")} for k, v in analyses.items()},
            "ml_scores": ml_scores,
            "routing": routing_result,
            "final_team": routing_result.get("routing_team", "Fast Track"),
            "final_adjuster": routing_result.get("adjuster", "Standard Adjuster"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in auto upload endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/auto/select")
async def auto_select_sample(
    claim_type: Optional[str] = Query(None, description="'medical' or 'accident'; random if not provided")
):
    """Select a random sample's required file set WITHOUT processing ML or creating a claim.

    Returns a structure with claim_type, claim_number (base), and file_urls pointing to a file-serving endpoint.
    Frontend will fetch each file and attach to its FormData before manual submit.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    dataset = base_dir / "ml" / "dataset"
    ct = claim_type if claim_type in ("medical", "accident") else random.choice(["medical", "accident"])

    def select_accident():
        acc = dataset / "accident"
        acord_dir = acc / "accord_form_100"
        acord_files = sorted(acord_dir.glob("*.pdf"))
        if not acord_files:
            raise HTTPException(status_code=500, detail="No accident samples found")
        f = random.choice(acord_files)
        m = re.search(r"(CLM-\d{4}-\d{4}-ACC_(SAFE|RISK))_acord\.pdf$", f.name)
        if not m:
            raise HTTPException(status_code=500, detail=f"Unexpected filename format: {f.name}")
        clm_base = m.group(1)
        mapping = {
            "acord": acc / "accord_form_100" / f"{clm_base}_acord.pdf",
            "loss": acc / "loss_reports_100" / f"{clm_base}_loss.pdf",
            "rc": acc / "rc_documents_100" / f"{clm_base}_rc.pdf",
            "dl": acc / "dl_documents_100" / f"{clm_base}_dl.pdf",
        }
        # police/fir doc
        police_dir = acc / "police_reports_100"
        police = None
        for p in police_dir.glob("*.pdf"):
            if clm_base in p.name and p.name.endswith("_police.pdf"):
                police = p
                break
        if not police:
            raise HTTPException(status_code=500, detail=f"Police report missing for {clm_base}")
        mapping["fir"] = police
        for k, v in mapping.items():
            if not v.exists():
                raise HTTPException(status_code=500, detail=f"Missing {k} doc for {clm_base}")
        return clm_base, mapping

    def select_medical():
        hea = dataset / "health"
        acord_dir = hea / "accord_form_100"
        acord_files = sorted(acord_dir.glob("*.pdf"))
        if not acord_files:
            raise HTTPException(status_code=500, detail="No medical samples found")
        f = random.choice(acord_files)
        m = re.search(r"(CLM-\d{4}-\d{4}-HEA_(SAFE|RISK))_acord\.pdf$", f.name)
        if not m:
            raise HTTPException(status_code=500, detail=f"Unexpected filename format: {f.name}")
        clm_base = m.group(1)
        mapping = {
            "acord": hea / "accord_form_100" / f"{clm_base}_acord.pdf",
            "loss": hea / "loss_reports_100" / f"{clm_base}_loss.pdf",
            "hospital": hea / "hospital_bills_100" / f"{clm_base}_hospital.pdf",
        }
        for k, v in mapping.items():
            if not v.exists():
                raise HTTPException(status_code=500, detail=f"Missing {k} doc for {clm_base}")
        return clm_base, mapping

    try:
        if ct == "accident":
            clm_base, mapping = select_accident()
        else:
            clm_base, mapping = select_medical()

        # Return file URLs referencing a secure file endpoint
        file_urls = {k: f"/upload/auto/file?path={v}" for k, v in mapping.items()}
        return {
            "claim_type": ct,
            "claim_number_base": clm_base,
            "files": file_urls,
            "required": list(mapping.keys()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting sample: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto/file")
async def get_auto_file(path: str = Query(..., description="Absolute dataset file path returned from /auto/select")):
    """Serve a dataset PDF after validating it's within the dataset directory.
    This avoids exposing arbitrary filesystem paths.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    dataset_root = (base_dir / "ml" / "dataset").resolve()
    requested = Path(path).resolve()
    if not str(requested).startswith(str(dataset_root)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not requested.exists():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(str(requested))
    return FileResponse(str(requested), media_type=mime or "application/pdf", filename=requested.name)
