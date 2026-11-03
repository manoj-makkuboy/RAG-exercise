import { describe, expect, it } from "vitest";
import { SSEParser } from "./sse";
import { linkCitations } from "./citations";

describe("SSEParser", () => {
  it("parses events split across chunks", () => {
    const p = new SSEParser<{ n: number }>();
    expect(p.push('data: {"n":')).toEqual([]);
    expect(p.push('1}\n\ndata: {"n":2}\n')).toEqual([{ n: 1 }]);
    expect(p.push("\n")).toEqual([{ n: 2 }]);
  });

  it("handles CRLF line endings and ignores comments", () => {
    const p = new SSEParser<{ ok: boolean }>();
    expect(p.push(': keep-alive\r\n\r\ndata: {"ok":true}\r\n\r\n')).toEqual([{ ok: true }]);
  });
});

describe("linkCitations", () => {
  it("turns [n] into citation links only for known sources", () => {
    expect(linkCitations("Yes [1][2], not [9].", 2)).toBe(
      "Yes [1](#cite-1)[2](#cite-2), not [9].",
    );
  });

  it("leaves markdown links and code alone", () => {
    expect(linkCitations("see [1](http://x) and `a[1]`", 3)).toBe("see [1](http://x) and `a[1]`");
  });
});
