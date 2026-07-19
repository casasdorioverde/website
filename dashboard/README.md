# Competitor pricing dashboard

Static page (no build step) that reads `data/latest.json` and renders the
weekly competitor comparison table. Deployed to the Vercel project `calc`.

`data/latest.json` is overwritten every week by the GitHub Actions workflow
(`.github/workflows/competitor-pricing.yml`), which runs
`tools/competitor-pricing`'s `main.py --output-json` and redeploys this
directory to Vercel. It's also committed to the repo so the placeholder
(empty) state ships correctly before the first real run.

To preview locally, just open `index.html` in a browser, or serve the
directory (`python3 -m http.server`) since `fetch()` needs http(s), not
`file://`.
