import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, streamChat, uploadDocument } from "./api";
import { MenuIcon, SendIcon, StopIcon } from "./components/Icons";
import { MessageView } from "./components/MessageView";
import { Sidebar, type Upload } from "./components/Sidebar";
import { SourcePanel } from "./components/SourcePanel";
import type { DocumentInfo, Message, Source } from "./types";

const SUGGESTIONS = [
  "Summarize the key points of these documents",
  "What are the most important dates or deadlines?",
  "List any numbers, limits or thresholds mentioned",
];

const uid = () => crypto.randomUUID();

export default function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const streaming = messages.some((m) => m.pending);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch((e: Error) => setLoadError(`Couldn't reach the API: ${e.message}`));
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleUpload = useCallback(async (files: File[]) => {
    await Promise.all(
      files.map(async (file) => {
        const id = uid();
        setUploads((u) => [...u, { id, name: file.name, status: "uploading" }]);
        try {
          const doc = await uploadDocument(file);
          setDocuments((docs) => [doc, ...docs.filter((d) => d.id !== doc.id)]);
          setUploads((u) => u.filter((x) => x.id !== id));
        } catch (e) {
          setUploads((u) =>
            u.map((x) => (x.id === id ? { ...x, status: "error", error: (e as Error).message } : x)),
          );
        }
      }),
    );
  }, []);

  const handleDelete = useCallback(async (doc: DocumentInfo) => {
    if (!window.confirm(`Delete "${doc.filename}"? Its chunks will be removed from search.`)) return;
    try {
      await deleteDocument(doc.id);
      setDocuments((docs) => docs.filter((d) => d.id !== doc.id));
      setSelected((s) => {
        const next = new Set(s);
        next.delete(doc.id);
        return next;
      });
    } catch (e) {
      window.alert((e as Error).message);
    }
  }, []);

  const updateMessage = (id: string, patch: (m: Message) => Message) =>
    setMessages((msgs) => msgs.map((m) => (m.id === id ? patch(m) : m)));

  async function ask(question: string) {
    const text = question.trim();
    if (!text || streaming) return;

    // Only completed exchanges go into history; failed answers would confuse the model.
    const history = messages
      .filter((m) => !m.error && m.content)
      .map((m) => ({ role: m.role, content: m.content }));
    const assistantId = uid();
    setMessages((msgs) => [
      ...msgs,
      { id: uid(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "", pending: true },
    ]);
    setInput("");

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      for await (const event of streamChat({
        question: text,
        history,
        documentIds: selected.size ? [...selected] : null,
        signal: controller.signal,
      })) {
        switch (event.type) {
          case "sources":
            updateMessage(assistantId, (m) => ({ ...m, sources: event.sources }));
            break;
          case "delta":
            updateMessage(assistantId, (m) => ({ ...m, content: m.content + event.text }));
            break;
          case "done":
            updateMessage(assistantId, (m) => ({ ...m, done: event }));
            break;
          case "error":
            updateMessage(assistantId, (m) => ({ ...m, error: event.message }));
            break;
        }
      }
    } catch (e) {
      const aborted = (e as Error).name === "AbortError";
      updateMessage(assistantId, (m) => ({
        ...m,
        error: aborted ? "Stopped." : (e as Error).message,
      }));
    } finally {
      updateMessage(assistantId, (m) => ({ ...m, pending: false }));
      abortRef.current = null;
    }
  }

  const toggleSelected = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const hasDocs = documents.length > 0;

  return (
    <div className={`app ${activeSource ? "with-source" : ""}`}>
      <Sidebar
        documents={documents}
        uploads={uploads}
        selected={selected}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onToggle={toggleSelected}
        onClearSelection={() => setSelected(new Set())}
        onUpload={handleUpload}
        onDelete={handleDelete}
        onDismissUpload={(id) => setUploads((u) => u.filter((x) => x.id !== id))}
      />
      {sidebarOpen && <div className="scrim" onClick={() => setSidebarOpen(false)} />}

      <main className="main">
        <header className="topbar mobile-only">
          <button className="icon-btn" onClick={() => setSidebarOpen(true)} aria-label="Open documents">
            <MenuIcon />
          </button>
          <span className="brand">DocChat</span>
        </header>

        <div className="thread" ref={threadRef}>
          {loadError && <div className="banner error center">{loadError}</div>}
          {messages.length === 0 ? (
            <div className="empty">
              <h1>Ask your documents anything</h1>
              <p>
                Answers come only from the files you upload, with numbered citations you can click
                to read the exact passage.
              </p>
              {hasDocs ? (
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => ask(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="hint">Start by adding a PDF, Markdown or text file on the left.</p>
              )}
            </div>
          ) : (
            messages.map((m) => (
              <MessageView
                key={m.id}
                message={m}
                activeSource={activeSource}
                onOpenSource={setActiveSource}
              />
            ))
          )}
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(input);
              }
            }}
            placeholder={hasDocs ? "Ask a question about your documents…" : "Add a document first…"}
            rows={1}
            maxLength={2000}
            aria-label="Question"
          />
          {streaming ? (
            <button type="button" className="send stop" onClick={() => abortRef.current?.abort()} aria-label="Stop">
              <StopIcon />
            </button>
          ) : (
            <button type="submit" className="send" disabled={!input.trim()} aria-label="Send">
              <SendIcon />
            </button>
          )}
        </form>
      </main>

      <SourcePanel source={activeSource} onClose={() => setActiveSource(null)} />
    </div>
  );
}
