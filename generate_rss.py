import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TEAM_ID   = "19262"
TEAM_NAME = "Harrogate Town"
ESPN_API  = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
    "eng.4/teams/" + TEAM_ID + "/schedule"
)
STANDINGS_API = (
    "https://site.api.espn.com/apis/v2/sports/soccer/eng.4/standings"
)
LEAGUE_COMP_KEYWORDS = ["league two", "league 2"]


def fetch_standings():
    try:
        resp = requests.get(STANDINGS_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    rows = []
    for group in data.get("standings", []):
        for entry in group.get("entries", []):
            team = entry.get("team", {}).get("displayName", "?")
            stats = {s["name"]: s.get("displayValue", "?")
                     for s in entry.get("stats", [])}
            rows.append({
                "pos":    stats.get("rank", "?"),
                "team":   team,
                "played": stats.get("gamesPlayed", "?"),
                "won":    stats.get("wins", "?"),
                "drawn":  stats.get("ties", "?"),
                "lost":   stats.get("losses", "?"),
                "gd":     stats.get("pointDifferential", "?"),
                "points": stats.get("points", "?"),
            })

    # Sort by position
    try:
        rows.sort(key=lambda r: int(r["pos"]))
    except (ValueError, TypeError):
        pass

    return rows


def format_standings_table(rows):
    if not rows:
        return ""

    # Find Harrogate's position for context
    harrogate_pos = None
    for r in rows:
        if TEAM_NAME in r["team"]:
            harrogate_pos = r["pos"]
            break

    lines = []
    lines.append("League Two Table:")
    lines.append(
        "{:<4} {:<22} {:>2} {:>2} {:>2} {:>2} {:>4} {:>3}".format(
            "Pos", "Team", "P", "W", "D", "L", "GD", "Pts"
        )
    )
    lines.append("-" * 46)

    for r in rows:
        marker = ">" if TEAM_NAME in r["team"] else " "
        lines.append(
            "{}{:<3} {:<22} {:>2} {:>2} {:>2} {:>2} {:>4} {:>3}".format(
                marker,
                str(r["pos"]),
                r["team"][:22],
                str(r["played"]),
                str(r["won"]),
                str(r["drawn"]),
                str(r["lost"]),
                str(r["gd"]),
                str(r["points"]),
            )
        )

    return "\n".join(lines)


def fetch_results(standings_table):
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
        home_score = home.get("score", {}).get("displayValue", "?")
        away_score = away.get("score", {}).get("displayValue", "?")

        comp_name = (
            competition.get("type", {}).get("text", "")
            or event.get("league", {}).get("name", "Unknown Competition")
        )

        event_id = event.get("id", "")
        link     = "https://www.espn.co.uk/football/match/_/gameId/" + event_id
        is_home  = TEAM_NAME in home_name
        opp      = away_name if is_home else home_name

        try:
            hs, as_ = int(home_score), int(away_score)
            if is_home:
                outcome = "W" if hs > as_ else ("D" if hs == as_ else "L")
                score   = str(hs) + "-" + str(as_)
            else:
                outcome = "W" if as_ > hs else ("D" if hs == as_ else "L")
                score   = str(as_) + "-" + str(hs)
        except ValueError:
            outcome = "?"
            score   = home_score + "-" + away_score

        title = (
            "[" + outcome + "] " + TEAM_NAME + " " + score + " " + opp +
            " - " + comp_name +
            " - " + date.strftime("%d %b %Y")
        )

        description = (
            "Full-time: " + home_name + " " + home_score +
            "-" + away_score + " " + away_name + ". " +
            date.strftime("%A %d %B %Y") + "."
        )

        # Append standings table for league matches only
        is_league = any(
            kw in comp_name.lower() for kw in LEAGUE_COMP_KEYWORDS
        )
        if is_league and standings_table:
            description += "\n\n" + standings_table

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

    ET.SubElement(channel, "title").text = "Harrogate Town FC - Recent Results"
    ET.SubElement(channel, "link").text  = "https://www.harrogatetownafc.com/"
    ET.SubElement(channel, "description").text = (
        "Latest match results for Harrogate Town FC (EFL League Two)"
    )
    ET.SubElement(channel, "language").text      = "en-gb"
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

    print("rss.xml written with " + str(len(results)) + " results.")


if __name__ == "__main__":
    standings_rows  = fetch_standings()
    standings_table = format_standings_table(standings_rows)
    results         = fetch_results(standings_table)
    if not results:
        print("WARNING: No results found.")
    else:
        generate_rss(results)
