"""TypeSafe Jev choice, same call LRF uses. One keep-or-drop on page text."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from app.config import CONFIDENCE_MIN, SearchConfig

FIT_QUESTION = {
    "fit": {
        "type": "choice",
        "instructions": (
            "Judge this holiday-apartment page against the team and the must-haves in state. "
            "Use only the page text. Do not guess a missing bedroom count."
        ),
        "criteria": {
            "KEEP": (
                "The page states a kitchen, towels, wifi, and a bathroom, "
                "a private bedroom for each woman, leftover beds for the men, "
                "and Monday afternoon arrival with Friday morning departure."
            ),
            "DROP": (
                "A must-have is absent, a woman would share a room, "
                "there are not enough beds, or the stay window does not match."
            ),
            "UNSURE": "Bedrooms, beds, or a must-have are not stated on the page.",
        },
    }
}


@dataclass
class Fit:
    choice: str
    confidence: float | None
    accepted: bool


def state_for(cfg: SearchConfig, page_text: str) -> str:
    return (
        f"Team: {cfg.team_label}. Women each need their own bedroom. "
        f"Men share the remaining beds.\n"
        f"Must have: {', '.join(cfg.must_have)}.\n"
        f"Stay: check-in {cfg.check_in.isoformat()} afternoon, "
        f"check-out {cfg.check_out.isoformat()} morning.\n"
        f"Page:\n{page_text}"
    )


def parse_fit(body: dict) -> Fit:
    answer = (body.get("answers") or {}).get("fit") or {}
    choice = str(answer.get("choice") or "UNSURE")
    raw = answer.get("confidence")
    confidence = float(raw) if isinstance(raw, (int, float)) else None
    accepted = choice == "KEEP" and confidence is not None and confidence >= CONFIDENCE_MIN
    return Fit(choice=choice, confidence=confidence, accepted=accepted)


def evaluate(cfg: SearchConfig, page_text: str, *, api_key: str | None = None, timeout: float = 20) -> Fit:
    key = (api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")).strip()
    if not key:
        return Fit(choice="UNSURE", confidence=None, accepted=False)
    payload = json.dumps(
        {"model": "jev-latest", "state": state_for(cfg, page_text), "questions": FIT_QUESTION}
    ).encode()
    request = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode())
    return parse_fit(body)
