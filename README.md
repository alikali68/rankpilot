# 🔍 RankPilot

> Data-driven SEO & technical website auditor. Deterministic scoring engine, concurrent crawler, zero APIs, pure Python.

**🚀 Live demo:** https://rankpilot-wvugccwcscig6wdpe2pqiq.streamlit.app/

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=flat&logo=plotly&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-2CA5E0?style=flat)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

---

## ✨ Features — Enterprise Edition

| Feature | Details |
|---------|---------|
| 🔍 7-category audit | Meta, headings, images, links, performance, security, content — 25 checks |
| 💯 Deterministic scoring | 0–100 with transparent weights — no black boxes |
| ⚡ Concurrent crawler | `ThreadPoolExecutor` — link & image probes run in parallel |
| 📱 Device profiles | Desktop Chrome 128 · Mobile iPhone Safari · Googlebot |
| 🎓 Letter grades | A (90+) → F (<60), with per-category sub-scores |
| 📊 Radar analytics | Plotly polar chart + category distribution table |
| 🎯 Priority action plan | Fails ranked by weight × severity — fix what moves the needle |
| 📄 PDF export | One-click client-ready audit report (ReportLab) |
| 💾 JSON export | Raw structured data for pipelines & SEO teams |
| 🌙 Premium dark UI | Tabbed Streamlit dashboard, custom CSS |
| 🐳 Docker-ready | Dockerfile + docker-compose for one-command deploy |

---

## 🧠 The Science — how the audit engine works

RankPilot doesn't guess — it *measures*. Every audit runs the same deterministic pipeline: same URL, same score, every time. No ML black boxes, no mystery heuristics.

### Pipeline

```mermaid
flowchart LR
    A[🌐 Target URL] --> B[📡 Session fetch]
    B --> C[🔬 DOM parse]
    C --> D[🧪 7 audit suites]
    D --> E[⚡ Concurrent probes]
    E --> F[⚖️ Weighted scoring]
    F --> G[🎯 Priority ranking]
    G --> H[📊 Dashboard · 📄 PDF · 💾 JSON]
```

### 1. 📡 Session-based fetching
A persistent `requests.Session` (connection pooling, real desktop User-Agent) fetches the target with a 10-second timeout. Typed error handling distinguishes SSL failures, timeouts, and DNS errors — each surfaces as a clear message, never a traceback. Non-HTML responses are rejected *before* parsing, so a PDF link never produces a garbage audit.

### 2. 🔬 Single-parse DOM
BeautifulSoup + `lxml` builds the document tree **once**. All seven audit suites read from that same tree — no re-fetching, no re-parsing, no wasted work.

### 3. 🧪 The seven audit suites — 25 checks
Each check is a pure function returning `earned / maximum` points, a finding, and a concrete recommendation:

- **Meta & Head (20 pts)** — title 30–60 chars, meta description 120–160 chars, viewport, charset, Open Graph trio, canonical URL
- **Headings (15 pts)** — exactly one H1, no skipped levels, non-empty headings, H1 20–70 chars
- **Images (15 pts)** — alt-text coverage, explicit width/height (kills Cumulative Layout Shift), file weight < 1MB via lightweight HEAD probes
- **Links (15 pts)** — broken-link scan with HEAD→GET fallback for CDN-blocked HEADs, anchor-text quality, `rel="noopener/nofollow"` on externals
- **Performance (15 pts)** — HTML < 100KB, external scripts ≤ 8, stylesheets ≤ 4, gzip/Brotli detection
- **Security (10 pts)** — HTTPS enforcement, mixed-content asset scan
- **Content (10 pts)** — 300+ words, H2 structure, average-sentence-length readability proxy

### 4. ⚡ Concurrency model
Link verification (up to 15 targets) and image weight probes (up to 10) run in dedicated `ThreadPoolExecutor` pools — 8 workers for links, 5 for images. What would take ~75 seconds sequentially completes in about 10. Sessions are reused across threads for connection pooling, and every streamed response is properly closed.

### 5. ⚖️ Deterministic scoring
Each check awards **full / partial / zero** credit against published thresholds — e.g. title 30–60 chars = 6 pts, present-but-off-length = 3, missing = 0. Status bands: **pass** ≥ 80%, **warn** 40–79%, **fail** < 40%. Grades map A (90+) → F (<60). The weight table is rendered in the UI next to every score — the number is fully auditable, never magic.

### 6. 🎯 Priority ranking
Every failed/warned check is ranked by `category_weight × severity` (fail = 2, warn = 1). The action plan therefore lists fixes in the order of *points recovered* — the single most valuable thing a site owner can do first.

### 7. 📱 Device profiles
Three User-Agent profiles — **Desktop Chrome 128**, **Mobile iPhone Safari**, **Googlebot** — because what users see, what phones see, and what Google sees are three different audits. Pick the lens before you scan.

---

## 🏗️ Architecture

The engine is fully decoupled from the UI — import it anywhere, no Streamlit required:

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

```python
from core.engine import RankPilotEngine

report = RankPilotEngine().inspect_url("https://example.com")
print(report.total_score, report.letter_grade)   # 70.5 C
```

**Data flow:** `URL → RankPilotEngine.inspect_url() → AuditReport → dashboard / PDF / JSON`.
The `AuditReport` dataclass is the single source of truth — the dashboard, the PDF generator, and the JSON exporter all derive from it.

---

## ⚡ Performance

| Technique | Effect |
|-----------|--------|
| `ThreadPoolExecutor` (8 workers) | Link health checks run concurrently |
| `ThreadPoolExecutor` (5 workers) | Image weight probes run concurrently |
| Session reuse | One `requests.Session` per audit — connection pooling |
| Bounded sampling | ≤15 links, ≤10 images, 10s fetch timeout |

Typical full audit: **seconds, not minutes**.

---

## 🛠️ Tech stack

- **Python 3.11** — core language
- **Streamlit** — dashboard UI
- **Requests** — HTTP fetching & concurrent probing
- **BeautifulSoup4 + lxml** — HTML parsing
- **Plotly** — radar-chart analytics
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
