import React, { useMemo, useRef, useState } from "react";
import { Send, Bot, UserCircle } from "lucide-react";
import { sendClaimChat, ChatMessage } from "@/api/chat";
import { toast } from "sonner";

interface ClaimChatProps {
  claimId: string;
  claimSummary?: {
    claimant?: string;
    claim_number?: string;
    policy_no?: string;
    loss_type?: string;
  };
}

const ClaimChat: React.FC<ClaimChatProps> = ({ claimId, claimSummary }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const header = useMemo(() => {
    return (
      <div className="flex items-center gap-2">
        <Bot className="w-4 h-4 text-[#a855f7]" />
        <span className="font-semibold">Claim Assistant</span>
      </div>
    );
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    const newUserMsg: ChatMessage = { role: "user", content: text };
    setMessages((m) => [...m, newUserMsg]);
    setInput("");
    setLoading(true);
    try {
      const { answer } = await sendClaimChat(claimId, text, messages);
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch (e: any) {
      toast.error(e?.message || "Chat request failed");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading) handleSend();
    }
  };

  return (
    <div className="bg-[#1a1a22] border border-[#2a2a32] rounded-lg flex flex-col h-[560px] overflow-hidden">
      <div className="px-4 py-3 border-b border-[#2a2a32] text-[#f3f4f6]">
        {header}
        {claimSummary && (
          <p className="mt-1 text-xs text-[#9ca3af] truncate">
            {(claimSummary.claim_number || claimId)} · {claimSummary.claimant} · {claimSummary.loss_type}
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-center text-[#9ca3af] text-sm mt-8">
            Ask about this claim's details, status, severity, extracted document data, or next steps.
          </div>
        ) : (
          messages.map((m, idx) => (
            <div key={idx} className="flex items-start gap-3">
              <div className="mt-1">
                {m.role === "assistant" ? (
                  <Bot className="w-4 h-4 text-[#a855f7]" />
                ) : (
                  <UserCircle className="w-4 h-4 text-[#9ca3af]" />
                )}
              </div>
              <div
                className={
                  "rounded-lg px-3 py-2 text-sm leading-relaxed max-w-[85%] " +
                  (m.role === "assistant"
                    ? "bg-[#0b0b0f] border border-[#2a2a32] text-[#f3f4f6]"
                    : "bg-[#2a2a32] text-white")
                }
              >
                {m.content}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex items-center gap-2 text-[#9ca3af] text-xs">
            <div className="h-2 w-2 rounded-full bg-[#a855f7] animate-pulse" />
            Thinking…
          </div>
        )}
      </div>

      <div className="p-3 border-t border-[#2a2a32]">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={loading}
            placeholder="Ask a question about this claim..."
            className="flex-1 bg-[#0b0b0f] border border-[#2a2a32] rounded-md px-3 py-2 text-sm text-[#f3f4f6] placeholder:text-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#a855f7]/40"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="inline-flex items-center justify-center rounded-md bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white px-3 py-2 text-sm font-medium hover:from-[#9333ea] hover:to-[#db2777] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClaimChat;
