/**
 * Rewrite "[n]" citation markers into markdown links "#cite-n" so the markdown renderer
 * hands them to our <a> override, which draws a clickable chip.
 * Skips inline code spans and existing markdown links, and ignores numbers that don't
 * match a supplied source (those are surfaced separately as invalid citations).
 */
export function linkCitations(text: string, sourceCount: number): string {
  return text
    .split(/(`[^`]*`)/g)
    .map((part) =>
      part.startsWith("`")
        ? part
        : part.replace(/\[(\d{1,3})\](?!\()/g, (match, n: string) => {
            const ref = Number(n);
            return ref >= 1 && ref <= sourceCount ? `[${ref}](#cite-${ref})` : match;
          }),
    )
    .join("");
}
