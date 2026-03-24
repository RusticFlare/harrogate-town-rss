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

    try:
        entries = data["children"][0]["standings"]["entries"]
    except (KeyError, IndexError):
        return None

    rows = []
    for entry in entries:
        team  = entry.get("team", {}).get("displayName", "?")
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

    try:
        rows.sort(key=lambda r: int(r["pos"]))
    except (ValueError, TypeError):
        pass

    return rows


def format_standings_table(rows):
    if not rows:
        return ""

    html  = "<table>\n"
    html += "  <thead>\n"
    html += "    <tr>"
    html += "<th>Pos</th>"
    html += "<th>Team</th>"
    html += "<th>P</th>"
    html += "<th>W</th>"
    html += "<th>D</th>"
    html += "<th>L</th>"
    html += "<th>GD</th>"
    html += "<th>Pts</th>"
    html += "</tr>\n"
    html += "  </thead>\n"
    html += "  <tbody>\n"

    for r in rows:
        is_harrogate = TEAM_NAME in r["team"]
        style = " style=\"font-weight: bold; background-color: #fff3cd;\"" if is_harrogate else ""
        html += "    <tr" + style + ">"
        html += "<td>" + str(r["pos"])    + "</td>"
        html += "<td>" + str(r["team"])   + "</td>"
        html += "<td>" + str(r["played"]) + "</td>"
        html += "<td>" + str(r["won"])    + "</td>"
        html += "<td>" + str(r["drawn"])  + "</td>"
        html += "<td>" + str(r["lost"])   + "</td>"
        html += "<td>" + str(r["gd"])     + "</td>"
        html += "<td>" + str(r["points"]) + "</td>"
        html += "</tr>\n"

    html += "  </tbody>\n"
    html += "</table>"

    return html


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
            "<p><strong>Full-time:</strong> " + home_name + " " + home_score +
            "-" + away_score + " " + away_name + "<br/>" +
            date.strftime("%A %d %B %Y") + "</p>"
        )

        is_league = any(
            kw in comp_name.lower() for kw in LEAGUE_COMP_KEYWORDS
        )
        if is_league and standings_table:
            description += "\n<h3>League Two Table</h3>\n" + standings_table

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
        ET.SubElement(item, "title").text = r["title"]
        ET.SubElement(item, "link").text  = r["link"]

        # Use CDATA so HTML in the description isn't entity-escaped
        desc = ET.SubElement(item, "description")
        desc.text = None
        desc.append(ET.Comment(" --><![CDATA[" + r["description"] + "]]><!-- "))

        ET.SubElement(item, "pubDate").text = (
            r["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        )
        ET.SubElement(item, "guid").text = r["guid"]

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")

    # ET.Comment wrapping produces slightly malformed CDATA, so fix it
    raw = ET.tostring(rss, encoding="unicode")
    raw = raw.replace(
        "<!-- --><![CDATA[", "<![CDATA["
    ).replace(
        "]]><!-- -->", "]]>"
    )

    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        f.write(raw)

    print("rss.xml written with " + str(len(results)) + " results.")


if __name__ == "__main__":
    standings_rows  = fetch_standings()
    standings_table = format_standings_table(standings_rows)
    results         = fetch_results(standings_table)
    if not results:
        print("WARNING: No results found.")
    else:
        generate_rss(results)
