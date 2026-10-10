# 🔍 RankPilot

> Data-driven SEO & technical website auditor. Deterministic scoring engine, concurrent crawler, zero APIs, pure Python.

**🚀 Live demo:** _deploying…_

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=flat&logo=plotly&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-2CA5E0?style=flat)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

---

## ✨ Features — Enterprise Edition

| Feature | Details |
|---------|---------|
| 🔍 7-category audit | Meta, headings, images, links, performance, security, content |
| 💯 Deterministic scoring | 0–100 with transparent weights — no black boxes |
| ⚡ Concurrent crawler | `ThreadPoolExecutor` — link & image checks run in parallel |
| 📱 Device profiles | Desktop Chrome 128 · Mobile iPhone Safari · Googlebot |
| 🎓 Letter grades | A (90+) → F (<60), with per-category sub-scores |
| 📊 Radar analytics | Plotly polar chart + category distribution table |
| 🎯 Priority action plan | Fails ranked by weight × severity |
| 📄 PDF export | One-click client-ready audit report (ReportLab) |
| 💾 JSON export | Raw structured data for pipelines & SEO teams |
| 🌙 Premium dark UI | Tabbed Streamlit dashboard, custom CSS |
| 🐳 Docker-ready | Dockerfile + docker-compose for one-command deploy |

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
rankpilot/
├── app.py              → Streamlit Enterprise dashboard (UI, charts, exports)
├── core/
│   ├── __init__.py
│   ├── models.py       → AuditCheck / AuditReport dataclasses
│   └── engine.py       → RankPilotEngine: fetch, audit, scoring
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

**Data flow:** `URL → RankPilotEngine.inspect_url() → AuditReport → dashboard / PDF / JSON`.
The engine is fully decoupled from the UI — import it anywhere:

```python
from core.engine import RankPilotEngine

report = RankPilotEngine().inspect_url("https://example.com")
print(report.total_score, report.letter_grade)
```

---

## ⚡ Performance

| Technique | Effect |
|-----------|--------|
| `ThreadPoolExecutor` (8 workers) | Link health checks run concurrently |
| `ThreadPoolExecutor` (5 workers) | Image weight probes run concurrently |
| Session reuse | One `requests.Session` per audit — connection pooling |
| Bounded sampling | ≤15 links, ≤10 images per audit |

Typical full audit: **seconds, not minutes**.

---

## 🛠️ Tech stack

- **Python 3.11** — core language
- **Streamlit** — dashboard UI
- **Requests** — HTTP fetching & concurrent probing
- **BeautifulSoup4 + lxml** — HTML parsing
- **Plotly** — radar chart analytics
- **ReportLab** — PDF report generation
- **Docker** — containerized deployment

## 🚀 Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or with Docker:

```bash
docker compose up -d --build
# open http://localhost:8501
```

## ☁️ Cloud deploy

One-click deploy on [Streamlit Community Cloud](https://streamlit.io/cloud) —
connect the repo and set `app.py` as the entry point.

## 🔮 Roadmap

- [ ] Core Web Vitals via PageSpeed API (optional key)
- [ ] Historical tracking — re-audit and diff scores over time
- [ ] Sitemap-aware multi-page crawl
- [ ] Scheduled audits with email digests

---

<p align="center">RankPilot — data-driven SEO audits 🔍</p>
