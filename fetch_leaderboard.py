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
    ("Round 3 · Echoes of Recitation", "echoes-of-recitation"),
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

def get_private_round3_ranking():
    # Use the frozen PRIVATE ranks, not a live/public Kaggle leaderboard.
    with Path("data/round3_private.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    teams = []
    for row in rows:
        rank = field(row, "Rank")
        score = field(row, "Score")
        members = [m.strip() for m in field(row, "TeamMemberUserNames").split(",") if m.strip()]
        if not rank.isdigit() or int(rank) < 1 or not score or not members:
            continue  # Ignore unranked benchmark entry.
        teams.append({"team": field(row, "TeamName"), "score": score,
                      "rank": int(rank), "members": members,
                      "verified_private": True})
    return sorted(teams, key=lambda t: t["rank"])

def get_ranking(slug):
    if slug == "echoes-of-recitation":
        return get_private_round3_ranking()
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
        members = [
            m.strip()
            for m in field(row, "TeamMemberUserNames").split(",")
            if m.strip()
        ]
        teams.append({
            "team": name,
            "score": score,
            "members": members,
            "rank": int(explicit_rank) if explicit_rank.isdigit() else len(teams) + 1
        })
    # Round 1 final (private) positions visually verified on Kaggle on Oct 22, 2026.
    # Unverified positions 8+ continue to use Kaggle's downloadable ordering,
    # which may be public rather than private; they must not be called final.
    if slug == "olo-academy-arabic-classification":
        verified = {"ahmed8529393": (1, "0.98"), "aaf": (2, "0.98"),
                    "meganut": (3, "0.96"), "osama hurubi": (4, "0.94"),
                    "sf73": (5, "0.94"), "43uo": (6, "0.94"), "rynq-18": (7, "0.94")}
        for team in teams:
            key = " ".join("".join(c for c in __import__("unicodedata").normalize("NFKD", team["team"].casefold()) if not __import__("unicodedata").combining(c)).split())
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
        status = ("final private" if slug == "echoes-of-recitation" and teams
                  else "live" if teams else "no_submissions")
    except (subprocess.CalledProcessError, RuntimeError) as e:
        teams, status = [], "not_available"
        print(f"WARNING {slug}: {e}")
    rounds.append({"title": title, "slug": slug,
                   "url": f"https://www.kaggle.com/competitions/{slug}/leaderboard",
                   "status": status, "teams": len(teams)})
    for t in teams:
        # Include all teams; unverified Round 1 ranks remain provisional.
        # Never treat an unknown-size team as one individual.
        # These counts were verified from the Round 1 final Kaggle screenshot.
        verified_sizes = {
            ("olo-academy-arabic-classification", "ahmed8529393"): 1,
            ("olo-academy-arabic-classification", "aaf"): 3,
            ("olo-academy-arabic-classification", "meganut"): 1,
            ("olo-academy-arabic-classification", "osama hurubi"): 1,
            ("olo-academy-arabic-classification", "sf73"): 2,
            ("olo-academy-arabic-classification", "43uo"): 1,
            ("olo-academy-arabic-classification", "rynq-18"): 1,
        }
        import unicodedata
        def clean_name(name):
            # Normalize decorated Kaggle names for matching (e.g. AAF diacritics).
            return " ".join("".join(c for c in unicodedata.normalize("NFKD", name.casefold())
                            if not unicodedata.combining(c)).split())
        key_team = clean_name(t["team"])
        # Resolve explicit roster, even where Kaggle display names have decorations.
        members = t.get("members") or roster.get((slug, normalized(t["team"]))) or roster.get((slug, key_team))
        if not members:
            for (rslug, rteam), rmem in roster.items():
                if rslug == slug and clean_name(rteam) == key_team:
                    members = rmem
                    break
        expected = verified_sizes.get((slug, key_team))
        if members and expected and len(members) != expected:
            raise ValueError(f"Roster count mismatch for {t['team']}: expected {expected}, got {len(members)}")
        if members:
            team_size = len(members)
            named_members = members
        elif expected == 1:
            team_size = 1
            named_members = [t["team"]]
        elif expected and expected > 1:
            team_size = expected
            named_members = [f"{t['team']} — member {n} (name needed)" for n in range(1, expected + 1)]
            unmapped.append({"competition": slug, "team": t["team"], "needed": expected})
        else:
            unmapped.append({"competition": slug, "team": t["team"], "needed": None})
            continue  # Unknown number of members: cannot allocate individual points fairly.
        share = round(rank_points(t["rank"]) / team_size, 2)
        for member in named_members:
            key = normalized(member)
            person = persons.setdefault(key, {"member": member, "total": 0.0, "rounds": [None] * len(COMPETITIONS)})
            person["total"] = round(person["total"] + share, 2)
            person["rounds"][i] = {"team": t["team"], "rank": t["rank"],
                                  "score": t["score"], "points": share,
                                  "team_size": team_size,
                                  "provisional": (not bool(members)) or (i == 0 and not t.get("verified_private"))}

ranking = sorted(persons.values(), key=lambda p: (-p["total"], p["member"].casefold()))
for rank, person in enumerate(ranking, 1):
    person["rank"] = rank

if not any(r["status"] == "live" for r in rounds):
    raise SystemExit("No accessible leaderboard results; previous site retained.")

payload = {
    "competition": "OLO Academy · Cumulative Individual Rankings",
    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "rounds": rounds, "people": ranking, "unmapped": unmapped,
    "note": "Teams with unknown memberships are listed as pending rather than incorrectly awarded solo points. Placeholder members need verified names.",
    "scoring": "Team rank points: 1st 100, 2nd 90, 3rd 80, etc. (minimum 10). Each member gets team points ÷ registered team size.",
}
(OUT / "leaderboard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Published {len(ranking)} participants. Unmapped team rosters: {len(unmapped)}")
