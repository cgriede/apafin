import unittest
from datetime import date

from app.config import apply_chat, config_from_body, default_config, next_stay
from app.jev import parse_fit
from app.rank import Listing, drop_reason, rank
from app.search import jev_ra_cmd, playwright_chrome, portal_list, run_search


TODAY = date(2026, 9, 26)


def listing(**kwargs) -> Listing:
    base = dict(
        name="Haus",
        place="Radelfingen",
        source="fewo",
        url="https://example.test/haus",
        price_chf=840,
        drive_min={"Detligen": 12, "Frieswil": 14},
        bedrooms=3,
        beds=6,
        amenities=["kitchen", "towels", "wifi", "bathroom"],
        stay_ok=True,
    )
    base.update(kwargs)
    return Listing(**base)


class StayTests(unittest.TestCase):
    def test_saturday_rolls_to_next_monday_friday(self):
        check_in, check_out = next_stay(TODAY)
        self.assertEqual(check_in, date(2026, 9, 28))
        self.assertEqual(check_out, date(2026, 10, 2))
        self.assertEqual(check_in.weekday(), 0)
        self.assertEqual(check_out.weekday(), 4)

    def test_default_card_matches_the_test_setup(self):
        cfg = default_config(TODAY)
        self.assertEqual(cfg.working_places, ["Detligen", "Frieswil"])
        self.assertEqual(cfg.team_label, "3M, 2F")
        self.assertEqual(cfg.budget_chf, 1000)
        self.assertEqual(cfg.must_have, ["kitchen", "towels", "wifi", "bathroom"])
        self.assertEqual(cfg.max_ride_min, 30)
        self.assertEqual(len(cfg.loaded_apartment_urls), 1)
        self.assertIn("769166993968066796", cfg.loaded_apartment_urls[0])


class RankTests(unittest.TestCase):
    def test_sample_returns_three_within_budget_and_ride(self):
        cfg = default_config(TODAY)
        result = run_search(cfg, mode="sample")
        names = [card["name"] for card in result["cards"]]
        self.assertEqual(names, ["Haus am Bach", "Wohnung Seedorf", "Stöckli Murzelen"])
        for card in result["cards"]:
            self.assertLessEqual(card["price_chf"], 1000)
            self.assertEqual(card["budget_chf"], 1000)
            self.assertEqual(card["left_chf"], 1000 - card["price_chf"])
            self.assertIn("Detligen", card["drive_min"])
            self.assertIn("Frieswil", card["drive_min"])
        dropped = {row["name"] for row in result["dropped"]}
        self.assertIn("Studio ohne Zimmer", dropped)
        self.assertIn("Weit weg", dropped)
        self.assertIn("Teuer", dropped)
        self.assertTrue(any("Pfadiheim" in line for line in result["log"]))

    def test_closer_beats_cheaper(self):
        cfg = default_config(TODAY)
        far_cheap = listing(name="Far", price_chf=500, drive_min={"Detligen": 25, "Frieswil": 29})
        near = listing(name="Near", price_chf=990, drive_min={"Detligen": 8, "Frieswil": 9})
        cards, _ = rank([far_cheap, near], cfg)
        self.assertEqual([card.listing.name for card in cards], ["Near", "Far"])

    def test_women_need_private_bedrooms(self):
        cfg = default_config(TODAY)
        short = listing(bedrooms=1, beds=6)
        self.assertIn("private bedrooms", drop_reason(short, cfg))

    def test_chat_raises_budget_and_pfadi(self):
        cfg = apply_chat(default_config(TODAY), "budget 1200 and also check Pfadiheime")
        self.assertEqual(cfg.budget_chf, 1200)
        self.assertTrue(cfg.include_pfadiheim)
        self.assertIn("pfadiheim", {name for name, _ in portal_list(cfg)})

    def test_form_body(self):
        cfg = config_from_body(
            {"working_place": "Detligen + Frieswil", "team": "3M, 2F", "budget_chf": 1000},
            today=TODAY,
        )
        self.assertEqual(cfg.men, 3)
        self.assertEqual(cfg.women, 2)


class JevTests(unittest.TestCase):
    def test_keep_needs_confidence(self):
        low = parse_fit({"answers": {"fit": {"choice": "KEEP", "confidence": 0.94}}})
        high = parse_fit({"answers": {"fit": {"choice": "KEEP", "confidence": 0.95}}})
        self.assertFalse(low.accepted)
        self.assertTrue(high.accepted)
        unsure = parse_fit({"answers": {"fit": {"choice": "UNSURE", "confidence": 0.99}}})
        self.assertFalse(unsure.accepted)

    def test_portal_command_passes_typed_values(self):
        cfg = default_config(TODAY)
        cmd = jev_ra_cmd("booking", "https://www.booking.com/", cfg, "apafin-booking")
        self.assertEqual(cmd[0], "uvx")
        self.assertIn("--profile", cmd)
        self.assertIn("apafin-booking", cmd)
        self.assertTrue(any(part.startswith("place=Detligen") for part in cmd))
        self.assertIn("--json", cmd)
        self.assertNotIn("pfadiheim", {name for name, _ in portal_list(cfg)})

    def test_playwright_chrome_is_the_newest_binary(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            older = home / ".cache/ms-playwright/chromium-1/chrome-linux64"
            newer = home / ".cache/ms-playwright/chromium-2/chrome-linux64"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            (older / "chrome").write_text("", encoding="utf-8")
            (newer / "chrome").write_text("", encoding="utf-8")
            self.assertEqual(playwright_chrome(home), str(newer / "chrome"))


if __name__ == "__main__":
    unittest.main()
