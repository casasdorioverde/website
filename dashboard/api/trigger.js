// Vercel serverless function that triggers the weekly report workflow on
// GitHub Actions (workflow_dispatch). The GitHub token never reaches the
// browser: it lives in a Vercel env var, and the button on the dashboard
// must send the shared passphrase (TRIGGER_SECRET) to use this endpoint,
// since the dashboard itself is publicly reachable.
//
// Required env vars on the Vercel project (Settings -> Environment Variables):
//   GITHUB_DISPATCH_TOKEN - fine-grained PAT, "Actions: write" on the repo
//   TRIGGER_SECRET        - passphrase you choose; typed into the dashboard
// Optional:
//   WORKFLOW_REPO - defaults to "casasdorioverde/website"
//   WORKFLOW_REF  - branch containing the workflow file,
//                   defaults to "claude/bb-competitor-price-tool-g1t21u"

const WORKFLOW_FILE = "competitor-pricing.yml";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST" });
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN;
  const secret = process.env.TRIGGER_SECRET;
  if (!token || !secret) {
    return res.status(503).json({
      error:
        "Not configured yet: set GITHUB_DISPATCH_TOKEN and TRIGGER_SECRET " +
        "in the Vercel project's environment variables.",
    });
  }

  if ((req.body && req.body.secret) !== secret) {
    return res.status(401).json({ error: "Wrong passphrase" });
  }

  const repo = process.env.WORKFLOW_REPO || "casasdorioverde/website";
  const ref = process.env.WORKFLOW_REF || "claude/bb-competitor-price-tool-g1t21u";

  const ghRes = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "competitor-pricing-dashboard",
      },
      body: JSON.stringify({ ref }),
    }
  );

  if (ghRes.status === 204) {
    return res.status(200).json({
      ok: true,
      message: `Workflow triggered on ${ref}. It takes a few minutes; refresh later.`,
    });
  }

  const detail = await ghRes.text();
  return res.status(502).json({
    error: `GitHub responded ${ghRes.status}`,
    detail: detail.slice(0, 500),
  });
}
