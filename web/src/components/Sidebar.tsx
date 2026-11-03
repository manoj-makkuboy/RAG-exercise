import { useRef, useState } from "react";
import type { DocumentInfo } from "../types";
import { CloseIcon, FileIcon, TrashIcon, UploadIcon } from "./Icons";

export interface Upload {
  id: string;
  name: string;
  status: "uploading" | "error";
  error?: string;
}

interface Props {
  documents: DocumentInfo[];
  uploads: Upload[];
  selected: Set<string>;
  open: boolean;
  onClose: () => void;
  onToggle: (id: string) => void;
  onClearSelection: () => void;
  onUpload: (files: File[]) => void;
  onDelete: (doc: DocumentInfo) => void;
  onDismissUpload: (id: string) => void;
}

const ACCEPT = ".pdf,.txt,.md,.markdown";

export function Sidebar(props: Props) {
  const { documents, uploads, selected } = props;
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const scopeLabel =
    selected.size === 0
      ? `Searching all ${documents.length} document${documents.length === 1 ? "" : "s"}`
      : `Searching ${selected.size} of ${documents.length} selected`;

  return (
    <aside className={`sidebar ${props.open ? "open" : ""}`} aria-label="Documents">
      <div className="sidebar-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <FileIcon size={16} />
          </span>
          DocChat
        </div>
        <button className="icon-btn mobile-only" onClick={props.onClose} aria-label="Close panel">
          <CloseIcon />
        </button>
      </div>

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          props.onUpload(Array.from(e.dataTransfer.files));
        }}
      >
        <UploadIcon />
        <div>
          <strong>Add documents</strong>
          <span>PDF, Markdown or text · drop or click</span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => {
            props.onUpload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>

      <div className="doc-list-header">
        <span>{scopeLabel}</span>
        {selected.size > 0 && (
          <button className="link-btn" onClick={props.onClearSelection}>
            Use all
          </button>
        )}
      </div>

      <ul className="doc-list">
        {uploads.map((u) => (
          <li key={u.id} className={`doc upload ${u.status}`}>
            {u.status === "uploading" ? <span className="spinner" aria-label="Uploading" /> : <FileIcon />}
            <div className="doc-text">
              <span className="doc-name">{u.name}</span>
              <span className="doc-meta">
                {u.status === "uploading" ? "Reading & indexing…" : u.error}
              </span>
            </div>
            {u.status === "error" && (
              <button className="icon-btn" onClick={() => props.onDismissUpload(u.id)} aria-label="Dismiss">
                <CloseIcon size={14} />
              </button>
            )}
          </li>
        ))}
        {documents.map((doc) => (
          <li key={doc.id} className={`doc ${selected.has(doc.id) ? "selected" : ""}`}>
            <label className="doc-select">
              <input
                type="checkbox"
                checked={selected.has(doc.id)}
                onChange={() => props.onToggle(doc.id)}
                aria-label={`Limit questions to ${doc.filename}`}
              />
              <div className="doc-text">
                <span className="doc-name" title={doc.filename}>
                  {doc.filename}
                </span>
                <span className="doc-meta">
                  {doc.media_type === "application/pdf"
                    ? `${doc.page_count} page${doc.page_count === 1 ? "" : "s"} · `
                    : ""}
                  {doc.chunk_count} chunks
                </span>
              </div>
            </label>
            <button
              className="icon-btn danger"
              onClick={() => props.onDelete(doc)}
              aria-label={`Delete ${doc.filename}`}
            >
              <TrashIcon />
            </button>
          </li>
        ))}
        {documents.length === 0 && uploads.length === 0 && (
          <li className="doc-empty">No documents yet. Add one to start asking questions.</li>
        )}
      </ul>
    </aside>
  );
}
