import React, { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload,
  X,
  FileText,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { uploadClaim } from "@/api/claims";
import type { AxiosProgressEvent } from "axios";
import { RoutingModal } from "@/components/shared/RoutingModal";
import { FileUploadSection } from "@/components/shared/FileUploadSection";

// Simplified - just a list of files, no preview needed

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
const ACCEPTED_FILE_TYPES = ".pdf";

const UploadPage = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    claim_type: "", // "medical" or "accident"
  });

  const [files, setFiles] = useState<{
    acord: File[];
    loss: File[];
    hospital: File[]; // Medical only
    fir: File[]; // Accident only
    rc: File[]; // Accident only
    dl: File[]; // Accident only
  }>({
    acord: [],
    loss: [],
    hospital: [],
    fir: [],
    rc: [],
    dl: [],
  });

  const [uploadProgress, setUploadProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [claimId, setClaimId] = useState<string>("");
  const [showRoutingModal, setShowRoutingModal] = useState(false);
  const [routingResult, setRoutingResult] = useState<{
    claimId: string;
    fraudScore: number;
    complexityScore?: number;
    severityLevel?: string;
    routingTeam: string;
    adjuster: string;
    routingReasons: string[];
    fullResponse?: any;
  } | null>(null);
  const [fraudThreshold] = useState(0.6); // Fraud score threshold

  // File input refs for each section
  const fileInputRefs = useRef<{
    acord: HTMLInputElement | null;
    loss: HTMLInputElement | null;
    hospital: HTMLInputElement | null;
    fir: HTMLInputElement | null;
    rc: HTMLInputElement | null;
    dl: HTMLInputElement | null;
  }>({
    acord: null,
    loss: null,
    hospital: null,
    fir: null,
    rc: null,
    dl: null,
  });

  const handleFormChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const { name, value } = e.target;
      setForm((prev) => ({
        ...prev,
        [name]: value,
      }));
      // Reset files when claim type changes
      if (name === "claim_type") {
        setFiles({
          acord: [],
          loss: [],
          hospital: [],
          fir: [],
          rc: [],
          dl: [],
        });
      }
    },
    []
  );

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File ${file.name} exceeds 20MB limit`;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return `File ${file.name} is not a PDF`;
    }
    return null;
  };

  const handleFileAdd = useCallback(
    (section: keyof typeof files, newFiles: FileList | null) => {
      if (!newFiles || newFiles.length === 0) return;

      const validFiles: File[] = [];
      const errors: string[] = [];

      Array.from(newFiles).forEach((file) => {
        const error = validateFile(file);
        if (error) {
          errors.push(error);
        } else {
          validFiles.push(file);
        }
      });

      if (errors.length > 0) {
        toast.error(errors.join(", "));
      }

      if (validFiles.length > 0) {
        setFiles((prev) => ({
          ...prev,
          [section]: [...prev[section], ...validFiles],
        }));
        toast.success(`Added ${validFiles.length} file(s) to ${section}`);
      }
    },
    []
  );

  const handleFileRemove = useCallback(
    (section: keyof typeof files, index: number) => {
      setFiles((prev) => ({
        ...prev,
        [section]: prev[section].filter((_, i) => i !== index),
      }));
    },
    []
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, section: keyof typeof files) => {
      e.preventDefault();
      e.stopPropagation();
      handleFileAdd(section, e.dataTransfer.files);
    },
    [handleFileAdd]
  );

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate required fields
    if (!form.name || !form.email) {
      toast.error("Please fill in name and email");
      return;
    }

    if (!form.claim_type) {
      toast.error("Please select a claim type");
      return;
    }

    // Validate files based on claim type
    if (form.claim_type === "medical") {
      if (files.acord.length === 0 || files.loss.length === 0 || files.hospital.length === 0) {
        toast.error("Please upload ACORD, Loss, and Hospital Bill documents");
        return;
      }
    } else if (form.claim_type === "accident") {
      if (files.acord.length === 0 || files.loss.length === 0 || files.fir.length === 0 || 
          files.rc.length === 0 || files.dl.length === 0) {
        toast.error("Please upload all required documents: ACORD, Loss, FIR, RC, and DL");
        return;
      }
    }

    setLoading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();

      // Generate claim number
      const claimNumber = `CLM-${Date.now()}`;
      formData.append("claim_number", claimNumber);
      formData.append("claim_type", form.claim_type);
      formData.append("name", form.name);
      formData.append("email", form.email);

      // Upload files based on claim type
      if (form.claim_type === "medical") {
        formData.append("acord", files.acord[0]);
        formData.append("loss", files.loss[0]);
        formData.append("hospital", files.hospital[0]);
      } else if (form.claim_type === "accident") {
        formData.append("acord", files.acord[0]);
        formData.append("loss", files.loss[0]);
        formData.append("fir", files.fir[0]);
        formData.append("rc", files.rc[0]);
        formData.append("dl", files.dl[0]);
      }

      const onUploadProgress = (progressEvent: AxiosProgressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress(percentCompleted);
        }
      };

      const response = await uploadClaim(formData, onUploadProgress);
      
      // Backend returns: { claim_number, ml_scores: { fraud_score, complexity_score, severity_level }, routing, final_team }
      const claimId = response.claim_number || response.id || claimNumber;
      const mlScores = (response as any).ml_scores || {};
      const fraudScore = mlScores.fraud_score || 0;
      const complexityScore = mlScores.complexity_score || 1.0;
      const severityLevel = mlScores.severity_level || "Low";
      
      setClaimId(claimId);
      setUploadProgress(100);
      
      // Store routing result for modal
      const responseAny = response as any;
      setRoutingResult({
        claimId,
        fraudScore,
        complexityScore,
        severityLevel,
        routingTeam: response.final_team || responseAny.routing?.routing_team,
        adjuster: responseAny.final_adjuster || responseAny.routing?.adjuster,
        routingReasons: (() => {
          const reasons = responseAny.routing?.routing_reasons;
          if (Array.isArray(reasons)) return reasons;
          if (responseAny.routing?.routing_reason) return [responseAny.routing.routing_reason];
          return [];
        })(),
        fullResponse: response,
      });
      
      // Show routing modal
      setShowRoutingModal(true);
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.message ||
        error.message ||
        "Failed to submit claim";
      toast.error(errorMessage);
      setUploadProgress(0);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = useCallback(() => {
    setForm({
      name: "",
      email: "",
      claim_type: "",
    });
    setFiles({
      acord: [],
      loss: [],
      hospital: [],
      fir: [],
      rc: [],
      dl: [],
    });
    // Reset all file inputs
    Object.values(fileInputRefs.current).forEach((ref) => {
      if (ref) ref.value = "";
    });
    toast.info("Form reset");
  }, []);

  // Handle routing modal close with redirect
  const handleRoutingModalClose = useCallback(() => {
    setShowRoutingModal(false);
    if (!routingResult) return;

    const { fraudScore } = routingResult;
    
    if (fraudScore >= fraudThreshold) {
      // Above threshold → redirect to team dashboard
      navigate("/team-dashboard", { 
        state: { 
          team: routingResult.routingTeam,
          claimId: routingResult.claimId 
        } 
      });
    } else {
      // Below threshold → redirect to homepage
      navigate("/");
    }
  }, [routingResult, fraudThreshold, navigate]);

  // Removed conditional sections - keeping only basic file upload

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0b0b0f] to-[#121216] flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="relative mb-6">
            <Loader2 className="w-16 h-16 text-[#a855f7] animate-spin mx-auto" />
          </div>
          <h2 className="text-2xl font-bold text-[#f3f4f6] mb-4">
            Uploading Your Claim...
          </h2>
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-4 mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-[#9ca3af]">Progress</span>
              <span className="text-sm font-bold text-[#a855f7]">
                {uploadProgress}%
              </span>
            </div>
            <div className="w-full bg-[#0b0b0f] rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#a855f7] to-[#ec4899] h-2 rounded-full transition-all duration-300 shadow-lg shadow-[#a855f7]/30"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
          <p className="text-[#9ca3af] text-sm">
            Please don't close this page
          </p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0b0b0f] to-[#121216] flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="mb-6 flex justify-center">
            <CheckCircle2 className="w-24 h-24 text-[#a855f7] animate-bounce" />
          </div>
          <h1 className="text-3xl font-bold text-[#f3f4f6] mb-2">
            Claim Submitted Successfully!
          </h1>
          <p className="text-[#9ca3af] mb-6">
            Your insurance claim has been received and is being processed by our
            AI system.
          </p>
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-6 mb-8">
            <p className="text-sm text-[#9ca3af] mb-2">Your Claim ID</p>
            <p className="text-2xl font-bold text-[#a855f7] font-mono">
              {claimId}
            </p>
            <p className="text-xs text-[#6b7280] mt-2">
              Save this ID for your records
            </p>
          </div>
          <button
            onClick={() => navigate("/")}
            className="w-full px-6 py-3 bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white rounded-lg hover:from-[#9333ea] hover:to-[#db2777] transition-all duration-300 ease-in-out font-medium shadow-lg shadow-[#a855f7]/20 hover:shadow-[#a855f7]/40"
          >
            Back Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0b0b0f] to-[#121216]">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-[#f3f4f6] mb-2">
            File Your Claim
          </h1>
          <p className="text-[#9ca3af]">
            Complete the form below to submit your insurance claim
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Simple Form Section */}
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-6 hover:border-[#a855f7]/30 transition-all duration-300">
            <h2 className="text-xl font-semibold text-[#f3f4f6] mb-6">
              Claim Information <span className="text-[#a855f7]">*</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[#9ca3af] mb-2">
                  Full Name <span className="text-[#a855f7]">*</span>
                </label>
                <input
                  type="text"
                  name="name"
                  required
                  value={form.name}
                  onChange={handleFormChange}
                  className="w-full px-4 py-2 rounded-lg bg-[#0d0f14] border border-gray-700 text-[#f3f4f6] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#a855f7] focus:border-[#a855f7] transition-all duration-300"
                  placeholder="John Doe"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#9ca3af] mb-2">
                  Email <span className="text-[#a855f7]">*</span>
                </label>
                <input
                  type="email"
                  name="email"
                  required
                  value={form.email}
                  onChange={handleFormChange}
                  className="w-full px-4 py-2 rounded-lg bg-[#0d0f14] border border-gray-700 text-[#f3f4f6] placeholder-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#a855f7] focus:border-[#a855f7] transition-all duration-300"
                  placeholder="john@example.com"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-[#9ca3af] mb-2">
                  Claim Type <span className="text-[#a855f7]">*</span>
                </label>
                <select
                  name="claim_type"
                  required
                  value={form.claim_type}
                  onChange={handleFormChange}
                  className="w-full px-4 py-2 rounded-lg bg-[#0d0f14] border border-gray-700 text-[#f3f4f6] focus:outline-none focus:ring-2 focus:ring-[#a855f7] focus:border-[#a855f7] transition-all duration-300"
                >
                  <option value="">Select claim type</option>
                  <option value="medical">Medical</option>
                  <option value="accident">Accident</option>
                </select>
              </div>
            </div>
          </div>

          {/* File Upload Sections - Conditional based on claim type */}
          {form.claim_type === "medical" && (
            <>
              {/* Medical: ACORD */}
              <FileUploadSection
                section="acord"
                title="ACORD Form"
                required
                files={files.acord}
                onAdd={(fileList) => handleFileAdd("acord", fileList)}
                onRemove={(index) => handleFileRemove("acord", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "acord")}
                inputRef={(el) => { fileInputRefs.current.acord = el; }}
              />
              
              {/* Medical: Loss */}
              <FileUploadSection
                section="loss"
                title="Loss Report"
                required
                files={files.loss}
                onAdd={(fileList) => handleFileAdd("loss", fileList)}
                onRemove={(index) => handleFileRemove("loss", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "loss")}
                inputRef={(el) => { fileInputRefs.current.loss = el; }}
              />
              
              {/* Medical: Hospital Bill */}
              <FileUploadSection
                section="hospital"
                title="Hospital Bill"
                required
                files={files.hospital}
                onAdd={(fileList) => handleFileAdd("hospital", fileList)}
                onRemove={(index) => handleFileRemove("hospital", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "hospital")}
                inputRef={(el) => { fileInputRefs.current.hospital = el; }}
              />
            </>
          )}

          {form.claim_type === "accident" && (
            <>
              {/* Accident: ACORD */}
              <FileUploadSection
                section="acord"
                title="ACORD Form"
                required
                files={files.acord}
                onAdd={(fileList) => handleFileAdd("acord", fileList)}
                onRemove={(index) => handleFileRemove("acord", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "acord")}
                inputRef={(el) => { fileInputRefs.current.acord = el; }}
              />
              
              {/* Accident: Loss */}
              <FileUploadSection
                section="loss"
                title="Loss Report"
                required
                files={files.loss}
                onAdd={(fileList) => handleFileAdd("loss", fileList)}
                onRemove={(index) => handleFileRemove("loss", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "loss")}
                inputRef={(el) => { fileInputRefs.current.loss = el; }}
              />
              
              {/* Accident: FIR */}
              <FileUploadSection
                section="fir"
                title="FIR (Police Report)"
                required
                files={files.fir}
                onAdd={(fileList) => handleFileAdd("fir", fileList)}
                onRemove={(index) => handleFileRemove("fir", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "fir")}
                inputRef={(el) => { fileInputRefs.current.fir = el; }}
              />
              
              {/* Accident: RC */}
              <FileUploadSection
                section="rc"
                title="RC (Registration Certificate)"
                required
                files={files.rc}
                onAdd={(fileList) => handleFileAdd("rc", fileList)}
                onRemove={(index) => handleFileRemove("rc", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "rc")}
                inputRef={(el) => { fileInputRefs.current.rc = el; }}
              />
              
              {/* Accident: DL */}
              <FileUploadSection
                section="dl"
                title="DL (Driving License)"
                required
                files={files.dl}
                onAdd={(fileList) => handleFileAdd("dl", fileList)}
                onRemove={(index) => handleFileRemove("dl", index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, "dl")}
                inputRef={(el) => { fileInputRefs.current.dl = el; }}
              />
            </>
          )}

          {/* Submit Buttons */}
          <div className="flex gap-4 pt-6">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="flex-1 px-6 py-3 border border-[#2a2a32] text-[#f3f4f6] rounded-lg hover:bg-[#1a1a22] hover:border-[#a855f7]/50 transition-all duration-300 font-medium"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="flex-1 px-6 py-3 border border-[#2a2a32] text-[#9ca3af] rounded-lg hover:bg-[#1a1a22] hover:text-[#f3f4f6] transition-all duration-300 font-medium"
            >
              Reset
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white rounded-lg hover:from-[#9333ea] hover:to-[#db2777] transition-all duration-300 ease-in-out font-medium shadow-lg shadow-[#a855f7]/20 hover:shadow-[#a855f7]/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Submit Claim
            </button>
          </div>
        </form>
      </div>

      {/* Routing Modal */}
      {showRoutingModal && routingResult && (
        <RoutingModal
          open={showRoutingModal}
          onClose={handleRoutingModalClose}
          routingResult={routingResult}
          fraudThreshold={fraudThreshold}
        />
      )}
    </div>
  );
};

export default UploadPage;