import json, urllib.request

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

def query(company, agencies):
    payload = {
        "filters": {
            "recipient_search_text": [company],
            "agencies": agencies,
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [{"start_date": "2021-01-01",
                             "end_date": "2026-12-31"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount"],
        "limit": 10, "sort": "Award Amount", "order": "desc", "page": 1,
    }
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("results", [])

DOD = [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}]
ICE = [{"type": "awarding", "tier": "subtier",
        "name": "U.S. Immigration and Customs Enforcement"}]

for company in ["Lockheed Martin", "Anduril", "General Dynamics", "Boeing", "L3Harris", "BAE Systems"]:
    for label, ag in (("DoD", DOD), ("ICE", ICE)):
        results = query(company, ag)
        total = sum(a.get("Award Amount") or 0 for a in results)
        print(f"\n{company} — {label}: top {len(results)} awards, "
              f"sum ~${total:,.0f}")
        for a in results[:5]:
            print(f"   {a.get('Recipient Name')}  "
                  f"${a.get('Award Amount') or 0:,.0f}  ({a.get('Award ID')})")