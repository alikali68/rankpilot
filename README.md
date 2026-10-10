# 🔍 RankPilot

> Data-driven SEO & technical website auditor. Deterministic scoring engine, zero APIs, pure Python.

**🚀 Live demo:** _deploying…_

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![BeautifulSoup4](https://img.shields.io/badge/BeautifulSoup4-43B02A?style=flat)
![Requests](https://img.shields.io/badge/Requests-2CA5E0?style=flat)

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🔍 7-category audit | Meta, headings, images, links, performance, security, content |
| 💯 Deterministic scoring | 0–100 with transparent weights — no black boxes |
| 🎓 Letter grades | A (90+) → F (<60), with per-category sub-scores |
| 🎯 Priority fix list | Fails ranked by weight × severity — fix what matters first |
| 🔗 Broken-link scanner | HEAD-checks up to 15 links, GET fallback for CDN-blocked HEADs |
| ⬇️ Markdown report | One-click full audit report download |
| 🌙 Dark modern UI | Tabbed Streamlit dashboard with custom CSS |

---

## 🧠 The Science — the scoring engine

Every audit runs the same deterministic pipeline. Same URL → same score, every time.

### Weights

| Category | Weight | What it measures |
|----------|--------|------------------|
| Meta & Head | 20 | title, meta description, viewport, charset, Open Graph, canonical |
| Headings | 15 | single H1, hierarchy, non-empty headings, H1 length |
| Images | 15 | alt-text coverage, dimensions, file weight |
| Links | 15 | broken links, anchor-text quality, external `rel` attributes |
| Performance | 15 | HTML size, script/style counts, compression |
| Security | 10 | HTTPS, mixed content |
| Content | 10 | word count, H2 structure, readability proxy |

### Check mechanics

Each check awards **full / partial / zero** credit against explicit thresholds —
e.g. title 30–60 chars = 6 pts, present-but-off-length = 3, missing = 0.
Status bands: **pass** ≥ 80%, **warn** 40–79%, **fail** < 40%.

### Priority ranking

Failed and warned checks are ranked by `category_weight × severity`
(fail = 2, warn = 1) — the fixes that move the score most come first.

---

## 🏗️ Architecture

```
app.py
├── CONFIG   → weights, thresholds, timeouts, user-agent
├── MODELS   → AuditCheck / AuditReport dataclasses
├── FETCH    → requests with desktop UA, 10s timeout, typed error handling
├── AUDIT    → audit_meta · audit_headings · audit_images · audit_links
│              audit_performance · audit_security · audit_content
├── SCORING  → aggregation, grade mapping, priority ranking
├── REPORT   → Markdown report builder
└── UI       → Streamlit: input · score hero · tabbed results · downloads
```

**Data flow:** `URL → Response → BeautifulSoup → checks[] → scores → report → UI`.
The `AuditReport` dataclass is the single source of truth — every view derives from it.

---

## ⚡ Performance notes

- Broken-link scan caps at 15 links × 5s HEAD timeout, with GET fallback
- Image weight sampling caps at 10 images via lightweight HEAD `Content-Length`
- A full audit typically completes in 5–20s depending on target responsiveness

---

## 🛠️ Tech stack

- **Python 3** — core language
- **Streamlit** — dashboard UI
- **Requests** — HTTP fetching & link probing
- **BeautifulSoup4 + lxml** — HTML parsing

## 🚀 Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ☁️ Deploy

One-click deploy on [Streamlit Community Cloud](https://streamlit.io/cloud) —
connect the repo and set `app.py` as the entry point.

## 🔮 Roadmap

- [ ] Core Web Vitals via PageSpeed API (optional key)
- [ ] Historical tracking — re-audit and diff scores over time
- [ ] PDF report export
- [ ] Sitemap-aware multi-page crawl

---

<p align="center">RankPilot — data-driven SEO audits 🔍</p>
