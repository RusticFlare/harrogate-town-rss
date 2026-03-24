import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TEAM_ID   = "19262"
TEAM_NAME = "Harrogate Town"
ESPN_API  = (
    f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
    f"eng.4/teams/{TEAM_ID}/schedule"
)

def fetch_results():
    resp = requests.get(ESPN_API, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    now     = datetime.now(timezone.utc)
    results = []

    for event in data.get("events", []):
        try:
            date = datetime.fromisoformat(
                event["date"].replace("Z", "+00:00")
            )
        except Exception:
            continue

        # Only include matches that have already been played
        if date >= now:
            continue

        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        home = next((c for c in competitors if c["homeAway"] == "home"), None)
        away = next((c for c in competitors if c["homeAway"] == "away"), None)
        if not home or not away:
            continue

        home_name  = home["team"]["displayName"]
        away_name  = away["team"]["displayName"]

        # Score is a dict with a displayValue field
        home_score = home.get("score", {}).get("displayValue", "?")
        away_score = away.get("score", {}).get("displayValue", "?")

        event_id    = event.get("id", "")
        link        = f"https://www.espn.co.uk/football/match/_/gameId/{event_id}"
        is_home     = TEAM_NAME in home_name
        venue_label = "H" if is_home else "A"
        opp         = away_name if is_home else home_name

        try:
            hs, as_ = int(home_score), int(away_score)
            if is_home:
                outcome = "W" if hs > as_ else ("D" if hs == as_ else "L")
                score   = f"{hs}–{as_}"
            else:
                outcome = "W" if as_ > hs else ("D" if hs == as_ else "L")
                score   = f"{as_}–{hs}"
        except ValueError:
            outcome = "?"
            score   = f"{home_score}–{away_score}"

        title = (
            f"[{outcome}] {TEAM_NAME} {score} {opp} "
            f"({venue_label}) – {date.strftime('%d %b %Y')}"
        )
        description = (
            f"Full-time: {home_name} {home_score}–{away_score} {away_name}. "
            f"{date.strftime('%A %-d %B %Y')}."
        )

        results.append({
            "title":       title,
            "date":        date,
            "link":        link,
            "description": description,
            "guid":        link,
        })

    results.sort(key=lambda x: x["date"], reverse=True)
    return results[:20]


def generate_rss(results):
    rss     = ET.Element("rss")
    rss.set("version", "2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Harrogate Town FC – Recent Results"
    ET.SubElement(channel, "link").text  = "https://www.harrogatetownafc.com/"
    ET.SubElement(channel, "description").text = (
        "Latest match results for Harrogate Town FC (EFL League Tw
