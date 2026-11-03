import type { Source } from "../types";
import { CloseIcon, FileIcon } from "./Icons";
import { sourceLabel } from "./MessageView";

interface Props {
  source: Source | null;
  onClose: () => void;
}

export function SourcePanel({ source, onClose }: Props) {
  return (
    <aside className={`source-panel ${source ? "open" : ""}`} aria-label="Source" aria-hidden={!source}>
      {source && (
        <>
          <div className="source-panel-header">
            <span className="ref big">{source.ref}</span>
            <div className="source-panel-title">
              <FileIcon />
              <span title={source.filename}>{sourceLabel(source)}</span>
            </div>
            <button className="icon-btn" onClick={onClose} aria-label="Close source">
              <CloseIcon />
            </button>
          </div>
          <div className="source-panel-meta">
            Similarity {source.similarity.toFixed(2)} · the exact passage the model was given
          </div>
          <blockquote className="source-text">{source.content}</blockquote>
        </>
      )}
    </aside>
  );
}
