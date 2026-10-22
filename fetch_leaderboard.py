import csv
import json
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

COMPETITIONS = [
    ("Round 1 · Arabic Classification", "olo-academy-arabic-classification"),
    ("Round 2 · Reasoning-Intensive Retrieval", "olo-academy-reasoning-intensive-retrieval"),
]
OUT = Path("site")
OUT.mkdir(exist_ok=True)

def field(row, *names):
    lookup = {str(k).lower().replace("_", "").replace(" ", ""): str(v or "").strip()
              for k, v in row.items() if k}
    return next((lookup[n.lower().replace("_", "").replace(" ", "")]
                 for n in names if lookup.get(n.lower().replace("_", "").replace(" ", ""))), "")

def normalized(s):
    return " ".join(s.casefold().split())

# roster.csv: competition,team,member; repeat one row for each member.
# A team with no roster entry is provisionally treated as a single participant.
roster = defaultdict(list)
roster_path = Path("roster.csv")
if roster_path.exists():
    with roster_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            slug, team, member = ((row.get(x) or "").strip() for x in ("competition", "team", "member"))
            if slug and team and member and normalized(member) not in {normalized(m) for m in roster[(slug, normalized(team))]}:
                roster[(slug, normalized(team))].append(member)

def get_ranking(slug):
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run(["kaggle", "competitions", "leaderboard", slug,
                        "--download", "--path", temp, "--quiet"], check=True, capture_output=True, text=True)
        for archive in Path(temp).rglob("*.zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(temp)
        candidates = list(Path(temp).rglob("*.csv"))
        if not candidates:
            raise RuntimeError("No leaderboard CSV returned")
        # CSV export usually contains teamId, teamName, submissionDate, score; no rank.
        file = max(candidates, key=lambda x: x.stat().st_size)
        with file.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    teams = []
    seen = set()
    for row in rows:
        name = field(row, "teamName", "team", "team name")
        score = field(row, "score", "publicScore", "public score")
        explicit_rank = field(row, "rank", "publicRank")
        if not name or normalized(name) in ("baseline", "baseline.csv", "sample_submission.csv"):
            continue
        if explicit_rank and explicit_rank.isdigit() and int(explicit_rank) == 0:
            continue
        if not score or normalized(name) in seen:
            continue
        seen.add(normalized(name))
        teams.append({"team": name, "score": score,
                      "rank": int(explicit_rank) if explicit_rank.isdigit() else len(teams) + 1})
    # Round 1 final (private) positions visually verified on Kaggle on Oct 22, 2026.
    # Unverified positions 8+ continue to use Kaggle's downloadable ordering,
    # which may be public rather than private; they must not be called final.
    if slug == "olo-academy-arabic-classification":
        verified = {"ahmed8529393": (1, "0.98"), "aaf": (2, "0.98"),
                    "meganut": (3, "0.96"), "osama hurubi": (4, "0.94"),
                    "sf73": (5, "0.94"), "43uo": (6, "0.94"), "rynq-18": (7, "0.94")}
        for team in teams:
            key = normalized(team["team"])
            if key in verified:
                team["rank"], team["score"] = verified[key]
                team["verified_private"] = True
            else:
                team["verified_private"] = False
    teams.sort(key=lambda t: t["rank"])
    return teams

def rank_points(rank):
    return max(10, 110 - 10 * rank)

persons = {}
rounds = []
unmapped = []
for i, (title, slug) in enumerate(COMPETITIONS):
    try:
        teams = get_ranking(slug)
        status = "live" if teams else "no_submissions"
    except (subprocess.CalledProcessError, RuntimeError) as e:
        teams, status = [], "not_available"
        print(f"WARNING {slug}: {e}")
    rounds.append({"title": title, "slug": slug,
                   "url": f"https://www.kaggle.com/competitions/{slug}/leaderboard",
                   "status": status, "teams": len(teams)})
    for t in teams:
        # Do not score non-verified Round 1 positions as though they are final.
        if i == 0 and not t.get("verified_private"):
            continue
        members = roster.get((slug, normalized(t["team"])))
        provisional = not bool(members)
        if not members:
            members = [t["team"]]
            unmapped.append({"competition": slug, "team": t["team"]})
        share = round(rank_points(t["rank"]) / len(members), 2)
        for member in members:
            key = normalized(member)
            person = persons.setdefault(key, {"member": member, "total": 0.0, "rounds": [None] * len(COMPETITIONS)})
            person["total"] = round(person["total"] + share, 2)
            person["rounds"][i] = {"team": t["team"], "rank": t["rank"],
                                  "score": t["score"], "points": share,
                                  "team_size": len(members), "provisional": provisional}
ranking = sorted(persons.values(), key=lambda p: (-p["total"], p["member"].casefold()))
for rank, person in enumerate(ranking, 1):
    person["rank"] = rank

if not any(r["status"] == "live" for r in rounds):
    raise SystemExit("No accessible leaderboard results; previous site retained.")

payload = {
    "competition": "OLO Academy · Cumulative Individual Rankings",
    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "rounds": rounds, "people": ranking, "unmapped": unmapped,
    "note": "Round 1 private ranks 1–7 verified. Ranks 8+ await final private export. Missing rosters are provisional.",
    "scoring": "Team rank points: 1st 100, 2nd 90, 3rd 80, etc. (minimum 10). Each member gets team points ÷ registered team size.",
}
(OUT / "leaderboard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Published {len(ranking)} participants. Unmapped team rosters: {len(unmapped)}")
