import { Upload, X, FileText } from "lucide-react";

interface FileUploadSectionProps {
  section: string;
  title: string;
  required?: boolean;
  files: File[];
  onAdd: (fileList: FileList | null) => void;
  onRemove: (index: number) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  inputRef: (el: HTMLInputElement | null) => void;
}

export const FileUploadSection = ({
  title,
  required = false,
  files,
  onAdd,
  onRemove,
  onDragOver,
  onDrop,
  inputRef,
}: FileUploadSectionProps) => {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-6 hover:border-[#a855f7]/30 transition-all duration-300">
      <label className="block text-sm font-semibold text-[#f3f4f6] mb-4">
        {title}
        {required && <span className="text-[#a855f7] ml-1">*</span>}
      </label>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2 mb-4">
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-3 bg-[#0b0b0f] border border-[#2a2a32] rounded-lg group hover:border-[#a855f7]/50 transition-all duration-300"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <FileText className="w-5 h-5 text-[#a855f7] flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[#f3f4f6] truncate group-hover:text-[#a855f7] transition-colors">
                    {file.name}
                  </p>
                  <p className="text-xs text-[#9ca3af]">
                    {formatFileSize(file.size)}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onRemove(index)}
                className="p-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-all duration-300"
                title="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload Zone */}
      <label
        onDragOver={onDragOver}
        onDrop={onDrop}
        className="border-2 border-dashed border-[#2a2a32] rounded-lg p-8 text-center hover:border-[#a855f7] hover:bg-[#a855f7]/5 transition-all duration-300 cursor-pointer block"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={(e) => {
            onAdd(e.target.files);
            if (e.target) e.target.value = "";
          }}
          className="hidden"
        />
        <Upload className="w-12 h-12 mx-auto text-[#6b7280] mb-3 group-hover:text-[#a855f7] transition-colors" />
        <p className="text-[#f3f4f6] font-medium mb-1">
          Drag and drop PDF file here
        </p>
        <p className="text-[#9ca3af] text-sm">or click to browse</p>
        <p className="text-[#6b7280] text-xs mt-2">
          Maximum 20MB per file
        </p>
      </label>
    </div>
  );
};

