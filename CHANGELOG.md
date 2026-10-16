# Changelog

All notable changes to RankPilot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/): every version lists
what was added, changed, and fixed — no silent behavior changes.

---

## [2.1.0] — 2026-10-16 — Module M2: Competitor Comparison

### Added
- **Compare audit mode** — benchmark any site against a competitor side-by-side.
- `core/compare.py` — deterministic comparison engine: per-check score
  normalization to 0–100, score/category deltas, win/lose/tie verdicts
  (tie = gap under 2 points), ranked **priority opportunities**
  (checks the competitor passes where you fail), and pages-behind count.
- Comparison dashboard: side-by-side score cards, diverging category-delta
  bar chart, sortable check matrix, opportunity cards.
- Two-page executive comparison PDF export.
- Honest staged progress reporting across both audits; a competitor crawl
  that fails surfaces a clear warning instead of aborting your audit.

### Fixed
- Failed pages now contribute 0 to per-check averages, consistent with how
  they contribute 0 to the headline site average (previously excluded,
  which made the comparison table look rosier than the site score).

## [2.0.0] — 2026-10-13 — Module M1: Multi-Page Site Audit

### Added
- **Full-site audit mode** — deterministic `/sitemap.xml` discovery
  (index files followed recursively, same-domain filtering, dedup,
  capped at `max_pages`), polite concurrent crawling
  (`ThreadPoolExecutor`, 5 workers, 0.3 s dispatch stagger).
- `SiteAuditReport` — average, median, per-category averages, weakest-5
  pages, A–F site grade on the identical scale as single-page audits.
- Site dashboard: aggregate health cards, weakest-page ranking,
  category distribution, one-page executive site PDF, site JSON export.
- Failed pages record zero-score reports instead of aborting the crawl;
  results stay in deterministic sitemap order across runs.

### Changed
- Professional scientific README: full methodology documentation
  (sitemap discovery, crawl politeness, aggregation statistics).

## [1.1.0] — 2026-10-11 → 2026-10-12 — Reliability & Correctness

### Fixed
- **Accept-Encoding decompression bug** — a manual `Accept-Encoding` header
  broke `urllib3` auto-decompression and produced false deflated scores;
  the engine now lets `requests` negotiate encoding (true scores restored).
- Fetch timeout raised to 30 s with retry for slow/large hosts.

## [1.0.0] — 2026-10-10 — Initial Release: RankPilot Enterprise Edition

### Added
- **Deterministic 25-check audit engine** (`core/engine.py`) across
  7 weighted categories — Meta & Head (20), Headings (15), Images (15),
  Links (15), Performance (15), Security (10), Content (10).
  Same URL → same score, every run. Zero ML, zero external APIs.
- Single-page Streamlit dashboard: Plotly radar chart, category tables,
  priority action plan (fails ranked by weight × severity).
- Device profiles: Desktop Chrome, Mobile iPhone Safari, Googlebot.
- One-click PDF audit report (ReportLab) and raw JSON export.
- Dark premium UI, Dockerfile + docker-compose one-command deploy.
- Live demo on Streamlit Community Cloud.
