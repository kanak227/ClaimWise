import React from "react";
import { Upload, X, FileText } from "lucide-react";

type SectionKey = "acord" | "loss" | "hospital" | "fir" | "rc" | "dl";

export interface CompactUploadBarProps {
  claimType: "medical" | "accident" | "";
  files: Record<SectionKey, File[]>;
  onAdd: (section: SectionKey, files: FileList | null) => void;
  onRemove: (section: SectionKey, index: number) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent, section: SectionKey) => void;
  inputRefs: Record<SectionKey, HTMLInputElement | null>;
  setInputRef: (section: SectionKey, el: HTMLInputElement | null) => void;
}

const LABELS: Record<SectionKey, string> = {
  acord: "ACORD",
  loss: "Loss",
  hospital: "Hospital",
  fir: "FIR",
  rc: "RC",
  dl: "DL",
};

export const CompactUploadBar: React.FC<CompactUploadBarProps> = ({
  claimType,
  files,
  onAdd,
  onRemove,
  onDragOver,
  onDrop,
  setInputRef,
}) => {
  const sections: SectionKey[] = claimType === "medical"
    ? ["acord", "loss", "hospital"]
    : claimType === "accident"
    ? ["acord", "loss", "fir", "rc", "dl"]
    : [];

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-3 hover:border-[#a855f7]/30 transition-all duration-300 sticky top-0 z-10">
      <div className="flex items-center gap-3 mb-2">
        <div className="shrink-0 px-2 py-1 rounded-md bg-[#0b0b0f] border border-[#2a2a32] text-[#9ca3af] text-[10px] uppercase tracking-wide">
          Required Docs
        </div>
        <p className="text-xs text-[#6b7280]">Upload PDFs for each required document below.</p>
      </div>
      <div className="flex flex-wrap items-stretch gap-3">
        {sections.map((section) => {
          const list = files[section] || [];
          const hasFile = list.length > 0;
          const first = list[0];
          const extraCount = list.length > 1 ? list.length - 1 : 0;
          return (
            <div key={section} className="flex items-center">
              <label
                onDragOver={onDragOver}
                onDrop={(e) => onDrop(e, section)}
                className={`group relative flex items-center gap-2 px-3 py-2 rounded-md border text-xs cursor-pointer select-none transition-all duration-300 ${
                  hasFile
                    ? "bg-[#0b0b0f] border-[#2a2a32] hover:border-[#a855f7]/50"
                    : "bg-[#0d0f14] border-[#2a2a32] hover:border-[#a855f7] hover:bg-[#a855f7]/5"
                }`}
                title={hasFile && first ? `${first.name} • ${formatFileSize(first.size)}` : `Upload ${LABELS[section]} PDF`}
              >
                <input
                  ref={(el) => setInputRef(section, el)}
                  type="file"
                  accept=".pdf"
                  onChange={(e) => {
                    onAdd(section, e.target.files);
                    if (e.target) e.target.value = "";
                  }}
                  className="hidden"
                />
                {hasFile ? (
                  <>
                    <FileText className="w-4 h-4 text-[#a855f7]" />
                    <span className="text-[#f3f4f6] truncate max-w-[140px]">
                      {LABELS[section]}: {first?.name}
                    </span>
                    {extraCount > 0 && (
                      <span className="ml-1 text-[10px] text-[#9ca3af]">+{extraCount}</span>
                    )}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        // remove first file; keep others if any
                        onRemove(section, 0);
                      }}
                      className="ml-1 p-1 rounded hover:bg-red-500/10 text-red-400 hover:text-red-300"
                      aria-label={`Remove ${LABELS[section]} file`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 text-[#9ca3af] group-hover:text-[#a855f7]" />
                    <span className="text-[#f3f4f6] group-hover:text-[#a855f7]">{LABELS[section]}</span>
                    <span className="text-[#a855f7] ml-1">*</span>
                  </>
                )}
              </label>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CompactUploadBar;
