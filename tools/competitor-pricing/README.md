# Competitor pricing tool

Weekly comparison of your B&B's price against nearby competitors: price per
night, room count, whether they have a pool, review rating, and a best-effort
occupancy signal. Emails you an HTML + CSV report, and publishes the same
data to a small dashboard at [`../../dashboard`](../../dashboard) (deployed
to the Vercel project `calc`).

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
