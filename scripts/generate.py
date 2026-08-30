# Regenerate README.md from SimplifyJobs

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

UPSTREAM_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "Summer2027-Internships/dev/.github/scripts/listings.json"
)

# ----------------------------- your filters -----------------------------
TERMS = {"Summer 2027"}          # only show listings tagged with these terms
CATEGORIES = {                   
    "Software",                  
    "AI/ML/Data",                # available categories: Software, AI/ML/Data, Quant, Hardware, Product
    "Quant",
}
MAX_AGE_DAYS = None             

# section order + display for the nav and per-category tables
CATEGORY_META = {
    "Software": ("💻", "Software Engineering", "software"),
    "AI/ML/Data": ("🤖", "Data Science, AI & ML", "ai-ml-data"),
    "Quant": ("📈", "Quantitative Finance", "quant"),
}

# per-flag badges: (unverified, verified)
# unverified = auto-published from suggested_annotations.yaml
# verified   = confirmed: true in annotations.yaml
BADGES = {
    "defense": ("\U0001F534", "\u2620\uFE0F", "\u26AA"),  # 🔴 / ☠️ / ⚪
    "ice": ("\U0001F535", "\U0001F940", "\u26AA"),        # 🔵 / 🥀 / ⚪
}

FIRE = "\U0001F525"  # 🔥 FAANG from Simplify FAANG_PLUS list

FIRE_COMPANIES = {
    "airbnb", "adobe", "amazon", "amd", "anthropic", "apple", "asana",
    "atlassian", "bytedance", "cloudflare", "coinbase", "crowdstrike",
    "databricks", "datadog", "doordash", "dropbox", "duolingo", "figma",
    "google", "ibm", "instacart", "intel", "linkedin", "lyft", "meta",
    "microsoft", "netflix", "notion", "nvidia", "openai", "oracle",
    "palantir", "paypal", "perplexity", "pinterest", "ramp", "reddit",
    "rippling", "robinhood", "roblox", "salesforce", "samsara",
    "servicenow", "shopify", "slack", "snap", "snapchat", "spacex",
    "splunk", "snowflake", "stripe", "square", "tesla", "tinder",
    "tiktok", "uber", "visa", "waymo", "x",
}

LEGAL_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|llp|ltd|limited|corp|corporation|co|company|"
    r"plc|gmbh|holdings|group)\b\.?", re.IGNORECASE
)


def normalize(name: str) -> str:
    """Normalize a company name for matching: lowercase, strip legal
    suffixes and punctuation, collapse whitespace."""
    name = name.lower()
    name = LEGAL_SUFFIXES.sub("", name)
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def load_listings(local_path: str | None) -> list[dict]:
    if local_path:
        raw = Path(local_path).read_text()
    else:
        with urllib.request.urlopen(UPSTREAM_URL, timeout=60) as resp:
            raw = resp.read().decode()
    listings = json.loads(raw)
    if not isinstance(listings, list) or not listings:
        sys.exit("Upstream listings file was empty or malformed; aborting "
                 "so the last good README is preserved.")
    return listings


def load_annotations() -> dict[str, dict]:
    # suggested_annotations.yaml is auto-published (unverified badges);
    # annotations.yaml is loaded second so hand-edits always win per flag
    merged: dict[str, dict] = {}
    for fname in ("suggested_annotations.yaml", "annotations.yaml"):
        path = ROOT / fname
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text()) or {}
        for company, meta in data.items():
            entry = merged.setdefault(normalize(company), {"flags": {}})
            entry["flags"].update((meta or {}).get("flags") or {})
    return merged


def keep(listing: dict) -> bool:
    if not listing.get("active") or not listing.get("is_visible", True):
        return False
    if TERMS and not TERMS.intersection(listing.get("terms") or []):
        return False
    if CATEGORIES and listing.get("category") not in CATEGORIES:
        return False
    if MAX_AGE_DAYS is not None:
        age = (dt.datetime.now(dt.timezone.utc).timestamp()
               - listing.get("date_posted", 0)) / 86400
        if age > MAX_AGE_DAYS:
            return False
    return True


def age_str(posted: int) -> str:
    days = int((dt.datetime.now(dt.timezone.utc).timestamp() - posted) / 86400)
    if days <= 0:
        return "0d"
    if days < 31:
        return f"{days}d"
    return f"{days // 30}mo"

def emoji_for(annotation: dict) -> str:
    # one badge per flag: unverified / verified / cleared
    out = []
    for fname, f in (annotation.get("flags") or {}).items():
        pair = BADGES.get(fname)
        if not pair:
            continue
        f = f if isinstance(f, dict) else {}
        if f.get("cleared"):
            out.append(pair[2])
        elif f.get("confirmed"):
            out.append(pair[1])
        else:
            out.append(pair[0])
    return " ".join(out)

def md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render(listings: list[dict], annotations: dict[str, dict]) -> str:
    by_cat: dict[str, list[tuple]] = {c: [] for c in CATEGORY_META}
    flagged: dict[str, dict] = {}
    total = 0

    for l in sorted(listings, key=lambda x: x.get("date_posted", 0),
                    reverse=True):
        if not keep(l):
            continue
        company = l["company_name"]
        ann = annotations.get(normalize(company), {})
        badge = emoji_for(ann)
        if normalize(company) in FIRE_COMPANIES:
            badge = (badge + " " + FIRE).strip()
        if ann and emoji_for(ann):
            flagged.setdefault(company, ann)
        name_cell = f"{badge} **{md_escape(company)}**" if badge \
            else f"**{md_escape(company)}**"
        title = md_escape(l["title"])
        # one location per line; >3 locations collapse into a dropdown
        loc_list = [md_escape(x) for x in (l.get("locations") or ["—"])]
        if len(loc_list) > 3:
            locs = (f"<details><summary><strong>{len(loc_list)} locations"
                    f"</strong></summary>" + "<br>".join(loc_list)
                    + "</details>")
        else:
            locs = "<br>".join(loc_list)
        by_cat.setdefault(l.get("category"), []).append(
            (name_cell, title, locs, l["url"], age_str(l.get("date_posted", 0)))
        )
        total += 1


    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    nav = " · ".join(
        f"[{label}](#{anchor})"
        for cat, (emoji, label, anchor) in CATEGORY_META.items()
        if by_cat.get(cat)
    )

    out = [
        '<a id="top"></a>',
        "",
        "# Summer 2027 Tech Internships",
        "",
        "[SimplifyJobs Summer 2027 Internships]"
        "(https://github.com/SimplifyJobs/Summer2027-Internships) "
        "with flags for large defense contracts and weapons manufacturers. ",
        "",
        "Contract amounts are pulled from [usaspending.gov](https://usaspending.gov/). "
        "Details for each company can be found in [Annotations](#annotations).",
        "",
        f"- {BADGES['defense'][0]} = Any company with DoD contracts totalling above $50M (2021-2026)",
        "",
        f"- {BADGES['ice'][0]} = Any company with ICE contracts totalling above $1M (2021-2026) (not including CBP)",
        "",
        f"- {BADGES['defense'][1]} = Human-verified weapons manufacturer / military surveillance tech",
        "",
        f"- {BADGES['ice'][1]} = Human-verified companies building for ICE",
        "",
        f"- {BADGES['defense'][2]} = Human-cleared (working for the DoD, but not weapons/surveillance)",
        "",
        f"- {FIRE} = FAANG+",
        "",
        "This is intended as a starting point for research. Since the main flag is based on raw DoD contract amounts, there may be some variation. ",
        "",
        f"Last updated: {now} · {total} active listings",
        "",
        f"Browse: {nav}",
        "",
    ]

    for cat, (emoji, label, anchor) in CATEGORY_META.items():
        rows = by_cat.get(cat)
        if not rows:
            continue
        out += [
            f'<a id="{anchor}"></a>',
            "",
            f"## {label}",
            "",
            "[\u2191 Back to top](#top)",
            "",
            "<details open>",
            f"<summary>Show/Hide {len(rows)} listings</summary>",
            "",  # blank line required so the markdown table renders inside
            "| Company | Role | Location | Application | Age |",
            "| --- | --- | --- | --- | --- |",
            *(f"| {name} | {title} | {locs} "
              f"| [Apply]({url}) | {age} |"
              for name, title, locs, url, age in rows),
            "",
            "</details>",
            "",
        ]

    def note_line(c):
        parts = []
        for fname, f in (flagged[c].get("flags") or {}).items():
            f = f if isinstance(f, dict) else {}
            detail = f.get("detail", "") or fname
            src = f.get("source", "")
            parts.append(detail + (f" — source: {src}" if src else ""))
        return f"- {emoji_for(flagged[c])} **{c}**: " + "; ".join(parts)

    def note_rank(c):
        # 0 = verified defense (☠️), 1 = verified ice (🥀),
        # 2 = unverified circles, 3 = fully cleared (⚪)
        flags = {k: (f if isinstance(f, dict) else {})
                 for k, f in (flagged[c].get("flags") or {}).items()}
        live = {k: f for k, f in flags.items() if not f.get("cleared")}
        if not live:
            return 3
        if flags.get("defense", {}).get("confirmed"):
            return 0
        if flags.get("ice", {}).get("confirmed"):
            return 1
        return 2

    notes = [note_line(c)
             for c in sorted(flagged, key=lambda c: (note_rank(c), c.lower()))]
    
    out += [
        "## Annotations",
        "",
        "Details for each company are listed below. The program sums the top 10 largest contracts from the past 5 years, so some companies may have much more in DoD contracts than represented here.",
        "",
        "<details open>",
        "<summary>Show/Hide notes</summary>",
        "",  # blank line required so the markdown renders inside
        *(notes or ["_No annotated companies in the current listings._"]),
        "",
        "</details>",
        "",
        "Listing data from [SimplifyJobs/Summer2027-Internships]"
        "(https://github.com/SimplifyJobs/Summer2027-Internships) "
        "(CC BY-NC 4.0).",
        "",
    ]

    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="path to a local listings.json")
    ap.add_argument("--out", default=str(ROOT / "README.md"))
    args = ap.parse_args()

    listings = load_listings(args.local)
    annotations = load_annotations()
    Path(args.out).write_text(render(listings, annotations))
    print(f"Wrote {args.out} ({len(listings)} listings fetched)")


if __name__ == "__main__":
    main()
