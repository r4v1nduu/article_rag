import React from "react";

function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

export const highlightText = (text: string, query: string) => {
  if (!query) return text;

  const queryWords = query
    .split(/\s+/)
    .filter((word) => word.length > 0)
    .map(escapeRegExp);

  if (queryWords.length === 0) return text;

  const regex = new RegExp(`(${queryWords.join("|")})`, "gi");
  const parts = text.split(regex);
  const lowerCaseQueryWords = queryWords.map((w) =>
    w.replace(/\\/g, "").toLowerCase()
  );

  return (
    <>
      {parts.map((part, i) =>
        lowerCaseQueryWords.includes(part.toLowerCase()) ? (
          <mark key={i} className="bg-yellow-200 dark:bg-yellow-800">
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
};

export const getSnippets = (
  text: string,
  query: string,
  snippetLength = 200
) => {
  if (!query) {
    return [
      text.substring(0, snippetLength) +
        (text.length > snippetLength ? "..." : ""),
    ];
  }

  const queryWords = query
    .split(/\s+/)
    .filter((word) => word.length > 0)
    .map(escapeRegExp);

  if (queryWords.length === 0) {
    return [
      text.substring(0, snippetLength) +
        (text.length > snippetLength ? "..." : ""),
    ];
  }

  const snippets: string[] = [];
  const regex = new RegExp(queryWords.join("|"), "gi");
  let match;
  let lastSnippetEnd = -1;

  while ((match = regex.exec(text)) !== null) {
    if (match.index < lastSnippetEnd) {
      continue; // This match is inside the last snippet we created.
    }

    const context = snippetLength / 2;
    const start = Math.max(0, match.index - context);
    const end = Math.min(text.length, match.index + match[0].length + context);

    let snippet = text.substring(start, end);

    if (start > 0) {
      snippet = "..." + snippet;
    }
    if (end < text.length) {
      snippet = snippet + "...";
    }
    snippets.push(snippet);
    lastSnippetEnd = end;
  }

  if (snippets.length === 0) {
    return [
      text.substring(0, snippetLength) +
        (text.length > snippetLength ? "..." : ""),
    ];
  }

  return snippets;
};
