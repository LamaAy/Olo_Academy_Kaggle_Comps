# OLO Academy Arabic Classification Challenge — Live Leaderboard

Displays the OLO Academy Arabic Classification Challenge public Kaggle leaderboard and refreshes it every 15 minutes with GitHub Actions (subject to GitHub's schedule queue and Kaggle API availability). The browser checks the published JSON every minute.

Competition: https://www.kaggle.com/competitions/olo-academy-arabic-classification-challenge/leaderboard?tab=public

## Setup

1. Create a **public** GitHub repository (e.g. `kaggle-leaderboard`) and upload all these files, including `.github/workflows/publish.yml`.
2. Open **Settings → Secrets and variables → Actions**.
   - Under **Secrets**, add `KAGGLE_USERNAME` and `KAGGLE_KEY` (classic Kaggle API username/key), **or** a supported `KAGGLE_API_TOKEN` if using Kaggle's newer token format. Never commit any credentials.
3. Ensure the Kaggle account for that token has accepted the competition rules and has access to the leaderboard.
4. Open **Settings → Pages → Build and deployment → Source → GitHub Actions**.
5. Open **Actions → Refresh Kaggle Leaderboard → Run workflow** for the first update. View the published URL shown in the workflow's deployment job.
6. The workflow runs automatically approximately every 15 minutes. Scheduled workflows may be delayed; use **Run workflow** to force a refresh.

## Notes

- This is the **public** leaderboard during an active competition, not the private final results.
- Kaggle's downloaded CSV is assumed to be sorted by leaderboard rank. Score direction (higher/lower better) is handled by Kaggle, not re-sorted by this site.
- GitHub Pages files are public, so team names and scores are public. Do not use this setup to display a private competition's rankings without permission.
- If the Kaggle CLI download returns a ZIP or a nonstandard CSV, adapt `fetch_leaderboard.py` to your downloaded file format.
- Initial score table will appear after the first successful GitHub Actions run.
