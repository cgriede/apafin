"""Search card. The form, the test setup, and the API share this shape."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

MUST_HAVE = ("kitchen", "towels", "wifi", "bathroom")
CONFIDENCE_MIN = 0.95


@dataclass
class SearchConfig:
    loaded_apartment_urls: list[str] = field(default_factory=list)
    working_places: list[str] = field(default_factory=lambda: ["Detligen", "Frieswil"])
    men: int = 3
    women: int = 2
    budget_chf: int = 1000
    check_in: date = field(default_factory=date.today)
    check_out: date = field(default_factory=date.today)
    must_have: list[str] = field(default_factory=lambda: list(MUST_HAVE))
    max_ride_min: int = 30
    include_pfadiheim: bool = False

    @property
    def team_label(self) -> str:
        return f"{self.men}M, {self.women}F"

    def to_json(self) -> dict:
        raw = asdict(self)
        raw["check_in"] = self.check_in.isoformat()
        raw["check_out"] = self.check_out.isoformat()
        raw["team"] = self.team_label
        return raw


def next_stay(today: date) -> tuple[date, date]:
    """Next Monday afternoon through Friday morning. Monday itself rolls a week."""
    days = (7 - today.weekday()) % 7
    if days == 0:
        days = 7
    check_in = today + timedelta(days=days)
    return check_in, check_in + timedelta(days=4)


def default_config(today: date | None = None) -> SearchConfig:
    check_in, check_out = next_stay(today or date.today())
    cfg = SearchConfig()
    cfg.check_in = check_in
    cfg.check_out = check_out
    return cfg


def parse_places(text: str) -> list[str]:
    return [part.strip() for part in text.split("+") if part.strip()]


def parse_team(text: str) -> tuple[int, int]:
    men = re.search(r"(\d+)\s*M", text, re.I)
    women = re.search(r"(\d+)\s*F", text, re.I)
    if not men or not women:
        raise ValueError("team must look like 3M, 2F")
    return int(men.group(1)), int(women.group(1))


def apply_chat(cfg: SearchConfig, text: str) -> SearchConfig:
    budget = re.search(r"budget\s+(\d+)", text, re.I)
    if budget:
        cfg.budget_chf = int(budget.group(1))
    if re.search(r"pfadi", text, re.I):
        cfg.include_pfadiheim = True
    team = re.search(r"(\d+\s*M\s*,\s*\d+\s*F)", text, re.I)
    if team:
        cfg.men, cfg.women = parse_team(team.group(1))
    return cfg


def config_from_body(body: dict, today: date | None = None) -> SearchConfig:
    cfg = default_config(today)
    if "working_place" in body:
        places = parse_places(str(body["working_place"]))
        if not places:
            raise ValueError("working place is empty")
        cfg.working_places = places
    if "team" in body:
        cfg.men, cfg.women = parse_team(str(body["team"]))
    if "budget_chf" in body:
        cfg.budget_chf = int(body["budget_chf"])
    if "max_ride_min" in body:
        cfg.max_ride_min = int(body["max_ride_min"])
    if "must_have" in body:
        cfg.must_have = [str(item).strip().lower() for item in body["must_have"] if str(item).strip()]
    if "loaded_apartment_urls" in body:
        urls = body["loaded_apartment_urls"] or []
        cfg.loaded_apartment_urls = [str(url).strip() for url in urls if str(url).strip()]
    if "include_pfadiheim" in body:
        cfg.include_pfadiheim = bool(body["include_pfadiheim"])
    if "check_in" in body and body["check_in"]:
        cfg.check_in = date.fromisoformat(str(body["check_in"]))
    if "check_out" in body and body["check_out"]:
        cfg.check_out = date.fromisoformat(str(body["check_out"]))
    note = str(body.get("chat") or "").strip()
    if note:
        apply_chat(cfg, note)
    if cfg.budget_chf < 0 or cfg.max_ride_min < 1:
        raise ValueError("budget and ride must be positive")
    if cfg.men < 0 or cfg.women < 0 or cfg.men + cfg.women < 1:
        raise ValueError("team is empty")
    return cfg
