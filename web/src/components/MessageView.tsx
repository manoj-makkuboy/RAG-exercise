import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkCitations } from "../citations";
import type { Message, Source } from "../types";
import { AlertIcon, SearchOffIcon } from "./Icons";

interface Props {
  message: Message;
  activeSource: Source | null;
  onOpenSource: (source: Source) => void;
}

export function MessageView({ message, activeSource, onOpenSource }: Props) {
  if (message.role === "user") {
    return <div className="msg user">{message.content}</div>;
  }

  const sources = message.sources ?? [];
  const cited = new Set(message.done?.cited ?? []);
  const outcome = message.done?.outcome;
  const notFound = outcome === "no_relevant_context" || outcome === "model_declined";

  return (
    <div className="msg assistant">
      {notFound && (
        <div className="banner muted">
          <SearchOffIcon /> Not found in your documents
        </div>
      )}
      {outcome === "uncited" && (
        <div className="banner warn">
          <AlertIcon /> This answer has no citations. Check it against the sources.
        </div>
      )}

      <div className="answer markdown">
        {message.pending && !message.content ? (
          <span className="thinking">
            {sources.length ? "Reading sources" : "Searching your documents"}
            <span className="dots" />
          </span>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => {
                const match = href?.match(/^#cite-(\d+)$/);
                if (!match) {
                  return (
                    <a href={href} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  );
                }
                const source = sources[Number(match[1]) - 1];
                return (
                  <button
                    className={`cite ${activeSource?.chunk_id === source?.chunk_id ? "active" : ""}`}
                    onClick={() => source && onOpenSource(source)}
                    title={source ? sourceLabel(source) : undefined}
                  >
                    {match[1]}
                  </button>
                );
              },
            }}
          >
            {linkCitations(message.content, sources.length)}
          </ReactMarkdown>
        )}
        {message.pending && message.content && <span className="caret" />}
      </div>

      {message.error && (
        <div className="banner error">
          <AlertIcon /> {message.error}
        </div>
      )}

      {sources.length > 0 && !notFound && (
        <div className="sources">
          <div className="sources-title">Sources</div>
          <div className="source-chips">
            {sources.map((s) => (
              <button
                key={s.chunk_id}
                className={`source-chip ${cited.has(s.ref) ? "cited" : ""} ${
                  activeSource?.chunk_id === s.chunk_id ? "active" : ""
                }`}
                onClick={() => onOpenSource(s)}
              >
                <span className="ref">{s.ref}</span>
                <span className="source-name">{sourceLabel(s)}</span>
                <RelevanceBar value={s.similarity} />
              </button>
            ))}
          </div>
        </div>
      )}

      {message.done && <Details done={message.done} />}
    </div>
  );
}

function RelevanceBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <span className="relevance" title={`Similarity ${value.toFixed(2)}`}>
      <span style={{ width: `${pct}%` }} />
    </span>
  );
}

function Details({ done }: { done: NonNullable<Message["done"]> }) {
  const [open, setOpen] = useState(false);
  const t = done.timings_ms;
  return (
    <div className="details">
      <button className="link-btn" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? "Hide details" : "Details"}
      </button>
      {open && (
        <dl>
          <dt>Outcome</dt>
          <dd>{done.outcome.replace(/_/g, " ")}</dd>
          {done.model && (
            <>
              <dt>Model</dt>
              <dd>{done.model}</dd>
            </>
          )}
          <dt>Latency</dt>
          <dd>
            retrieval {t.retrieval ?? "–"} ms
            {t.llm_first_token != null && ` · first token ${t.llm_first_token} ms`} · total {t.total} ms
          </dd>
          {done.usage.input_tokens != null && (
            <>
              <dt>Tokens</dt>
              <dd>
                {done.usage.input_tokens} in · {done.usage.output_tokens} out
              </dd>
            </>
          )}
          {done.invalid_citations.length > 0 && (
            <>
              <dt>Invalid citations</dt>
              <dd>{done.invalid_citations.map((n) => `[${n}]`).join(" ")}</dd>
            </>
          )}
          <dt>Trace</dt>
          <dd className="mono">{done.trace_id}</dd>
        </dl>
      )}
    </div>
  );
}

export function sourceLabel(s: Source): string {
  return s.page_number ? `${s.filename} · p.${s.page_number}` : s.filename;
}
