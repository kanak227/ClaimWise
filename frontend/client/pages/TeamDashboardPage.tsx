import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ArrowLeft, RefreshCw, Filter, CheckCircle2, AlertTriangle, Clock } from "lucide-react";
import { toast } from "sonner";
import { getClaims } from "@/api/claims";

// Flexible claim type matching backend payload we use in UI
type Claim = {
  id?: string;
  claim_number: string;
  status?: string;
  fraud_score?: number;
  complexity_score?: number;
  severity_level?: string;
  routing_team?: string;
  adjuster?: string;
  claim_type?: string;
  created_at?: string;
  ml_scores?: {
    fraud_score?: number;
    complexity_score?: number;
    severity_level?: string;
  };
};

const TeamDashboardPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const team = location.state?.team || "Fast Track";
  const claimId = location.state?.claimId;

  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    fetchClaims();
    // Refresh every 5 seconds for real-time updates
    const interval = setInterval(fetchClaims, 5000);
    return () => clearInterval(interval);
  }, [team]);

  const fetchClaims = async () => {
    try {
      setLoading(true);
      // Fetch claims filtered by team/queue
  const response = await getClaims({ queue: team === "All Teams" ? undefined : team });
  setClaims(response as unknown as Claim[]);
    } catch (error: any) {
      toast.error("Failed to fetch claims");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const filteredClaims = claims.filter((claim) => {
    if (filter === "all") return true;
    if (filter === "high-fraud") {
      const fraudScore = claim.fraud_score ?? claim.ml_scores?.fraud_score ?? 0;
      return fraudScore >= 0.6;
    }
    if (filter === "high-complexity") {
      const complexityScore = claim.complexity_score ?? claim.ml_scores?.complexity_score ?? 1.0;
      return complexityScore >= 3.5;
    }
    if (filter === "high-severity") {
      const severity = (claim.severity_level ?? claim.ml_scores?.severity_level ?? "Low").toLowerCase();
      return severity === "high";
    }
    if (filter === "pending") {
      const status = (claim.status || "").toLowerCase();
      return status === "pending" || status === "processing";
    }
    return true;
  });

  const getStatusIcon = (fraudScore?: number) => {
    if (!fraudScore) return <Clock className="w-5 h-5 text-gray-400" />;
    if (fraudScore >= 0.6) return <AlertTriangle className="w-5 h-5 text-red-400" />;
    return <CheckCircle2 className="w-5 h-5 text-green-400" />;
  };

  const getStatusColor = (fraudScore?: number) => {
    if (!fraudScore) return "text-gray-400";
    if (fraudScore >= 0.6) return "text-red-400";
    return "text-green-400";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0b0b0f] to-[#121216]">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <button
              onClick={() => navigate("/")}
              className="flex items-center gap-2 text-[#9ca3af] hover:text-[#f3f4f6] mb-4 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </button>
            <h1 className="text-3xl font-bold text-[#f3f4f6] mb-2">
              {team} Team Dashboard
            </h1>
            <p className="text-[#9ca3af]">
              Real-time queue of claims routed to your team
            </p>
          </div>
          <button
            onClick={fetchClaims}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-[#1a1a22] border border-[#2a2a32] text-[#f3f4f6] rounded-lg hover:bg-[#2a2a32] transition-all duration-300"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm text-[#9ca3af] mb-1">Total Claims</p>
            <p className="text-2xl font-bold text-[#f3f4f6]">{claims.length}</p>
          </div>
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm text-[#9ca3af] mb-1">High Fraud Risk</p>
            <p className="text-2xl font-bold text-red-400">
              {claims.filter((c) => {
                const fraudScore = c.fraud_score ?? c.ml_scores?.fraud_score ?? 0;
                return fraudScore >= 0.6;
              }).length}
            </p>
          </div>
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm text-[#9ca3af] mb-1">Pending Review</p>
            <p className="text-2xl font-bold text-yellow-400">
              {claims.filter((c) => (c.status || "").toLowerCase() === "pending").length}
            </p>
          </div>
          <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg p-4">
            <p className="text-sm text-[#9ca3af] mb-1">Processed</p>
            <p className="text-2xl font-bold text-green-400">
              {claims.filter((c) => (c.status || "").toLowerCase() === "processed").length}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 flex items-center gap-4 flex-wrap">
          <Filter className="w-5 h-5 text-[#9ca3af]" />
          <div className="flex gap-2 flex-wrap">
            {[
              { id: "all", label: "All" },
              { id: "high-fraud", label: "High Fraud" },
              { id: "high-complexity", label: "High Complexity" },
              { id: "high-severity", label: "High Severity" },
              { id: "pending", label: "Pending" }
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`px-4 py-2 rounded-lg border transition-all duration-300 text-sm ${
                  filter === f.id
                    ? "bg-[#a855f7] border-[#a855f7] text-white shadow-lg shadow-[#a855f7]/30"
                    : "bg-[#1a1a22] border-[#2a2a32] text-[#f3f4f6] hover:border-[#a855f7]/50 hover:bg-[#2a2a32]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Claims Queue */}
        <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg overflow-hidden">
          <div className="p-6 border-b border-[#2a2a32]">
            <h2 className="text-xl font-semibold text-[#f3f4f6]">Claims Queue</h2>
          </div>
          
          {loading && claims.length === 0 ? (
            <div className="p-12 text-center">
              <RefreshCw className="w-8 h-8 text-[#a855f7] animate-spin mx-auto mb-4" />
              <p className="text-[#9ca3af]">Loading claims...</p>
            </div>
          ) : filteredClaims.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-[#9ca3af]">No claims found in queue</p>
            </div>
          ) : (
            <div className="divide-y divide-[#2a2a32]">
              {filteredClaims.map((claim) => (
                <div
                  key={claim.id || claim.claim_number}
                  className="p-6 hover:bg-[#0b0b0f] transition-all duration-300 cursor-pointer"
                  onClick={() => navigate(`/claims/${claim.id || claim.claim_number}`)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1">
                      {getStatusIcon(claim.fraud_score)}
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <p className="text-lg font-semibold text-[#f3f4f6]">
                            {claim.claim_number}
                          </p>
                          {claim.claim_type && (
                            <span className="px-2 py-1 text-xs bg-[#a855f7]/20 text-[#a855f7] rounded">
                              {claim.claim_type}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-[#9ca3af] flex-wrap">
                          {(() => {
                            const fraudScore = claim.fraud_score ?? claim.ml_scores?.fraud_score;
                            const complexityScore = claim.complexity_score ?? claim.ml_scores?.complexity_score;
                            const severityLevel = claim.severity_level ?? claim.ml_scores?.severity_level;
                            
                            return (
                              <>
                                {fraudScore !== undefined && (
                                  <span className={getStatusColor(fraudScore)}>
                                    Fraud: {(fraudScore * 100).toFixed(1)}%
                                  </span>
                                )}
                                {complexityScore !== undefined && (
                                  <span className="text-[#a855f7]">
                                    Complexity: {complexityScore.toFixed(1)}
                                  </span>
                                )}
                                {severityLevel && (
                                  <span className={
                                    severityLevel === "High" ? "text-red-400" :
                                    severityLevel === "Medium" ? "text-yellow-400" :
                                    "text-green-400"
                                  }>
                                    Severity: {severityLevel}
                                  </span>
                                )}
                                {claim.adjuster && (
                                  <span>Assignee: {claim.adjuster}</span>
                                )}
                                {claim.created_at && (
                                  <span>{new Date(claim.created_at).toLocaleDateString()}</span>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-sm font-medium mb-1 ${
                        (claim.status || "").toLowerCase() === "processed" ? "text-green-400" : 
                        (claim.status || "").toLowerCase() === "pending" ? "text-yellow-400" : 
                        "text-gray-400"
                      }`}>
                        {claim.status || "Pending"}
                      </p>
                      {claimId === (claim.id || claim.claim_number) && (
                        <span className="text-xs text-[#a855f7]">New</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TeamDashboardPage;

