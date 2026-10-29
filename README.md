# Killian's Wall of Love ❤️

Every Trustpilot, AppSumo and Poppy Wall of Love review that names Killian, on one page to
send people before their call.

- `index.html` — the page. Reads `reviews.json`.
- `reviews.json` — the reviews. Built by `tools/refresh.py`; don't edit by hand.
- `hidden.json` — review ids to leave off the page, e.g. `["as:385369", "tp:6a8f8c3c01ca2da21ac124ea"]`.
- `tools/trustpilot_seed.json` — the Trustpilot reviews collected by hand on 2026-10-28.

## How it stays up to date

`.github/workflows/refresh.yml` runs every 3 hours. It reads:

1. **AppSumo** — `appsumo.com/api/v2/deals/255707/reviews/` (public).
2. **The Poppy Wall of Love feed** — `getpoppy.ai/api/proof` (public). The Wall imports new
   Trustpilot reviews on its own, so new Trustpilot reviews arrive this way.

Any review that says Killian (or Kilian / Killan) gets added, then the page republishes.
Reviews are never removed by a refresh; only `hidden.json` takes one off.

Trustpilot itself blocks servers, so a Trustpilot review the Wall never imports (like
Constance Lyners Mendes, Oct 14) has to be added to `tools/trustpilot_seed.json` by hand.

## The link to send

**https://killian-poppy.vercel.app/wall-of-love**

`short-link/vercel.json` is a Vercel project (`killian-poppy`, Killian's own account) that shows the
GitHub Pages page under that address. It never needs redeploying: the page loads its photo and
`reviews.json` from GitHub Pages (`<base href>` in `index.html`), so the 3-hourly refresh shows up
there too. To change the Vercel config: `cd short-link && npx vercel deploy --prod`.

## Run it locally

```bash
python3 tools/refresh.py
```
