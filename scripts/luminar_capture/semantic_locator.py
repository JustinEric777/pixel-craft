"""Parse Computer Use accessibility text without retaining stale element indexes."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ELEMENT = re.compile(r"^\s*(?P<index>\d+)\s+(?P<body>.+)$")
_IDENTIFIER = re.compile(r"(?:^|, )ID: (?P<identifier>[^,]+)")


@dataclass(frozen=True)
class AccessibilityElement:
    index: int
    body: str
    identifier: str | None

    @property
    def selected(self) -> bool:
        return "(selected)" in self.body or "Value: selected" in self.body


def parse_accessibility_tree(text: str) -> tuple[AccessibilityElement, ...]:
    elements: list[AccessibilityElement] = []
    for line in text.splitlines():
        match = _ELEMENT.match(line)
        if not match:
            continue
        body = match.group("body")
        identifier = _IDENTIFIER.search(body)
        elements.append(
            AccessibilityElement(
                index=int(match.group("index")),
                body=body,
                identifier=identifier.group("identifier") if identifier else None,
            )
        )
    return tuple(elements)


def find_by_identifier(text: str, identifier: str) -> AccessibilityElement:
    matches = [
        element
        for element in parse_accessibility_tree(text)
        if element.identifier == identifier
    ]
    if not matches:
        raise LookupError(f"accessibility element is missing: {identifier}")
    if len(matches) > 1:
        raise LookupError(f"accessibility element is ambiguous: {identifier}")
    return matches[0]


def find_by_locator(text: str, locator: str) -> AccessibilityElement:
    """Find an element by AX identifier or exact accessibility text token."""

    elements = parse_accessibility_tree(text)
    matches = [
        element
        for element in elements
        if element.identifier == locator or locator in element.body.split()
    ]
    if not matches:
        raise LookupError(f"accessibility element is missing: {locator}")
    if len(matches) > 1:
        raise LookupError(f"accessibility element is ambiguous: {locator}")
    return matches[0]
