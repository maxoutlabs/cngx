# cngx Drift Tracker

Static public site for opt-in community drift metrics. Built with plain Python (`tracker/build.py`), no framework, deployed to GitHub Pages.

## Sample data policy

**Default view: empty community charts until live data loads.** The browser fetches aggregated community metrics from a public S3 index every few minutes. Sample records in `data/samples/` are bundled for pipeline testing and illustration only. They are exposed behind an explicit **"show illustrative sample"** toggle, not on first load.

Community submissions arrive via `cngx submit` (HTTPS POST). No GitHub pull requests. No personal identity is collected or stored.

## Directory layout

```
tracker/
├── README.md
├── build.py            # Builds site/ (index + docs/)
├── static/
│   ├── site.css        # Shared minimal styles
│   ├── app.js          # Tracker charts + live S3 fetch + sample toggle
│   └── docs.js         # Docs sidebar + copy buttons
├── scripts/
│   └── capture_screenshots.py  # Playwright visual + dash verification
├── data/
│   ├── samples/        # Demo data (opt-in in UI only)
│   └── community/      # Real submissions
└── site/               # Generated output (deployed)
    ├── index.html
    ├── docs/index.html
    ├── data.js
    ├── site.css
    ├── app.js
    └── docs.js
```

## Build locally

```bash
python tracker/build.py
python tracker/scripts/capture_screenshots.py  # requires playwright + chromium
```

## Deployment

`.github/workflows/tracker-deploy.yml` builds and deploys `tracker/site/` to GitHub Pages on push to `main` (tracker paths only).
