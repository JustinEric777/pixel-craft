"""Small local WordPiece tokenizer for the bundled semantic-search model."""

from __future__ import annotations

import json
import re
from pathlib import Path


class WordPieceTokenizer:
    def __init__(self, path: Path, max_length: int = 16) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.vocab: dict[str, int] = payload["model"]["vocab"]
        self.max_length = max_length
        self.unk = self.vocab.get("[UNK]", 100)
        self.cls = self.vocab.get("[CLS]", 101)
        self.sep = self.vocab.get("[SEP]", 102)
        self.pad = self.vocab.get("[PAD]", 0)

    def encode(self, text: str) -> tuple[list[int], list[int]]:
        tokens = ["[CLS]"]
        for word in re.findall(r"[a-z0-9]+|[^\w\s]", text.lower()):
            start = 0
            pieces: list[str] = []
            while start < len(word):
                end = len(word)
                found: str | None = None
                while end > start:
                    candidate = word[start:end]
                    if start:
                        candidate = "##" + candidate
                    if candidate in self.vocab:
                        found = candidate
                        break
                    end -= 1
                if found is None:
                    pieces = ["[UNK]"]
                    break
                pieces.append(found)
                start = end
            tokens.extend(pieces)
        tokens.append("[SEP]")
        ids = [self.vocab.get(token, self.unk) for token in tokens[: self.max_length]]
        ids.extend([self.pad] * (self.max_length - len(ids)))
        mask = [1 if index < len(tokens[: self.max_length]) else 0 for index in range(self.max_length)]
        return ids, mask
