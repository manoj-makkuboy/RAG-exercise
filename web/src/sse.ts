/**
 * Minimal Server-Sent Events parser for fetch() streams.
 * (EventSource can't POST a JSON body, so we read the response stream ourselves.)
 */
export class SSEParser<T> {
  private buffer = "";

  /** Feed a decoded text chunk; returns every complete event it finished. */
  push(chunk: string): T[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const events: T[] = [];
    let boundary: number;
    while ((boundary = this.buffer.indexOf("\n\n")) !== -1) {
      const raw = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const data = raw
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) events.push(JSON.parse(data) as T);
    }
    return events;
  }
}

export async function* readSSE<T>(response: Response): AsyncGenerator<T> {
  if (!response.body) throw new Error("Response has no body");
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SSEParser<T>();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    yield* parser.push(value);
  }
}
