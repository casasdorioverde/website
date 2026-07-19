// Vercel serverless function that triggers the weekly report workflow on
// GitHub Actions (workflow_dispatch). The GitHub token never reaches the
// browser: it lives in a Vercel env var. Note the endpoint is open -
// anyone who finds the dashboard URL can start a workflow run.
//
// Required env vars on the Vercel project (Settings -> Environment Variables):
//   GITHUB_DISPATCH_TOKEN - fine-grained PAT, "Actions: write" on the repo
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
  if (!token) {
    return res.status(503).json({
      error:
        "Not configured yet: set GITHUB_DISPATCH_TOKEN in the Vercel " +
        "project's environment variables.",
    });
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
