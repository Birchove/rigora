"""Deterministic heading-aware Markdown chunking."""

import re
from uuid import NAMESPACE_URL, uuid5

from research_mentor.domain.documents import DocumentChunk


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class MarkdownChunker:
    def __init__(self, *, max_chars: int, overlap_chars: int) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be between zero and max_chars")
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def split(self, document_id: str, markdown: str) -> list[DocumentChunk]:
        blocks = self._blocks(markdown)
        segments: list[tuple[list[str], str]] = []
        current_path: list[str] | None = None
        current_text = ""

        for heading_path, paragraph in blocks:
            separator = "\n\n" if current_text else ""
            if (
                current_path == heading_path
                and len(current_text + separator + paragraph) <= self._max_chars
            ):
                current_text += separator + paragraph
                continue
            if current_text:
                segments.append((current_path or [], current_text))
            current_path = heading_path
            current_text = paragraph

        if current_text:
            segments.append((current_path or [], current_text))

        normalized: list[tuple[list[str], str]] = []
        step = self._max_chars - self._overlap_chars
        for heading_path, text in segments:
            if len(text) <= self._max_chars:
                normalized.append((heading_path, text))
                continue
            start = 0
            while start < len(text):
                normalized.append((heading_path, text[start : start + self._max_chars]))
                if start + self._max_chars >= len(text):
                    break
                start += step

        return [
            DocumentChunk(
                chunk_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{document_id}:{ordinal}:{heading_path}:{text}",
                    )
                ),
                document_id=document_id,
                ordinal=ordinal,
                heading_path=heading_path,
                markdown=text,
            )
            for ordinal, (heading_path, text) in enumerate(normalized)
        ]

    @staticmethod
    def _blocks(markdown: str) -> list[tuple[list[str], str]]:
        heading_path: list[str] = []
        paragraph_lines: list[str] = []
        blocks: list[tuple[list[str], str]] = []

        def flush() -> None:
            if paragraph_lines:
                paragraph = "\n".join(paragraph_lines).strip()
                if paragraph:
                    blocks.append((heading_path.copy(), paragraph))
                paragraph_lines.clear()

        for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            match = HEADING.match(line)
            if match:
                flush()
                level = len(match.group(1))
                heading_path[:] = heading_path[: level - 1]
                heading_path.append(match.group(2))
            elif line.strip():
                paragraph_lines.append(line)
            else:
                flush()
        flush()
        return blocks
