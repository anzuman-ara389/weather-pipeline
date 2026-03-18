# Automated Weather Pipeline with GitHub Pages

This repository is a small end-to-end data pipeline for the course assignment.

It does four things automatically:
1. fetches tomorrow's weather forecast from Open-Meteo
2. stores the result in a local SQLite database
3. asks Groq to generate a bilingual poem
4. publishes the result to GitHub Pages

## Repository structure

- `fetch.py` – main pipeline script
- `weather.db` – SQLite database created automatically
- `locations.json` – the 3 places used in the assignment
- `.github/workflows/weather.yml` – GitHub Actions workflow
- `docs/index.html` – published GitHub Pages site
- `docs/data.json` – raw structured output for the latest run

## Setup

### 1. Replace the placeholder locations

Edit `locations.json` so the three entries match:
- your place of birth
- your last residence before arriving to Aalborg
- Aalborg

If all 3 would be Aalborg, use the allowed fallback from the assignment:
- Aalborg
- Copenhagen
- Nice, France

## 2. Create a Groq API key

Create an API key in Groq, then add it as a GitHub repository secret:
- name: `GROQ_API_KEY`
- value: your real key

In GitHub:
`Settings -> Secrets and variables -> Actions -> New repository secret`

## 3. Optional local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your_key_here"
python fetch.py
```

## 4. Enable GitHub Pages

In GitHub:
- go to `Settings -> Pages`
- under **Build and deployment**, choose **Deploy from a branch**
- branch: `main`
- folder: `/docs`

## 5. Workflow schedule

GitHub Actions cron runs in UTC.
The workflow in this repo is set to run daily at **19:00 UTC**, which matches **20:00 Danish time during standard time (CET)**.

If you want it to match Danish summer time exactly later, you would need to adjust the cron because GitHub Actions schedules do not use Europe/Copenhagen time directly.

## Notes for the report / presentation

This solution uses:
- **API**: Open-Meteo weather API + geocoding API
- **Database**: SQLite
- **LLM**: Groq API
- **Automation**: GitHub Actions
- **Publishing**: GitHub Pages

## Change the second language in the poem

Inside `fetch.py`, search for this sentence in `generate_poem()`:

```python
2) Your native language placeholder: replace this with the user's chosen language from the repo README.
```

Replace that text with your actual language, for example:
- Danish
- Arabic
- Romanian
- French

That makes the poem bilingual in English + your chosen language.
