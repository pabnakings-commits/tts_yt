"""Script cleanup and chunking so long YouTube scripts generate reliably."""
from __future__ import annotations

import re

MAX_CHUNK_CHARS = 900


def clean_script(text: str) -> str:
    """Normalize whitespace/newlines without mangling paragraph structure."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of spaces/tabs, but keep newlines.
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ blank lines down to a single paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def split_into_sentences(paragraph: str) -> list[str]:
    # Simple, dependency-free sentence splitter tuned for narration scripts.
    pieces = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    return [p for p in pieces if p]


def chunk_script(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split cleaned script text into speech-friendly chunks.

    Splits on paragraph boundaries first, then sentence boundaries, so no
    chunk ever cuts a sentence in half and chunks stay under `max_chars`.
    Order is always preserved.
    """
    cleaned = clean_script(text)
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        sentences = split_into_sentences(paragraph) or [paragraph]
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            if len(sentence) <= max_chars:
                current = sentence
            else:
                # A single sentence longer than max_chars: hard-split on
                # word boundaries so we never truncate mid-word.
                words = sentence.split(" ")
                piece = ""
                for word in words:
                    cand = f"{piece} {word}".strip() if piece else word
                    if len(cand) <= max_chars:
                        piece = cand
                    else:
                        if piece:
                            chunks.append(piece)
                        piece = word
                if piece:
                    current = piece
        if current:
            chunks.append(current)
            current = ""

    if current:
        chunks.append(current)

    return chunks
