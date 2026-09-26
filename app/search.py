"""Collect listings, then rank them. Portals are jev-ra sessions, one profile each."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from app.config import SearchConfig
from app.jev import evaluate
from app.rank import Listing, rank

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "detligen.json"

PORTALS = (
    ("booking", "https://www.booking.com/"),
    ("airbnb", "https://www.airbnb.com/"),
    ("fewo", "https://www.fewo.ch/"),
    ("pfadiheim", "https://www.pfadiheim.ch/"),
)


def portal_list(cfg: SearchConfig) -> tuple[tuple[str, str], ...]:
    names = {"booking", "airbnb", "fewo"}
    if cfg.include_pfadiheim:
        names.add("pfadiheim")
    return tuple(item for item in PORTALS if item[0] in names)


def jev_ra_cmd(source: str, url: str, cfg: SearchConfig, profile: str) -> list[str]:
    places = " and ".join(cfg.working_places)
    goal = (
        f"Search a whole holiday apartment for {cfg.team_label} near {places}. "
        f"Check-in {cfg.check_in.isoformat()} afternoon, check-out {cfg.check_out.isoformat()} morning. "
        f"Total at or under {cfg.budget_chf} CHF. Must have {', '.join(cfg.must_have)}. "
        "Open one listing page that shows price, beds, bedrooms, and the address."
    )
    return [
        "uvx",
        "jev-ra",
        "run",
        url,
        goal,
        "--value",
        f"place={cfg.working_places[0]}",
        "--value",
        f"check_in={cfg.check_in.isoformat()}",
        "--value",
        f"check_out={cfg.check_out.isoformat()}",
        "--value",
        f"guests={cfg.men + cfg.women}",
        "--max-steps",
        "8",
        "--profile",
        profile,
        "--json",
    ]


def playwright_chrome(home: Path | None = None) -> str | None:
    """Playwright's Chromium, the browser mini-proj runs already have."""
    root = Path(home or Path.home()) / ".cache" / "ms-playwright"
    if not root.is_dir():
        return None
    found = sorted(path for path in root.glob("chromium-*/chrome-linux64/chrome") if path.is_file())
    return str(found[-1]) if found else None


def browser_env() -> dict[str, str]:
    env = os.environ.copy()
    if env.get("JEV_RA_CHROME"):
        return env
    chrome = playwright_chrome()
    if chrome:
        env["JEV_RA_CHROME"] = chrome
    return env


def listing_from_json(raw: dict) -> Listing:
    return Listing(
        name=str(raw["name"]),
        place=str(raw.get("place") or ""),
        source=str(raw.get("source") or ""),
        url=str(raw.get("url") or ""),
        price_chf=int(raw["price_chf"]),
        drive_min={str(key): int(value) for key, value in raw.get("drive_min", {}).items()},
        bedrooms=None if raw.get("bedrooms") is None else int(raw["bedrooms"]),
        beds=None if raw.get("beds") is None else int(raw["beds"]),
        amenities=[str(item).lower() for item in raw.get("amenities") or []],
        stay_ok=bool(raw.get("stay_ok", True)),
        page_text=str(raw.get("page_text") or ""),
    )


def load_sample() -> list[Listing]:
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return [listing_from_json(item) for item in payload["listings"]]


def apply_jev(listings: list[Listing], cfg: SearchConfig, log: list[str]) -> None:
    """Ask Jev only when beds or bedrooms are missing and the page text is present."""
    for listing in listings:
        if listing.bedrooms is not None and listing.beds is not None:
            continue
        if not listing.page_text:
            continue
        fit = evaluate(cfg, listing.page_text)
        listing.jev_keep = fit.accepted
        log.append(
            f"Jev {listing.name}: {fit.choice} confidence={fit.confidence} accepted={fit.accepted}"
        )


def _run_jev(cmd: list[str], log: list[str], source: str) -> list[Listing]:
    env = browser_env()
    chrome = env.get("JEV_RA_CHROME") or ""
    if not chrome:
        log.append(f"{source}: no Chrome binary. Set JEV_RA_CHROME.")
        return []
    log.append(f"{source}: jev-ra profile {cmd[cmd.index('--profile') + 1]} chrome {chrome}")
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.append(f"{source}: {exc}")
        return []
    log.append(f"{source}: exit {done.returncode}")
    text = (done.stdout or "") + "\n" + (done.stderr or "")
    found = _listings_in_output(text, source)
    if not found:
        tail = " ".join(text.split())[:240]
        if tail:
            log.append(f"{source} output: {tail}")
    return found


def collect_live(cfg: SearchConfig) -> tuple[list[Listing], list[str]]:
    log: list[str] = []
    listings: list[Listing] = []
    if shutil.which("uvx") is None:
        log.append("uvx is not installed, so the portal browser session did not start.")
        return listings, log
    for source, url in portal_list(cfg):
        listings.extend(_run_jev(jev_ra_cmd(source, url, cfg, f"apafin-{source}"), log, source))
    for index, url in enumerate(cfg.loaded_apartment_urls, start=1):
        listings.extend(_run_jev(jev_ra_cmd("loaded", url, cfg, f"apafin-loaded-{index}"), log, "loaded"))
    return listings, log


def _listings_in_output(text: str, source: str) -> list[Listing]:
    found: list[Listing] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{") or "price_chf" not in line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows = raw["listings"] if isinstance(raw, dict) and "listings" in raw else [raw]
        for row in rows:
            if isinstance(row, dict) and "price_chf" in row and "name" in row:
                row.setdefault("source", source)
                found.append(listing_from_json(row))
    return found


def run_search(cfg: SearchConfig, *, mode: str = "live") -> dict:
    log: list[str] = []
    if mode == "sample":
        listings = load_sample()
        log.append("Sample listings for Detligen and Frieswil. No portal was opened.")
    else:
        listings, log = collect_live(cfg)
    if not cfg.include_pfadiheim:
        allowed = []
        for listing in listings:
            if listing.source == "pfadiheim":
                log.append(f"{listing.name}: Pfadiheim stays off unless the note asks for it.")
            else:
                allowed.append(listing)
        listings = allowed
    apply_jev(listings, cfg, log)
    cards, dropped = rank(listings, cfg)
    if not cards:
        log.append("No listing passed the rules.")
    return {
        "config": cfg.to_json(),
        "cards": [card.to_json(cfg) for card in cards],
        "dropped": dropped,
        "log": log,
    }
