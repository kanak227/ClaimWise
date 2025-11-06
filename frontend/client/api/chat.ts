import axios from "axios";
import { API_BASE, API_ENDPOINTS } from "./config";

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequestBody {
  message: string;
  history?: ChatMessage[];
}

export interface ChatResponseBody {
  answer: string;
}

export async function sendClaimChat(
  claimId: string,
  message: string,
  history: ChatMessage[] = []
): Promise<ChatResponseBody> {
  const url = `${API_BASE}${API_ENDPOINTS.claims.chat(claimId)}`;
  const { data } = await axios.post<ChatResponseBody>(url, {
    message,
    history,
  } as ChatRequestBody);
  return data;
}
