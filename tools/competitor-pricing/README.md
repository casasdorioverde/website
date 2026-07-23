# Competitor pricing tool

Weekly comparison of your B&B's price against nearby competitors: price per
night, room count, whether they have a pool, review rating, and a best-effort
occupancy signal. Emails you an HTML + CSV report, and publishes the same
data to a small dashboard at [`../../dashboard`](../../dashboard) (deployed
to the Vercel project `calc`).

Each run checks up to three **date windows** (next weekend, +30 days,
+90 days — configurable under `search.windows`), scrapes **your own
Booking.com listing** as a parity check (`us.booking_url`), and keeps a
**history** of dated snapshots (`--history-dir`) that powers week-over-week
deltas, dashboard sparklines, and **change alerts** (price moves ≥10%,
newly sold out, a competitor newly undercutting you). With
`email.mode: changes_only` the email is only sent on runs with alerts.

## How each source is handled

- **Booking.com** — scraped directly (headless browser via Playwright,
  because Booking renders prices client-side). Booking's markup changes
  often and their Terms of Service restrict automated access, so treat this
  as best-effort: it degrades gracefully (missing fields show as `?` rather
  than crashing), keeps request volume to one page load per competitor per
  week, and you should recheck the selectors in
  `competitor_pricing/scrapers/booking.py` if fields stop populating.
- **Airbnb** — **not scraped**. Airbnb has no public API and actively blocks
  automated access. Instead, `competitor_pricing/providers/http_json.py` is a
  generic client you point at a paid data vendor (AirDNA, Rabbu, AirROI,
  Mashvisor, PriceLabs, etc.) that legitimately resells Airbnb price/occupancy
  estimates. Sign up with one, then fill in `airbnb_provider` in
  `config.yaml` — `field_map` uses dot-notation to pull values out of
  whatever JSON shape that vendor returns, so no code changes are needed for
  a typical REST+JSON API. Leave `enabled: false` until you have a
  subscription; competitors with only an `airbnb_listing_id` will just show
  `?` until then.
- **Your own price** — entered manually in `config.yaml` (`us:` section).
  There's no scraping needed for your own listing since you know your price.

## Occupancy

Nobody publishes real occupancy numbers for free. The Booking scraper looks
for the scarcity language Booking shows on the page itself ("Sold out",
"Only 2 rooms left", "In high demand") and reports `sold_out` / `limited` /
`available` / `unknown` accordingly — it's a signal, not a hard number. The
Airbnb provider path can report a real `occupancy_pct` if your chosen vendor
supplies one.

## Zones (grouping competitors by area)

Every property is tagged with a Madeira **zone** so the report and dashboard
can group like-for-like and highlight the competitors that actually share your
market. There are five canonical zones, ordered west → east:

| Zone key      | Label            | Covers                                            |
| ------------- | ---------------- | ------------------------------------------------- |
| `southwest`   | South-West       | Ponta do Sol, Calheta, Ribeira Brava — **home**   |
| `south`       | South / Funchal  | Funchal, Câmara de Lobos                           |
| `southeast`   | South-East       | Santa Cruz, Machico, Caniço, airport              |
| `north`       | North            | São Vicente, Santana, Porto Moniz, Porto da Cruz  |
| `porto-santo` | Porto Santo      | Porto Santo island                                |

You don't have to remember the exact keys. The `region:` field on each
competitor (and `us.zone`) is normalised by `competitor_pricing/zones.py`, so
a compass point (`SW`), a zone name (`southwest`), or just a town (`Calheta`,
`Machico`) all resolve to the right zone — accents and case are ignored. An
unrecognised value is grouped under **Other / unmapped** and logged as a
warning so you can spot the typo. `us.zone` marks your **home zone**, which the
dashboard highlights and compares against directly.

Run the zone tests with `python tests/test_zones.py` (or `pytest tests/`).

## Setup

```bash
cd tools/competitor-pricing
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.example.yaml config.yaml
# edit config.yaml: your price, competitor Booking.com URLs / Airbnb listing IDs
```

Test locally without sending email:

```bash
python -m competitor_pricing.main --dry-run
# or, to also save a CSV locally:
python -m competitor_pricing.main --dry-run --output-csv report.csv
# full CI-equivalent run (JSON for the dashboard + history snapshots):
python -m competitor_pricing.main \
  --output-json ../../dashboard/public/data/latest.json \
  --history-dir ../../dashboard/public/data/history
```

## Running for real (email)

Requires an SMTP account (Gmail app password, SendGrid, your host's SMTP,
etc.) and `email.from` / `email.to` set in `config.yaml`:

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USER=you@example.com
export SMTP_PASSWORD=...
export AIRBNB_DATA_API_KEY=...   # only if airbnb_provider.enabled: true

python -m competitor_pricing.main
```

## Weekly automation (GitHub Actions)

`.github/workflows/competitor-pricing.yml` runs this every Monday. It needs
these repository secrets (Settings → Secrets and variables → Actions):

- `COMPETITOR_PRICING_CONFIG` — the full contents of your `config.yaml`
  (kept as a secret rather than committed, since it lists competitors and
  email addresses)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `AIRBNB_DATA_API_KEY` — only needed if you enable the Airbnb provider
- `VERCEL_TOKEN` — a Vercel personal access token (vercel.com → Settings →
  Tokens), used to redeploy the `dashboard/` directory to the `calc`
  project after each run

You can also trigger it manually from the Actions tab (`workflow_dispatch`).

## Adding/removing competitors

Edit `config.yaml` (or the `COMPETITOR_PRICING_CONFIG` secret for the
scheduled run) — no code changes needed. Each entry needs a `booking_url`
and/or `airbnb_listing_id`; `rooms` / `has_pool` are optional manual
fallbacks used whenever the scraper or provider can't confirm a value.
