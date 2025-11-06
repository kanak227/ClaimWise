import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

interface RoutingModalProps {
  open: boolean;
  onClose: () => void;
  routingResult: {
    claimId: string;
    fraudScore: number;
    complexityScore?: number;
    severityLevel?: string;
    routingTeam: string;
    adjuster: string;
    routingReasons: string[];
  } | null;
  fraudThreshold: number;
}

export const RoutingModal = ({ open, onClose, routingResult, fraudThreshold }: RoutingModalProps) => {
  if (!routingResult) return null;

  const { fraudScore, routingTeam, adjuster, routingReasons, claimId } = routingResult;
  const isHighFraud = fraudScore >= fraudThreshold;
  const isRouted = routingTeam && routingTeam !== "Fast Track";

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#1a1a22] border-[#2a2a32] text-[#f3f4f6] max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-[#f3f4f6] flex items-center gap-3">
            {isHighFraud ? (
              <>
                <AlertTriangle className="w-6 h-6 text-red-400" />
                High Fraud Risk Detected
              </>
            ) : isRouted ? (
              <>
                <CheckCircle2 className="w-6 h-6 text-green-400" />
                Claim Routed Successfully
              </>
            ) : (
              <>
                <CheckCircle2 className="w-6 h-6 text-[#a855f7]" />
                Claim Processed
              </>
            )}
          </DialogTitle>
          <DialogDescription className="text-[#9ca3af]">
            Your claim has been analyzed and routed to the appropriate team
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Claim ID */}
          <div className="bg-[#0b0b0f] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm text-[#9ca3af] mb-1">Claim ID</p>
            <p className="text-lg font-mono text-[#a855f7] font-bold">{claimId}</p>
          </div>

          {/* ML Scores Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Fraud Score */}
            <div className="bg-[#0b0b0f] border border-[#2a2a32] rounded-lg p-4">
              <div className="flex justify-between items-center mb-2">
                <p className="text-sm text-[#9ca3af]">Fraud Score</p>
                <p className={`text-lg font-bold ${isHighFraud ? 'text-red-400' : 'text-green-400'}`}>
                  {Number.isFinite(fraudScore) ? (fraudScore * 100).toFixed(1) : "--"}%
                </p>
              </div>
              <div className="w-full bg-[#2a2a32] rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    isHighFraud 
                      ? 'bg-gradient-to-r from-red-500 to-red-600' 
                      : fraudScore > 0.3
                      ? 'bg-gradient-to-r from-yellow-500 to-yellow-600'
                      : 'bg-gradient-to-r from-green-500 to-green-600'
                  }`}
                  style={{ width: `${Math.min(Number.isFinite(fraudScore) ? fraudScore * 100 : 0, 100)}%` }}
                />
              </div>
              <p className="text-xs text-[#6b7280] mt-2">
                Threshold: {(fraudThreshold * 100).toFixed(0)}%
              </p>
            </div>

            {/* Complexity Score */}
            {routingResult.complexityScore !== undefined && (
              <div className="bg-[#0b0b0f] border border-[#2a2a32] rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-sm text-[#9ca3af]">Complexity</p>
                  <p className="text-lg font-bold text-[#a855f7]">
                    {routingResult.complexityScore.toFixed(1)}
                  </p>
                </div>
                <div className="w-full bg-[#2a2a32] rounded-full h-2 overflow-hidden">
                  <div
                    className="h-2 rounded-full transition-all duration-300 bg-gradient-to-r from-[#a855f7] to-[#ec4899]"
                    style={{ width: `${Math.min((routingResult.complexityScore / 5) * 100, 100)}%` }}
                  />
                </div>
                <p className="text-xs text-[#6b7280] mt-2">
                  {routingResult.complexityScore >= 3.5 ? "High" : routingResult.complexityScore >= 2 ? "Medium" : "Low"}
                </p>
              </div>
            )}

            {/* Severity Level */}
            {routingResult.severityLevel && (
              <div className="bg-[#0b0b0f] border border-[#2a2a32] rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-sm text-[#9ca3af]">Severity</p>
                  <p className={`text-lg font-bold ${
                    routingResult.severityLevel === "High" ? "text-red-400" :
                    routingResult.severityLevel === "Medium" ? "text-yellow-400" :
                    "text-green-400"
                  }`}>
                    {routingResult.severityLevel}
                  </p>
                </div>
                <div className="w-full bg-[#2a2a32] rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-2 rounded-full transition-all duration-300 ${
                      routingResult.severityLevel === "High" ? "bg-red-500" :
                      routingResult.severityLevel === "Medium" ? "bg-yellow-500" :
                      "bg-green-500"
                    }`}
                    style={{ 
                      width: routingResult.severityLevel === "High" ? "100%" :
                             routingResult.severityLevel === "Medium" ? "66%" : "33%"
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Routing Information */}
          <div className="bg-[#0b0b0f] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm font-semibold text-[#f3f4f6] mb-3">Routing Decision</p>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[#6b7280] text-xs block mb-1">Team Type:</span>
                  <p className="text-[#f3f4f6] font-semibold text-base">{routingTeam || "Fast Track"}</p>
                  <p className="text-[#9ca3af] text-xs mt-1">
                    {routingTeam?.includes("SIU") || routingTeam?.includes("Fraud") ? "Special Investigation Unit" :
                     routingTeam?.includes("Health Dept") ? 
                       (routingTeam.includes("High") ? "Health Department - High Complexity Team" :
                        routingTeam.includes("Mid") ? "Health Department - Medium Complexity Team" :
                        "Health Department - Standard Processing Team") :
                     routingTeam?.includes("Accident Dept") ?
                       (routingTeam.includes("High") ? "Accident Department - High Complexity Team" :
                        routingTeam.includes("Mid") ? "Accident Department - Medium Complexity Team" :
                        "Accident Department - Standard Processing Team") :
                     routingTeam?.includes("Complex Claims") ? "High Complexity Team" :
                     routingTeam?.includes("Litigation") ? "Legal Affairs Team" :
                     routingTeam?.includes("Subrogation") ? "Recovery Team" :
                     routingTeam?.includes("Total Loss") ? "Total Loss Specialists" :
                     routingTeam?.includes("Bodily Injury") ? "Medical Claims Team" :
                     "Standard Processing Team"}
                  </p>
                </div>
                <div>
                  <span className="text-[#6b7280] text-xs block mb-1">Team Skill Level:</span>
                  <p className="text-[#f3f4f6] font-semibold text-base">{adjuster || "Standard Adjuster"}</p>
                  <p className="text-[#9ca3af] text-xs mt-1">
                    {adjuster?.includes("SIU") || adjuster?.includes("Investigator") ? "Expert Level" :
                     adjuster?.includes("Senior") ? "Senior Level" :
                     adjuster?.includes("Specialist") ? "Specialist Level" :
                     "Standard Level"}
                  </p>
                </div>
              </div>
              {routingReasons.length > 0 && (
                <div className="pt-3 border-t border-[#2a2a32]">
                  <span className="text-[#6b7280] text-xs block mb-2">Routing Reasons:</span>
                  <ul className="list-disc list-inside text-[#f3f4f6] text-sm space-y-1">
                    {routingReasons.map((reason, idx) => (
                      <li key={idx} className="text-[#a855f7]">{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Status Message */}
          <div className={`border rounded-lg p-4 ${
            isHighFraud 
              ? 'bg-red-500/10 border-red-500/30' 
              : isRouted 
              ? 'bg-green-500/10 border-green-500/30'
              : 'bg-[#a855f7]/10 border-[#a855f7]/30'
          }`}>
            <p className="text-sm text-[#f3f4f6]">
              {isHighFraud 
                ? `⚠️ High fraud risk detected. Claim routed to ${routingTeam} for investigation.`
                : isRouted
                ? `✅ Claim successfully routed to ${routingTeam} team.`
                : '✅ Claim processed and added to queue.'}
            </p>
          </div>

          {/* Action Button */}
          <button
            onClick={onClose}
            className="w-full px-6 py-3 bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white rounded-lg hover:from-[#9333ea] hover:to-[#db2777] transition-all duration-300 ease-in-out font-medium shadow-lg shadow-[#a855f7]/20 hover:shadow-[#a855f7]/40"
          >
            {isHighFraud ? "View Team Dashboard" : "Continue"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

