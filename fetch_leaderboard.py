import csv
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

slug = os.environ.get('KAGGLE_COMPETITION', 'olo-academy-arabic-classification-challenge').strip()
if not slug:
    raise SystemExit('Set the KAGGLE_COMPETITION repository variable to your competition URL slug.')

out = Path('site')
out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    subprocess.run(['kaggle', 'competitions', 'leaderboard', slug, '--download', '--path', temp, '--quiet'], check=True)
    files = list(Path(temp).rglob('*.csv'))
    if not files:
        import zipfile
        for archive in Path(temp).rglob('*.zip'):
            with zipfile.ZipFile(archive) as z:
                z.extractall(temp)
        files = list(Path(temp).rglob('*.csv'))
    if not files:
        raise SystemExit('Kaggle returned no leaderboard CSV; check competition access and submissions.')
    file = max(files, key=lambda f: f.stat().st_mtime)
    with file.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)


def field(row, *names):
    lower = {k.lower().replace('_', '').replace(' ', ''): v for k, v in row.items() if k}
    for name in names:
        val = lower.get(name.lower().replace('_', '').replace(' ', ''))
        if val is not None:
            return val
    return ''

teams = []
for row in rows:
    name = field(row, 'teamName', 'team', 'Team Name')
    score = field(row, 'score', 'publicScore', 'public score')
    if not name:
        continue
    teams.append({
        'team': name,
        'rank': field(row, 'rank', 'publicRank') or str(len(teams) + 1),
        'score': score,
        'submission_date': field(row, 'submissionDate', 'lastSubmission', 'Submission Date'),
    })

payload = {
    'competition': 'OLO Academy Arabic Classification Challenge',
    'competition_url': 'https://www.kaggle.com/competitions/olo-academy-arabic-classification-challenge/leaderboard?tab=public',
    'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'teams': teams,
}
(out / 'leaderboard.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"Prepared {len(teams)} teams for {slug}")
