"""
RankPilot Deterministic Scoring Engine.
High-concurrency technical crawler & validator.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.models import AuditCheck, AuditReport

GENERIC_ANCHOR_SET = {
    "click here", "click", "read more", "learn more",
    "more", "link", "here", "this", "website", "view more",
    "continue", "details", "info",
}

USER_AGENTS = {
    "Desktop (Chrome 128)": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Mobile (iPhone Safari)": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    ),
    "Googlebot Desktop": (
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    ),
}


class RankPilotEngine:
    def __init__(self, user_agent_key: str = "Desktop (Chrome 128)", timeout: int = 10):
        self.ua = USER_AGENTS.get(user_agent_key, USER_AGENTS["Desktop (Chrome 128)"])
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        })

    @staticmethod
    def _calc_status(earned: float, maximum: float) -> str:
        if maximum <= 0:
            return "pass"
        ratio = earned / maximum
        if ratio >= 0.80:
            return "pass"
        if ratio >= 0.40:
            return "warn"
        return "fail"

    @staticmethod
    def _calc_grade(score: float) -> str:
        if score >= 90.0:
            return "A"
        if score >= 80.0:
            return "B"
        if score >= 70.0:
            return "C"
        if score >= 60.0:
            return "D"
        return "F"

    def fetch(self, url: str) -> Tuple[requests.Response | None, str | None]:
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url

        try:
            resp = self.session.get(clean_url, timeout=self.timeout, allow_redirects=True)
            return resp, None
        except requests.exceptions.SSLError as e:
            return None, f"SSL/TLS Handshake Error: {str(e)}"
        except requests.exceptions.Timeout:
            return None, f"Connection timed out after {self.timeout}s."
        except requests.exceptions.ConnectionError:
            return None, "DNS Lookup / Connection failure. Server unreachable."
        except requests.exceptions.RequestException as e:
            return None, f"HTTP Protocol Error: {str(e)}"

    def inspect_url(self, target_url: str) -> AuditReport:
        t_start = time.time()
        resp, err = self.fetch(target_url)
        if err:
            raise RuntimeError(err)

        content_type = resp.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise RuntimeError(
                f"URL did not return HTML content (Content-Type: {content_type or 'unknown'})."
            )

        final_url = resp.url
        parsed_base = urlparse(final_url)
        content_bytes = resp.content
        html_text = resp.text
        doc_size_kb = len(content_bytes) / 1024.0

        soup = BeautifulSoup(html_text, "lxml")
        checks: List[AuditCheck] = []

        # =====================================================================
        # 1. Meta & Head (20 pts)
        # =====================================================================
        # Title (6 pts)
        t_tag = soup.find("title")
        title_txt = t_tag.get_text().strip() if t_tag else ""
        t_len = len(title_txt)
        if 30 <= t_len <= 60:
            t_score = 6.0
            t_msg = f"Title length optimal ({t_len} chars): '{title_txt}'"
        elif t_len > 0:
            t_score = 3.0
            t_msg = f"Title present but sub-optimal length ({t_len} chars). Target: 30-60 chars."
        else:
            t_score = 0.0
            t_msg = "No <title> tag found."
        checks.append(AuditCheck(
            "meta_title", "Title Tag", "Meta & Head", t_score, 6.0,
            self._calc_status(t_score, 6.0), t_msg,
            "Ensure title is descriptive and spans between 30 and 60 characters.",
            {"length": t_len, "value": title_txt}
        ))

        # Meta Description (5 pts)
        m_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        desc_txt = m_desc_tag.get("content", "").strip() if m_desc_tag else ""
        d_len = len(desc_txt)
        if 120 <= d_len <= 160:
            d_score = 5.0
            d_msg = f"Meta description is optimal ({d_len} chars)."
        elif d_len > 0:
            d_score = 2.5
            d_msg = f"Meta description present but length is {d_len} chars (Ideal: 120-160)."
        else:
            d_score = 0.0
            d_msg = "Missing <meta name='description'> tag."
        checks.append(AuditCheck(
            "meta_description", "Meta Description", "Meta & Head", d_score, 5.0,
            self._calc_status(d_score, 5.0), d_msg,
            "Provide a concise meta description between 120 and 160 characters.",
            {"length": d_len, "value": desc_txt}
        ))

        # Viewport (3 pts)
        vp_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        vp_score = 3.0 if (vp_tag and vp_tag.get("content")) else 0.0
        checks.append(AuditCheck(
            "meta_viewport", "Mobile Viewport", "Meta & Head", vp_score, 3.0,
            self._calc_status(vp_score, 3.0),
            "Viewport tag configured." if vp_score else "Viewport meta tag is absent.",
            "Add <meta name='viewport' content='width=device-width, initial-scale=1.0'>."
        ))

        # Charset (2 pts)
        cs_tag = soup.find("meta", attrs={"charset": True}) or soup.find(
            "meta", attrs={"http-equiv": re.compile(r"^content-type$", re.I)}
        )
        cs_score = 2.0 if cs_tag else 0.0
        checks.append(AuditCheck(
            "meta_charset", "Charset Encoding", "Meta & Head", cs_score, 2.0,
            self._calc_status(cs_score, 2.0),
            f"Charset declared: {cs_tag.get('charset', 'custom')}" if cs_tag else "Missing charset definition.",
            "Declare <meta charset='UTF-8'> in the <head>."
        ))

        # Open Graph (2 pts)
        og_t = soup.find("meta", property="og:title")
        og_d = soup.find("meta", property="og:description")
        og_i = soup.find("meta", property="og:image")
        og_cnt = sum(bool(x and x.get("content")) for x in [og_t, og_d, og_i])
        og_score = 2.0 if og_cnt == 3 else (1.0 if og_cnt > 0 else 0.0)
        checks.append(AuditCheck(
            "meta_og", "Open Graph Protocol", "Meta & Head", og_score, 2.0,
            self._calc_status(og_score, 2.0),
            f"Open Graph completion: {og_cnt}/3 tags found.",
            "Add og:title, og:description, and og:image tags for rich social snippets."
        ))

        # Canonical (2 pts)
        can_tag = soup.find("link", rel=re.compile(r"\bcanonical\b", re.I))
        can_score = 2.0 if (can_tag and can_tag.get("href")) else 0.0
        checks.append(AuditCheck(
            "meta_canonical", "Canonical URL", "Meta & Head", can_score, 2.0,
            self._calc_status(can_score, 2.0),
            f"Canonical link defined: {can_tag.get('href')}" if can_score else "Canonical link missing.",
            "Add <link rel='canonical' href='...'> to prevent duplicate content indexing."
        ))

        # =====================================================================
        # 2. Headings (15 pts)
        # =====================================================================
        headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
        h1s = soup.find_all("h1")
        h1_cnt = len(h1s)

        # Single H1 (6 pts)
        if h1_cnt == 1:
            h1_score = 6.0
            h1_msg = "Exactly one <h1> element located."
        elif h1_cnt > 1:
            h1_score = 3.0
            h1_msg = f"Multiple ({h1_cnt}) <h1> elements found."
        else:
            h1_score = 0.0
            h1_msg = "No <h1> element found."
        checks.append(AuditCheck(
            "head_single_h1", "Single H1 Tag", "Headings", h1_score, 6.0,
            self._calc_status(h1_score, 6.0), h1_msg,
            "Ensure exactly one <h1> heading per page."
        ))

        # Skipped Levels (4 pts)
        levels = [int(h.name[1]) for h in headings]
        skipped = False
        for i in range(len(levels) - 1):
            if levels[i + 1] > levels[i] + 1:
                skipped = True
                break
        sk_score = 4.0 if not skipped else 0.0
        checks.append(AuditCheck(
            "head_hierarchy", "Heading Hierarchy", "Headings", sk_score, 4.0,
            self._calc_status(sk_score, 4.0),
            "Heading depth is sequential." if not skipped else "Heading levels skip hierarchically (e.g. H1 to H3).",
            "Maintain logical heading nest levels without jumping depths."
        ))

        # Non-empty headings (3 pts)
        empty_headings = [h for h in headings if not h.get_text().strip()]
        eh_score = 3.0 if (len(empty_headings) == 0 and len(headings) > 0) else (1.5 if len(headings) == 0 else 0.0)
        checks.append(AuditCheck(
            "head_non_empty", "Non-Empty Headings", "Headings", eh_score, 3.0,
            self._calc_status(eh_score, 3.0),
            f"All {len(headings)} headings contain content." if not empty_headings else f"Found {len(empty_headings)} empty heading elements.",
            "Remove or populate empty heading tags."
        ))

        # H1 Length 20-70 chars (2 pts)
        if h1_cnt == 1:
            h1_txt_len = len(h1s[0].get_text().strip())
            h1_l_score = 2.0 if 20 <= h1_txt_len <= 70 else 0.0
            h1_l_msg = f"H1 length is {h1_txt_len} characters."
        else:
            h1_l_score = 0.0
            h1_l_msg = "H1 length cannot be evaluated (absent or duplicate)."
        checks.append(AuditCheck(
            "head_h1_len", "H1 Text Length", "Headings", h1_l_score, 2.0,
            self._calc_status(h1_l_score, 2.0), h1_l_msg,
            "Target H1 length between 20 and 70 characters."
        ))

        # =====================================================================
        # 3. Images (15 pts)
        # =====================================================================
        img_tags = soup.find_all("img")
        tot_imgs = len(img_tags)

        # Alt text coverage (8 pts)
        if tot_imgs == 0:
            alt_score = 8.0
            alt_msg = "No images found on page."
        else:
            valid_alts = sum(1 for img in img_tags if img.get("alt") and img.get("alt").strip())
            alt_ratio = valid_alts / tot_imgs
            alt_score = round(8.0 * alt_ratio, 2)
            alt_msg = f"{valid_alts} of {tot_imgs} ({alt_ratio * 100:.1f}%) images have alt attributes."
        checks.append(AuditCheck(
            "img_alt_coverage", "Alt Text Coverage", "Images", alt_score, 8.0,
            self._calc_status(alt_score, 8.0), alt_msg,
            "Provide descriptive alt text for accessibility and search indexing."
        ))

        # Dimensions (4 pts)
        if tot_imgs == 0:
            dim_score = 4.0
            dim_msg = "No images found on page."
        else:
            dims = sum(1 for img in img_tags if img.get("width") and img.get("height"))
            dim_ratio = dims / tot_imgs
            dim_score = round(4.0 * dim_ratio, 2)
            dim_msg = f"{dims} of {tot_imgs} ({dim_ratio * 100:.1f}%) images have width and height attributes."
        checks.append(AuditCheck(
            "img_dimensions", "Explicit Image Dimensions", "Images", dim_score, 4.0,
            self._calc_status(dim_score, 4.0), dim_msg,
            "Specify width and height attributes to prevent Cumulative Layout Shift (CLS)."
        ))

        # Image File Weight < 1MB (3 pts) — concurrent HEAD checks
        img_srcs = [urljoin(final_url, img["src"]) for img in img_tags if img.get("src")][:10]
        oversized = 0

        def check_img_weight(img_url: str) -> bool:
            try:
                with self.session.head(img_url, timeout=3, allow_redirects=True) as h:
                    cl = h.headers.get("Content-Length")
                    if cl and cl.strip().isdigit() and int(cl) > 1024 * 1024:
                        return True
            except Exception:
                pass
            return False

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(check_img_weight, src) for src in img_srcs]
            for f in as_completed(futures):
                if f.result():
                    oversized += 1

        w_score = 3.0 if oversized == 0 else 0.0
        checks.append(AuditCheck(
            "img_file_weight", "Image File Weight", "Images", w_score, 3.0,
            self._calc_status(w_score, 3.0),
            f"No oversized images detected in sample ({len(img_srcs)} inspected)." if oversized == 0 else f"{oversized} image(s) exceed 1MB threshold.",
            "Compress assets and serve modern formats (WebP, AVIF)."
        ))

        # =====================================================================
        # 4. Links (15 pts)
        # =====================================================================
        anchor_tags = soup.find_all("a", href=True)
        valid_links = []
        for a in anchor_tags:
            h = a["href"].strip()
            if h and not h.startswith(("mailto:", "tel:", "javascript:", "#")):
                valid_links.append(urljoin(final_url, h))

        # Sample up to 15 unique links concurrently (8 pts)
        test_links = list(dict.fromkeys(valid_links))[:15]
        healthy_links = 0

        def verify_link(link: str) -> bool:
            try:
                with self.session.head(link, timeout=4, allow_redirects=True) as res:
                    if res.status_code < 400:
                        return True
                # Fallback to GET for CDN strictness
                with self.session.get(link, timeout=4, stream=True) as res:
                    ok = res.status_code < 400
                return ok
            except Exception:
                return False

        if not test_links:
            lnk_score = 8.0
            lnk_msg = "No outgoing or internal links to test."
        else:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(verify_link, test_links))
                healthy_links = sum(1 for r in results if r)
            lnk_ratio = healthy_links / len(test_links)
            lnk_score = round(8.0 * lnk_ratio, 2)
            lnk_msg = f"{healthy_links} of {len(test_links)} tested links returned healthy status codes."

        checks.append(AuditCheck(
            "link_health", "Broken Link Scan", "Links", lnk_score, 8.0,
            self._calc_status(lnk_score, 8.0), lnk_msg,
            "Repair or eliminate dead links returning 4xx or 5xx codes."
        ))

        # Anchor text quality (4 pts)
        generic_cnt = 0
        tot_anchors = len(anchor_tags)
        for a in anchor_tags:
            txt = a.get_text().strip().lower()
            if not txt or txt in GENERIC_ANCHOR_SET:
                generic_cnt += 1
        gen_ratio = (generic_cnt / tot_anchors) if tot_anchors > 0 else 0.0
        gen_score = 4.0 if gen_ratio < 0.20 else 0.0
        checks.append(AuditCheck(
            "link_anchor_text", "Anchor Text Quality", "Links", gen_score, 4.0,
            self._calc_status(gen_score, 4.0),
            f"Generic anchor density is {gen_ratio * 100:.1f}% (Threshold: <20%).",
            "Use context-rich anchor keywords rather than 'click here' or empty text."
        ))

        # External rel tags (3 pts)
        ext_links = [a for a in anchor_tags if urlparse(urljoin(final_url, a["href"])).netloc != parsed_base.netloc]
        if not ext_links:
            rel_score = 3.0
            rel_msg = "No outbound external links present."
        else:
            rel_safe = sum(1 for a in ext_links if any(x in str(a.get("rel", "")).lower() for x in ["noopener", "nofollow"]))
            rel_ratio = rel_safe / len(ext_links)
            rel_score = round(3.0 * rel_ratio, 2)
            rel_msg = f"{rel_safe} of {len(ext_links)} ({rel_ratio * 100:.1f}%) external links use noopener/nofollow."
        checks.append(AuditCheck(
            "link_external_rel", "External Link Security", "Links", rel_score, 3.0,
            self._calc_status(rel_score, 3.0), rel_msg,
            "Add rel='noopener' or rel='nofollow' to outbound external hyperlinks."
        ))

        # =====================================================================
        # 5. Performance (15 pts)
        # =====================================================================
        # HTML Size (5 pts)
        if doc_size_kb < 100.0:
            doc_score = 5.0
            doc_msg = f"HTML payload is light ({doc_size_kb:.1f} KB < 100 KB)."
        elif doc_size_kb < 300.0:
            doc_score = 3.0
            doc_msg = f"HTML payload is moderate ({doc_size_kb:.1f} KB < 300 KB)."
        else:
            doc_score = 0.0
            doc_msg = f"HTML document size exceeds 300 KB ({doc_size_kb:.1f} KB)."
        checks.append(AuditCheck(
            "perf_html_size", "HTML Document Size", "Performance", doc_score, 5.0,
            self._calc_status(doc_score, 5.0), doc_msg,
            "Minify DOM and keep initial document download below 100 KB."
        ))

        # External scripts <= 8 (4 pts)
        ext_scripts = [s for s in soup.find_all("script") if s.get("src")]
        n_scripts = len(ext_scripts)
        if n_scripts <= 8:
            sc_score = 4.0
        else:
            sc_score = round(4.0 * max(0.0, 1.0 - ((n_scripts - 8) / 16.0)), 2)
        checks.append(AuditCheck(
            "perf_external_scripts", "External Script Count", "Performance", sc_score, 4.0,
            self._calc_status(sc_score, 4.0),
            f"Found {n_scripts} external script files.",
            "Consolidate scripts or defer loading to reduce render-blocking execution."
        ))

        # External stylesheets <= 4 (3 pts)
        ext_css = [l for l in soup.find_all("link", rel=re.compile(r"\bstylesheet\b", re.I)) if l.get("href")]
        n_css = len(ext_css)
        if n_css <= 4:
            css_score = 3.0
        else:
            css_score = round(3.0 * max(0.0, 1.0 - ((n_css - 4) / 8.0)), 2)
        checks.append(AuditCheck(
            "perf_external_css", "External Stylesheet Count", "Performance", css_score, 3.0,
            self._calc_status(css_score, 3.0),
            f"Found {n_css} external stylesheet references.",
            "Bundle CSS bundles and inline above-the-fold critical CSS."
        ))

        # Compression (3 pts)
        encoding = resp.headers.get("Content-Encoding", "").lower()
        comp_score = 3.0 if any(c in encoding for c in ["gzip", "br", "deflate", "zstd"]) else 0.0
        checks.append(AuditCheck(
            "perf_compression", "Server Compression", "Performance", comp_score, 3.0,
            self._calc_status(comp_score, 3.0),
            f"Active compression: '{encoding}'" if comp_score else "No HTTP compression detected.",
            "Enable Brotli or Gzip on reverse proxies or web servers."
        ))

        # =====================================================================
        # 6. Security (10 pts)
        # =====================================================================
        # HTTPS (6 pts)
        is_https = parsed_base.scheme == "https"
        https_score = 6.0 if is_https else 0.0
        checks.append(AuditCheck(
            "sec_https", "HTTPS Transport Security", "Security", https_score, 6.0,
            self._calc_status(https_score, 6.0),
            "Served securely over HTTPS." if is_https else "Site is served insecurely over plain HTTP.",
            "Enforce full-site HTTPS encryption via modern SSL/TLS certificates."
        ))

        # Mixed Content (4 pts)
        if not is_https:
            mix_score = 0.0
            mix_msg = "Cannot assess mixed content on non-HTTPS origin."
        else:
            insecure_items = []
            for tag, attr in [("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src")]:
                for elem in soup.find_all(tag):
                    v = elem.get(attr, "")
                    if v.startswith("http://"):
                        insecure_items.append(v)
            mix_score = 4.0 if len(insecure_items) == 0 else 0.0
            mix_msg = "No mixed HTTP assets detected." if mix_score else f"Found {len(insecure_items)} mixed insecure assets."
        checks.append(AuditCheck(
            "sec_mixed_content", "Mixed Content Evaluation", "Security", mix_score, 4.0,
            self._calc_status(mix_score, 4.0), mix_msg,
            "Replace all absolute HTTP asset URLs with HTTPS links."
        ))

        # =====================================================================
        # 7. Content (10 pts)
        # =====================================================================
        body = soup.find("body")
        raw_text = body.get_text(separator=" ", strip=True) if body else ""
        words = re.findall(r"\b\w+\b", raw_text)
        word_count = len(words)

        # Word count >= 300 (5 pts)
        if word_count >= 300:
            wc_score = 5.0
            wc_msg = f"Content volume is sufficient ({word_count} words)."
        elif word_count >= 100:
            wc_score = 2.5
            wc_msg = f"Thin content detected ({word_count} words; Target: 300+)."
        else:
            wc_score = 0.0
            wc_msg = f"Extremely thin text content ({word_count} words)."
        checks.append(AuditCheck(
            "cnt_word_volume", "Text Volume", "Content", wc_score, 5.0,
            self._calc_status(wc_score, 5.0), wc_msg,
            "Provide at least 300 words of comprehensive, original content."
        ))

        # H2 Subheadings (3 pts)
        h2_cnt = len(soup.find_all("h2"))
        h2_score = 3.0 if h2_cnt >= 1 else 0.0
        checks.append(AuditCheck(
            "cnt_h2_structure", "H2 Subheading Structure", "Content", h2_score, 3.0,
            self._calc_status(h2_score, 3.0),
            f"Found {h2_cnt} H2 subheadings organizing the page." if h2_score else "No H2 subheadings detected.",
            "Structure body copy logically using H2 section subheadings."
        ))

        # Readability proxy (2 pts)
        sentences = [s.strip() for s in re.split(r"[.!?]+", raw_text) if len(s.strip()) > 3]
        avg_sent = (word_count / len(sentences)) if sentences else (float(word_count) if word_count else 0.0)
        read_score = 2.0 if avg_sent < 25.0 else 0.0
        checks.append(AuditCheck(
            "cnt_readability", "Sentence Readability", "Content", read_score, 2.0,
            self._calc_status(read_score, 2.0),
            f"Average sentence length is {avg_sent:.1f} words (Target: < 25)." if avg_sent else "Insufficient text.",
            "Shorten lengthy sentences to keep average length under 25 words."
        ))

        # Aggregation
        categories = ["Meta & Head", "Headings", "Images", "Links", "Performance", "Security", "Content"]
        cat_scores: Dict[str, Dict[str, float]] = {}
        total_earned = 0.0

        for cat in categories:
            cat_c = [c for c in checks if c.category == cat]
            c_earned = sum(c.earned for c in cat_c)
            c_max = sum(c.maximum for c in cat_c)
            cat_scores[cat] = {
                "earned": round(c_earned, 2),
                "max": round(c_max, 2),
                "pct": round((c_earned / c_max) * 100 if c_max > 0 else 0.0, 1),
            }
            total_earned += c_earned

        final_score = min(100.0, max(0.0, round(total_earned, 1)))

        return AuditReport(
            target_url=target_url,
            final_url=final_url,
            status_code=resp.status_code,
            response_time=round(time.time() - t_start, 2),
            total_score=final_score,
            letter_grade=self._calc_grade(final_score),
            category_scores=cat_scores,
            checks=checks,
            metrics={
                "html_kb": round(doc_size_kb, 1),
                "word_count": word_count,
                "images_total": tot_imgs,
                "links_total": tot_anchors,
                "scripts_ext": n_scripts,
                "styles_ext": n_css,
                "encoding": encoding or "None",
            },
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
