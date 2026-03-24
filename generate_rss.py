import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TEAM_ID = "19262"
TEAM_NAME = "Harrogate Town"
ESPN_API = (
    f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.4"
    f"/teams/{TEAM_ID}/schedule"
)

def fetch_results():
    resp = requests.get(ESPN_API, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for event in data.get("events", []):
        status_name = (
            event.get("status", {})
                 .get("type", {})
                 .get("name", "")
        )
        if status_name != "STATUS_FINAL":
            continue

        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        home = next((c for c in competitors if c["homeAway"] == "home"), None)
        away = next((c for c in competitors if c["homeAway"] == "away"), None)
        if not home or not away:
            continue

        home_name  = home["team"]["displayName"]
        away_name  = away["team"]["displayName"]
        home_score = home.get("score", "?")
        away_score = away.get("score", "?")

        try:
            date = datetime.fromisoformat(
                event["date"].replace("Z", "+00:00")
            )
        except Exception:
            date = datetime.now(timezone.utc)

        event_id = event.get("id", "")
        link = f"https://www.espn.co.uk/football/match/_/gameId/{event_id}"

        # Work out which side Harrogate are and label home/away
        is_home = TEAM_NAME in home_name
        venue_label = "Home" if is_home else "Away"
        if is_home:
            opp = away_name
            score_display = f"{home_score}–{away_score}"
        else:
            opp = home_name
            score_display = f"{away_score}–{home_score}"

        # Win / Draw / Loss from Harrogate's perspective
        try:
            hs, as_ = int(home_score), int(away_score)
            if is_home:
                outcome = "Win" if hs > as_ else ("Draw" if hs == as_ else "Loss")
            else:
                outcome = "Win" if as_ > hs else ("Draw" if hs == as_ else "Loss")
        except ValueError:
            outcome = ""

        title = (
            f"{TEAM_NAME} {score_display} vs {opp} "
            f"({venue_label}, {outcome}) – {date.strftime('%d %b %Y')}"
        )
        description = (
            f"Full-time score: {home_name} {home_score}–{away_score} {away_name}. "
            f"Played on {date.strftime('%A %-d %B %Y')}."
        )

        results.append({
            "title": title,
            "date": date,
            "link": link,
            "description": description,
            "guid": link,
        })

    results.sort(key=lambda x: x["date"], reverse=True)
    return results[:20]


def generate_rss(results):
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Harrogate Town FC – Recent Results"
    ET.SubElement(channel, "link").text = "https://www.harrogatetownafc.com/"
    ET.SubElement(channel, "description").text = (
        "Latest match results for Harrogate Town FC (EFL League Two)"
    )
    ET.SubElement(channel, "language").text = "en-gb"
    ET.SubElement(channel, "lastBuildDate").text = (
        datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    )

    for r in results:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text       = r["title"]
        ET.SubElement(item, "link").text        = r["link"]
        ET.SubElement(item, "description").text = r["description"]
        ET.SubElement(item, "pubDate").text     = (
            r["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        )
        ET.SubElement(item, "guid").text        = r["guid"]

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")

    with open("rss.xml", "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)

    print(f"✅  rss.xml written with {len(results)} results.")


if __name__ == "__main__":
    results = fetch_results()
    generate_rss(results)
