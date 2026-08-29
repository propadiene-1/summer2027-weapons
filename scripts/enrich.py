# query for DoD contracts (USAspending.gov) --> write to suggested_annotations.yaml

import argparse
import difflib
import json
import time
import urllib.request
from pathlib import Path

import yaml

from generate import UPSTREAM_URL, load_listings, normalize

ROOT = Path(__file__).resolve().parent.parent
CHECKED = ROOT / "checked_companies.yaml"
SUGGESTED = ROOT / "suggested_annotations.yaml"

USASPENDING_API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DOD_THRESHOLD_USD = 1_000_000   # at least 1M with DoD
ICE_THRESHOLD_USD = 250_000     # at least 250k with ICE
FUZZY_REVIEW_BAND = 0.85        # match ratio below which we mark "needs review"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def dod_awards(company: str) -> list[dict]: #query USAspending for DoD contracts w/ this company
    payload = {
        "filters": {
            "recipient_search_text": [company],
            "agencies": [{"type": "awarding", "tier": "toptier",
                          "name": "Department of Defense"}],
            "award_type_codes": ["A", "B", "C", "D"],  # contracts
            "time_period": [{"start_date": "2021-01-01",
                             "end_date": "2026-12-31"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount"],
        "limit": 10,
        "page": 1,
    }
    req = urllib.request.Request(
        USASPENDING_API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp).get("results", [])

def ice_awards(company: str) -> list[dict]:
    payload = {
        "filters": {
            "recipient_search_text": [company],
            "agencies": [{"type": "awarding", "tier": "subtier",
                          "name": "U.S. Immigration and Customs Enforcement"}],
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [{"start_date": "2021-01-01",
                             "end_date": "2026-12-31"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount"],
        "limit": 10,
        "page": 1,
    }
    req = urllib.request.Request(
        USASPENDING_API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp).get("results", [])

def similarity(a: str, b: str) -> float: # name similarity; max of a character-levle ratio and token-containment score
    na, nb = normalize(a), normalize(b)
    char_ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return char_ratio
    containment = len(ta & tb) / min(len(ta), len(tb))
    return max(char_ratio, containment)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25,
                    help="max new companies to check this run")
    ap.add_argument("--local", help="path to a local listings.json")
    args = ap.parse_args()

    listings = load_listings(args.local)
    annotated = {normalize(k) for k in load_yaml(ROOT / "annotations.yaml")}
    checked = load_yaml(CHECKED)
    suggested = load_yaml(SUGGESTED)

    companies = {}  # normalized -> display name, active listings only
    for l in listings:
        if l.get("active"):
            companies.setdefault(normalize(l["company_name"]),
                                 l["company_name"])

    todo = [name for norm, name in sorted(companies.items())
            if norm not in annotated and norm not in checked][: args.limit]
    print(f"{len(todo)} new companies to check this run")

    for name in todo:
        norm = normalize(name)
        entry = {"checked": time.strftime("%Y-%m-%d")}
        try:
            awards = dod_awards(name)
        except Exception as exc:  # network hiccup: skip, retry next run
            print(f"  {name}: query failed ({exc}); will retry next run")
            continue

        # Keep only awards whose recipient actually resembles this company.
        flags = {}
        matches = []
        for a in awards:
            ratio = similarity(name, a.get("Recipient Name", ""))
            if ratio >= FUZZY_REVIEW_BAND:
                matches.append((ratio, a))
        
        total = sum(a.get("Award Amount") or 0 for _, a in matches)
        if matches and total >= DOD_THRESHOLD_USD:
            best_ratio = max(r for r, _ in matches)
            flags["defense"] = {
                "detail": f"DoD contracts ~${total:,.0f} "
                          f"(2021–2026, {len(matches)} awards)",
                "source": "usaspending",
                "confirmed": False,
                "match_confidence": round(best_ratio, 2),
                "needs_review": best_ratio < 0.95,
            }

        time.sleep(1)
        try:
            ice_results = ice_awards(name)
        except Exception as exc:
            print(f"  {name}: ICE query failed ({exc}); will retry next run")
            continue
        ice_matches = [(similarity(name, a.get("Recipient Name", "")), a)
                       for a in ice_results]
        ice_matches = [(r, a) for r, a in ice_matches
                       if r >= FUZZY_REVIEW_BAND]
        ice_total = sum(a.get("Award Amount") or 0 for _, a in ice_matches)
        if ice_matches and ice_total >= ICE_THRESHOLD_USD:
            best = max(r for r, _ in ice_matches)
            flags["ice"] = {
                "detail": f"ICE contracts ~${ice_total:,.0f} "
                          f"(2021–2026, {len(ice_matches)} awards)",
                "source": "usaspending",
                "confirmed": False,
                "match_confidence": round(best, 2),
                "needs_review": best < 0.95,
            }

        if flags:
            suggested[name] = {"flags": flags}
            print(f"  {name}: SUGGEST {', '.join(flags)}")
        else:
            print(f"  {name}: clean")

        checked[norm] = entry
        time.sleep(1)  # be polite to the API

    CHECKED.write_text(yaml.safe_dump(checked, sort_keys=True))
    SUGGESTED.write_text(yaml.safe_dump(suggested, sort_keys=True))
    print(f"\nWrote {SUGGESTED.name} — review it, then move accepted "
          f"entries into annotations.yaml")


if __name__ == "__main__":
    main()