import { readSSE } from "./sse";
import type { ChatEvent, DocumentInfo } from "./types";

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch("/api/documents");
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/documents", { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await errorMessage(res));
}

export interface ChatParams {
  question: string;
  history: { role: "user" | "assistant"; content: string }[];
  documentIds: string[] | null;
  signal: AbortSignal;
}

export async function* streamChat(params: ChatParams): AsyncGenerator<ChatEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: params.question,
      history: params.history,
      document_ids: params.documentIds,
    }),
    signal: params.signal,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  yield* readSSE<ChatEvent>(res);
}
