import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ── Configuration ────────────────────────────────────────────────────────────

TEAM_ID   = "19262"
TEAM_NAME = "Harrogate Town"
LEAGUE_ID = "eng.4"  # ESPN league slug, e.g. eng.1 (Premier League),
                     # eng.2 (Championship), eng.3 (League One), eng.4 (League Two)

# Keywords used to identify league matches (for standings table)
# Should match part of the competition name returned by ESPN
LEAGUE_KEYWORDS = ["league two"]

# How many results to include in the feed
MAX_RESULTS = 20

# ── ESPN API endpoints (derived from config above) ───────────────────────────

SCHEDULE_URL  = "https://site.api.espn.com/apis/site/v2/sports/soccer/" + LEAGUE_ID + "/teams/" + TEAM_ID + "/schedule"
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/" + LEAGUE_ID + "/standings"

# ── Standings ─────────────────────────────────────────────────────────────────

def fetch_standings():
    try:
        data    = requests.get(STANDINGS_URL, timeout=10).json()
        entries = data["children"][0]["standings"]["entries"]
    except Exception:
        return []

    rows = []
    for entry in entries:
        team  = entry.get("team", {}).get("displayName", "?")
        stats = {s["name"]: s.get("displayValue", "?") for s in entry.get("stats", [])}
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

    rows.sort(key=lambda r: int(r["pos"]) if str(r["pos"]).isdigit() else 99)
    return rows


def standings_html(rows):
    if not rows:
        return ""

    def th(label):
        return "<th>" + label + "</th>"

    def td(value):
        return "<td>" + str(value) + "</td>"

    html  = "<table>\n<thead><tr>"
    html += th("Pos") + th("Team") + th("P") + th("W") + th("D") + th("L") + th("GD") + th("Pts")
    html += "</tr></thead>\n<tbody>\n"

    for r in rows:
        is_our_team = TEAM_NAME in r["team"]
        style       = " style=\"font-weight:bold; background-color:#fff3cd;\"" if is_our_team else ""
        html += "<tr" + style + ">"
        html += td(r["pos"]) + td(r["team"]) + td(r["played"]) + td(r["won"])
        html += td(r["drawn"]) + td(r["lost"]) + td(r["gd"]) + td(r["points"])
        html += "</tr>\n"

    html += "</tbody>\n</table>"
    return html


# ── Results ───────────────────────────────────────────────────────────────────

def fetch_results(table_html):
    try:
        data = requests.get(SCHEDULE_URL, timeout=10).json()
    except Exception:
        return []

    now     = datetime.now(timezone.utc)
    results = []

    for event in data.get("events", []):
        try:
            date = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except Exception:
            continue

        if date >= now:
            continue

        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        home        = next((c for c in competitors if c["homeAway"] == "home"), None)
        away        = next((c for c in competitors if c["homeAway"] == "away"), None)
        if not home or not away:
            continue

        home_name  = home["team"]["displayName"]
        away_name  = away["team"]["displayName"]
        home_score = home.get("score", {}).get("displayValue", "?")
        away_score = away.get("score", {}).get("displayValue", "?")
        comp_name  = (
            competition.get("type", {}).get("text", "")
            or event.get("league", {}).get("name", "")
            or "Unknown Competition"
        )
        event_id   = event.get("id", "")
        link       = "https://www.espn.co.uk/football/match/_/gameId/" + event_id
        is_home    = TEAM_NAME in home_name

        try:
            hs, as_   = int(home_score), int(away_score)
            our_score = hs if is_home else as_
            opp_score = as_ if is_home else hs
            outcome   = "W" if our_score > opp_score else ("D" if our_score == opp_score else "L")
            score_str = str(hs) + "-" + str(as_)
        except ValueError:
            outcome   = "?"
            score_str = home_score + "-" + away_score

        title = (
            "[" + outcome + "] " +
            home_name + " " + score_str + " " + away_name +
            " - " + comp_name +
            " - " + date.strftime("%d %b %Y")
        )

        content = (
            "<p><strong>Full-time:</strong> " +
            home_name + " " + home_score + "-" + away_score + " " + away_name +
            "<br/>" + date.strftime("%A %d %B %Y") + "</p>"
        )
        if any(kw in comp_name.lower() for kw in LEAGUE_KEYWORDS) and table_html:
            content += "\n<h3>League Table</h3>\n" + table_html

        results.append({
            "title":   title,
            "date":    date,
            "link":    link,
            "content": content,
        })

    results.sort(key=lambda r: r["date"], reverse=True)
    return results[:MAX_RESULTS]


# ── Atom feed generation ──────────────────────────────────────────────────────

ATOM = "http://www.w3.org/2005/Atom"

def atom_el(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, "{" + ATOM + "}" + tag, **attrs)
    if text is not None:
        el.text = text
    return el


def write_atom(results):
    ET.register_namespace("", ATOM)
    feed = ET.Element("{" + ATOM + "}feed")

    atom_el(feed, "title",    TEAM_NAME + " - Recent Results")
    atom_el(feed, "link",     href="https://www.espn.co.uk/football/club/_/id/" + TEAM_ID)
    atom_el(feed, "link",     rel="self", href="feed.xml")
    atom_el(feed, "id",       "https://www.espn.co.uk/football/club/_/id/" + TEAM_ID)
    atom_el(feed, "subtitle", "Latest match results for " + TEAM_NAME)
    atom_el(feed, "updated",  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    for i, r in enumerate(results):
        entry = atom_el(feed, "entry")
        atom_el(entry, "title",     r["title"])
        atom_el(entry, "link",      href=r["link"])
        atom_el(entry, "id",        r["link"])
        atom_el(entry, "published", r["date"].strftime("%Y-%m-%dT%H:%M:%SZ"))
        atom_el(entry, "updated",   r["date"].strftime("%Y-%m-%dT%H:%M:%SZ"))
        # Use a placeholder replaced with CDATA after serialisation
        atom_el(entry, "content",   "CONTENT_PLACEHOLDER_" + str(i), type="html")

    ET.indent(feed, space="  ")
    raw = ET.tostring(feed, encoding="unicode", xml_declaration=False)

    for i, r in enumerate(results):
        raw = raw.replace(
            "CONTENT_PLACEHOLDER_" + str(i),
            "<![CDATA[" + r["content"] + "]]>"
        )

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        f.write(raw)

    print("feed.xml written with " + str(len(results)) + " entries.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    table   = standings_html(fetch_standings())
    results = fetch_results(table)
    if results:
        write_atom(results)
    else:
        print("WARNING: No results found.")
