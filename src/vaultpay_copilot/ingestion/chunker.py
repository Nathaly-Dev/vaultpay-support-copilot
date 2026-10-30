"""Lê uma política em Markdown e a divide em chunks (um por artigo)."""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->\n?", re.DOTALL)
_ARTICLE = re.compile(r"^## (Art\. .+)$", re.MULTILINE)
_REQUIRED_KEYS = ("slug", "title", "category", "effective_date")


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str


@dataclass(frozen=True)
class Policy:
    slug: str
    title: str
    category: str
    effective_date: date
    content: str
    content_hash: str
    chunks: list[Chunk]


def parse_policy(path: Path) -> Policy:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")

    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError(f"{path.name}: cabeçalho '---' não encontrado")

    meta = _parse_front_matter(match.group(1), path.name)
    body = _COMMENT.sub("", text[match.end() :]).strip()

    return Policy(
        slug=meta["slug"],
        title=meta["title"],
        category=meta["category"],
        effective_date=date.fromisoformat(meta["effective_date"]),
        content=body,
        content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        chunks=split_into_chunks(meta["title"], body),
    )


def split_into_chunks(title: str, body: str) -> list[Chunk]:
    articles = list(_ARTICLE.finditer(body))
    if not articles:
        raise ValueError(f"'{title}': nenhum artigo '## Art.' encontrado")

    chunks = []
    for i, art in enumerate(articles):
        end = articles[i + 1].start() if i + 1 < len(articles) else len(body)
        text = body[art.end() : end].strip()
        # O título vai junto para o artigo não perder o contexto da política.
        chunks.append(Chunk(index=i, content=f"{title}\n{art.group(1)}\n{text}"))
    return chunks


def _parse_front_matter(raw: str, filename: str) -> dict[str, str]:
    meta = {}
    for line in raw.split("\n"):
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()

    missing = [k for k in _REQUIRED_KEYS if not meta.get(k)]
    if missing:
        raise ValueError(f"{filename}: campos ausentes no cabeçalho: {missing}")
    return meta
