export interface DocumentInfo {
  id: string;
  filename: string;
  media_type: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
}

export interface Source {
  ref: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  content: string;
  similarity: number;
}

export type Outcome =
  | "answered"
  | "uncited"
  | "model_declined"
  | "no_relevant_context"
  | "error";

export interface DoneEvent {
  type: "done";
  trace_id: string;
  outcome: Outcome;
  cited: number[];
  invalid_citations: number[];
  model: string | null;
  usage: { input_tokens: number | null; output_tokens: number | null };
  timings_ms: Record<string, number | null>;
}

export type ChatEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "delta"; text: string }
  | DoneEvent
  | { type: "error"; message: string; trace_id?: string };

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  done?: DoneEvent;
  error?: string;
  pending?: boolean;
}
