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

## "Run report now" button

The dashboard has a button that triggers the GitHub Actions workflow on
demand via `api/trigger.js` (a Vercel serverless function). The GitHub
token stays server-side. Note there is no passphrase: anyone who finds the
dashboard URL can start a run. To activate the button, set these
environment variables on the `calc` Vercel project (Settings ->
Environment Variables), then redeploy:

- `GITHUB_DISPATCH_TOKEN` - a fine-grained GitHub personal access token
  (github.com -> Settings -> Developer settings -> Fine-grained tokens)
  scoped to this repo with **Actions: Read and write** permission
- `WORKFLOW_REF` (optional) - branch containing the workflow file; defaults
  to the repo's default branch

Until the token is set, the button returns a clear "not configured"
message.
