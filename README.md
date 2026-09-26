# Apafin

Web app for Anna at Wesser und Partner. One search returns up to three holiday apartments for one team.

The page ranks. TypeSafe Jev only answers keep or drop when a listing page does not state beds and bedrooms. Portal clicks go through a `jev-ra` browser session, one Chrome profile per site (`booking`, `airbnb`, `fewo`). A Cursor agent is not in that loop.

## Test setup

The form opens with this card:

- loaded apartment URL: the Airbnb room `769166993968066796`
- working place: Detligen + Frieswil
- team: 3M, 2F
- budget: 1000 CHF
- stay: next Monday afternoon to Friday morning
- must have: kitchen, towels, wifi, bathroom
- max ride: 30 minutes to each place

Sample scores that card without opening a portal. Search runs `uvx jev-ra` when `uvx` is installed. `TYPESAFE_API_KEY` stays on the server.

## Run

```bash
conda activate mini-proj
python -m unittest discover -s tests
python -m app.server
```

The server sets `JEV_RA_CHROME` to Playwright's Chromium under `~/.cache/ms-playwright` when that variable is empty.

Open http://127.0.0.1:8080. Ctrl+Enter searches. Ctrl+Shift+Enter scores the sample.

## Image

`VERSION` is the product version. A Grieder Labs DeployUnit pins the built image sha. The container stays up. Secrets are mounted at run time, not baked in.

```bash
docker compose up -d --build
```
