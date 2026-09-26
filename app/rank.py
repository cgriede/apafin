"""Hard rules and the sort. Jev does not pick the order."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import SearchConfig


@dataclass
class Listing:
    name: str
    place: str
    source: str
    url: str
    price_chf: int
    drive_min: dict[str, int]
    bedrooms: int | None
    beds: int | None
    amenities: list[str]
    stay_ok: bool = True
    page_text: str = ""
    jev_keep: bool = False

    def amenity_set(self) -> set[str]:
        return {item.strip().lower() for item in self.amenities}


def rooms_cover(listing: Listing, men: int, women: int) -> bool:
    """Each woman takes one bedroom and one bed. Men use the beds that remain."""
    if listing.jev_keep:
        return True
    if listing.bedrooms is None or listing.beds is None:
        return False
    if listing.bedrooms < women:
        return False
    return listing.beds - women >= men


def drop_reason(listing: Listing, cfg: SearchConfig) -> str | None:
    if not listing.stay_ok:
        return "Stay is not Monday afternoon to Friday morning"
    if listing.price_chf > cfg.budget_chf:
        return f"{listing.price_chf} CHF is over the {cfg.budget_chf} CHF budget"
    for place in cfg.working_places:
        minutes = listing.drive_min.get(place)
        if minutes is None:
            return f"Drive time to {place} is missing"
        if minutes > cfg.max_ride_min:
            return f"{minutes} min to {place} is over {cfg.max_ride_min} min"
    missing = [item for item in cfg.must_have if item not in listing.amenity_set()]
    if missing:
        return "Missing " + ", ".join(missing)
    if not rooms_cover(listing, cfg.men, cfg.women):
        return (
            f"Needs {cfg.women} private bedrooms and {cfg.men} more beds, "
            f"listing has {listing.bedrooms} bedrooms and {listing.beds} beds"
        )
    return None


def longer_drive(listing: Listing, cfg: SearchConfig) -> int:
    return max(listing.drive_min[place] for place in cfg.working_places)


def why(listing: Listing, nxt: Listing | None, cfg: SearchConfig) -> str:
    minutes = longer_drive(listing, cfg)
    left = cfg.budget_chf - listing.price_chf
    budget = f"{listing.price_chf} CHF of {cfg.budget_chf} CHF, {left} CHF left"
    if nxt is None:
        return f"{minutes} min to the farther work place. {budget}."
    nxt_minutes = longer_drive(nxt, cfg)
    if minutes < nxt_minutes:
        return f"{minutes} min to the farther work place, next is {nxt_minutes} min. {budget}."
    return f"Same {minutes} min ride as the next, {listing.price_chf} CHF against {nxt.price_chf} CHF. {budget}."


def room_sentence(listing: Listing, cfg: SearchConfig) -> str:
    if listing.jev_keep and (listing.bedrooms is None or listing.beds is None):
        return f"Jev kept the page for {cfg.women} private rooms and {cfg.men} more beds."
    return (
        f"{listing.bedrooms} bedrooms, {listing.beds} beds. "
        f"{cfg.women} private rooms for the women, {cfg.men} beds left for the men."
    )


@dataclass
class Card:
    listing: Listing
    why: str
    room_sentence: str

    def to_json(self, cfg: SearchConfig) -> dict:
        listing = self.listing
        return {
            "name": listing.name,
            "place": listing.place,
            "source": listing.source,
            "url": listing.url,
            "price_chf": listing.price_chf,
            "budget_chf": cfg.budget_chf,
            "left_chf": cfg.budget_chf - listing.price_chf,
            "drive_min": {place: listing.drive_min.get(place) for place in cfg.working_places},
            "must_have": [item for item in cfg.must_have if item in listing.amenity_set()],
            "room_sentence": self.room_sentence,
            "why": self.why,
        }


def rank(listings: list[Listing], cfg: SearchConfig) -> tuple[list[Card], list[dict]]:
    kept: list[Listing] = []
    dropped: list[dict] = []
    for listing in listings:
        reason = drop_reason(listing, cfg)
        if reason:
            dropped.append({"name": listing.name, "source": listing.source, "reason": reason})
        else:
            kept.append(listing)
    kept.sort(key=lambda item: (longer_drive(item, cfg), item.price_chf, item.name))
    top = kept[:3]
    cards = [
        Card(
            listing=item,
            why=why(item, top[index + 1] if index + 1 < len(top) else None, cfg),
            room_sentence=room_sentence(item, cfg),
        )
        for index, item in enumerate(top)
    ]
    return cards, dropped
