"""
RankPilot: Data-Driven SEO and Technical Website Auditor.
A single-file Streamlit application with a deterministic scoring engine.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# Configuration and Constants
# -----------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 RankPilot/1.0"
)
REQUEST_TIMEOUT = 10
LINK_CHECK_TIMEOUT = 5
MAX_LINKS_TO_CHECK = 15
MAX_IMAGES_TO_CHECK = 10

GENERIC_ANCHOR_TEXTS = {
    "click here",
    "click",
    "read more",
    "learn more",
    "more",
    "link",
    "here",
    "this",
    "website",
    "view more",
    "continue",
}

# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------
@dataclass
class AuditCheck:
    name: str
    category: str
    earned: float
    maximum: float
    status: str  # "pass", "warn", "fail"
    finding: str
    recommendation: str

@dataclass
class AuditReport:
    url: str
    status_code: int
    response_time: float
    total_score: float
    letter_grade: str
    category_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    checks: List[AuditCheck] = field(default_factory=list)
    raw_stats: Dict[str, any] = field(default_factory=dict)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_status(earned: float, maximum: float) -> str:
    """Calculate pass, warn, or fail status based on percentage."""
    if maximum <= 0:
        return "pass"
    ratio = earned / maximum
    if ratio >= 0.80:
        return "pass"
    if ratio >= 0.40:
        return "warn"
    return "fail"

def calculate_letter_grade(score: float) -> str:
    """Map numeric score (0-100) to standard letter grade."""
    if score >= 90.0:
        return "A"
    if score >= 80.0:
        return "B"
    if score >= 70.0:
        return "C"
    if score >= 60.0:
        return "D"
    return "F"

def normalize_url(url: str) -> str:
    """Ensure URL includes valid scheme."""
    cleaned = url.strip()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    return cleaned

def fetch_page(url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
    """Fetch target web page with desktop user agent."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        return response, None
    except requests.exceptions.SSLError as exc:
        return None, f"SSL/TLS Certificate verification failed: {exc}"
    except requests.exceptions.Timeout:
        return None, f"Connection timed out after {REQUEST_TIMEOUT} seconds."
    except requests.exceptions.ConnectionError:
        return None, "Connection failed. Please check the domain name and network."
    except requests.exceptions.RequestException as exc:
        return None, f"HTTP request failed: {exc}"

# -----------------------------------------------------------------------------
# Core Scoring Engine
# -----------------------------------------------------------------------------
def run_audit(url: str, response: requests.Response) -> AuditReport:
    """Execute complete deterministic audit across 7 categories."""
    soup = BeautifulSoup(response.text, "lxml")
    checks: List[AuditCheck] = []
    base_url = response.url
    parsed_base = urlparse(base_url)

    # -------------------------------------------------------------------------
    # 1. Meta & Head (20 pts)
    # -------------------------------------------------------------------------
    # Title (6 pts)
    title_tag = soup.find("title")
    title_text = title_tag.get_text().strip() if title_tag else ""
    title_len = len(title_text)
    if 30 <= title_len <= 60:
        t_pts = 6.0
        t_find = f"Page title is present and optimal length ({title_len} chars): '{title_text}'"
        t_rec = "Keep title within 30-60 characters."
    elif title_len > 0:
        t_pts = 3.0
        t_find = f"Page title is present but off-length ({title_len} chars): '{title_text}'"
        t_rec = "Adjust title length to 30-60 characters for best SERP appearance."
    else:
        t_pts = 0.0
        t_find = "No <title> tag found on page."
        t_rec = "Add a descriptive <title> tag between 30 and 60 characters."
    checks.append(AuditCheck("Page Title", "Meta & Head", t_pts, 6.0, get_status(t_pts, 6.0), t_find, t_rec))

    # Meta Description (5 pts)
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    desc_len = len(meta_desc)
    if 120 <= desc_len <= 160:
        d_pts = 5.0
        d_find = f"Meta description is present and optimal length ({desc_len} chars)."
        d_rec = "Maintain meta description between 120 and 160 characters."
    elif desc_len > 0:
        d_pts = 2.5
        d_find = f"Meta description present but off-length ({desc_len} chars)."
        d_rec = "Rewrite meta description to fit 120-160 characters."
    else:
        d_pts = 0.0
        d_find = "Meta description is missing."
        d_rec = "Add a <meta name='description'> tag with 120-160 characters."
    checks.append(AuditCheck("Meta Description", "Meta & Head", d_pts, 5.0, get_status(d_pts, 5.0), d_find, d_rec))

    # Viewport Meta (3 pts)
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    v_pts = 3.0 if viewport and viewport.get("content") else 0.0
    v_find = "Viewport meta tag declared." if v_pts == 3.0 else "Viewport meta tag missing."
    v_rec = "Keep viewport configured." if v_pts == 3.0 else "Add <meta name='viewport' content='width=device-width, initial-scale=1.0'>."
    checks.append(AuditCheck("Viewport Configuration", "Meta & Head", v_pts, 3.0, get_status(v_pts, 3.0), v_find, v_rec))

    # Charset Declared (2 pts)
    charset_meta = soup.find("meta", attrs={"charset": True}) or soup.find(
        "meta", attrs={"http-equiv": re.compile(r"^content-type$", re.I)}
    )
    c_pts = 2.0 if charset_meta else 0.0
    c_find = f"Character encoding declared: {charset_meta.get('charset', 'content-type')}" if charset_meta else "Charset is not explicitly declared."
    c_rec = "Keep charset declared." if c_pts == 2.0 else "Declare character set using <meta charset='UTF-8'>."
    checks.append(AuditCheck("Charset Declaration", "Meta & Head", c_pts, 2.0, get_status(c_pts, 2.0), c_find, c_rec))

    # Open Graph Tags (2 pts)
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_img = soup.find("meta", property="og:image")
    og_count = sum(bool(x and x.get("content")) for x in [og_title, og_desc, og_img])
    if og_count == 3:
        og_pts = 2.0
        og_find = "All essential Open Graph tags present (title, description, image)."
    elif og_count > 0:
        og_pts = 1.0
        og_find = f"Open Graph tags incomplete ({og_count}/3 found)."
    else:
        og_pts = 0.0
        og_find = "No essential Open Graph tags found."
    og_rec = "Provide complete og:title, og:description, and og:image metadata for social previews."
    checks.append(AuditCheck("Open Graph Meta", "Meta & Head", og_pts, 2.0, get_status(og_pts, 2.0), og_find, og_rec))

    # Canonical Link (2 pts)
    canonical = soup.find("link", rel=re.compile(r"\bcanonical\b", re.I))
    can_pts = 2.0 if canonical and canonical.get("href") else 0.0
    can_find = f"Canonical link found: {canonical.get('href')}" if can_pts == 2.0 else "Canonical link missing."
    can_rec = "Keep canonical links to prevent duplicate content issues." if can_pts == 2.0 else "Add <link rel='canonical' href='...'>."
    checks.append(AuditCheck("Canonical Link", "Meta & Head", can_pts, 2.0, get_status(can_pts, 2.0), can_find, can_rec))

    # -------------------------------------------------------------------------
    # 2. Headings (15 pts)
    # -------------------------------------------------------------------------
    all_headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
    h1_tags = soup.find_all("h1")

    # Exactly one H1 (6 pts)
    h1_count = len(h1_tags)
    if h1_count == 1:
        h1_pts = 6.0
        h1_find = "Page contains exactly one <h1> tag."
    elif h1_count > 1:
        h1_pts = 3.0
        h1_find = f"Page contains {h1_count} <h1> tags."
    else:
        h1_pts = 0.0
        h1_find = "Page has no <h1> tag."
    h1_rec = "Ensure each page has exactly one top-level <h1>."
    checks.append(AuditCheck("Single H1 Structure", "Headings", h1_pts, 6.0, get_status(h1_pts, 6.0), h1_find, h1_rec))

    # Skipped heading levels (4 pts)
    heading_levels = [int(h.name[1]) for h in all_headings]
    skipped_levels = False
    for i in range(len(heading_levels) - 1):
        if heading_levels[i + 1] > heading_levels[i] + 1:
            skipped_levels = True
            break
    skip_pts = 4.0 if (not skipped_levels) else 0.0
    skip_find = "Heading hierarchy is sequential with no skipped levels." if not skipped_levels else "Heading levels skip hierarchically (e.g., H1 followed directly by H3)."
    skip_rec = "Nest heading tags logically (H1 -> H2 -> H3) without jumping levels."
    checks.append(AuditCheck("Heading Hierarchy", "Headings", skip_pts, 4.0, get_status(skip_pts, 4.0), skip_find, skip_rec))

    # Non-empty headings (3 pts)
    empty_headings = [h for h in all_headings if not h.get_text().strip()]
    empty_pts = 3.0 if (len(empty_headings) == 0 and len(all_headings) > 0) else (0.0 if empty_headings else 1.5)
    empty_find = f"All {len(all_headings)} headings contain text." if not empty_headings else f"Found {len(empty_headings)} empty heading tags."
    empty_rec = "Ensure all heading tags contain clear, descriptive text."
    checks.append(AuditCheck("Non-Empty Headings", "Headings", empty_pts, 3.0, get_status(empty_pts, 3.0), empty_find, empty_rec))

    # H1 Length 20-70 chars (2 pts)
    if h1_count == 1:
        h1_len = len(h1_tags[0].get_text().strip())
        h1_len_pts = 2.0 if 20 <= h1_len <= 70 else 0.0
        h1_len_find = f"H1 length is {h1_len} characters."
    else:
        h1_len_pts = 0.0
        h1_len_find = f"Cannot validate H1 length (found {h1_count} H1 tags)."
    h1_len_rec = "Aim for an H1 length between 20 and 70 characters."
    checks.append(AuditCheck("H1 Text Length", "Headings", h1_len_pts, 2.0, get_status(h1_len_pts, 2.0), h1_len_find, h1_len_rec))

    # -------------------------------------------------------------------------
    # 3. Images (15 pts)
    # -------------------------------------------------------------------------
    images = soup.find_all("img")
    total_imgs = len(images)

    # Alt-text coverage (8 pts)
    if total_imgs == 0:
        alt_pts = 8.0
        alt_find = "No images found on page."
    else:
        valid_alts = sum(1 for img in images if img.get("alt") and img.get("alt").strip())
        alt_ratio = valid_alts / total_imgs
        alt_pts = round(8.0 * alt_ratio, 2)
        alt_find = f"{valid_alts} of {total_imgs} images ({alt_ratio * 100:.1f}%) have non-empty alt text."
    alt_rec = "Add descriptive alt attributes to all informational images."
    checks.append(AuditCheck("Alt Text Coverage", "Images", alt_pts, 8.0, get_status(alt_pts, 8.0), alt_find, alt_rec))

    # Dimension attributes (4 pts)
    if total_imgs == 0:
        dim_pts = 4.0
        dim_find = "No images found on page."
    else:
        with_dim = sum(1 for img in images if img.get("width") and img.get("height"))
        dim_ratio = with_dim / total_imgs
        dim_pts = round(4.0 * dim_ratio, 2)
        dim_find = f"{with_dim} of {total_imgs} images ({dim_ratio * 100:.1f}%) specify width and height."
    dim_rec = "Set explicit width and height attributes to reduce layout shifts (CLS)."
    checks.append(AuditCheck("Image Dimensions", "Images", dim_pts, 4.0, get_status(dim_pts, 4.0), dim_find, dim_rec))

    # Image file sizes under 1MB (3 pts)
    sampled_images = images[:MAX_IMAGES_TO_CHECK]
    oversized_images = 0
    checked_sizes = 0
    for img in sampled_images:
        src = img.get("src")
        if not src:
            continue
        full_img_url = urljoin(base_url, src)
        try:
            h_resp = requests.head(full_img_url, timeout=3, allow_redirects=True)
            cl = h_resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                checked_sizes += 1
                if int(cl) > 1024 * 1024:
                    oversized_images += 1
        except Exception:
            continue

    if oversized_images == 0:
        size_pts = 3.0
        size_find = f"No images over 1MB detected (sampled {len(sampled_images)} images)."
    else:
        size_pts = 0.0
        size_find = f"Found {oversized_images} image(s) exceeding 1MB in sample."
    size_rec = "Compress images and serve modern formats (WebP, AVIF) to keep under 1MB."
    checks.append(AuditCheck("Image File Weight", "Images", size_pts, 3.0, get_status(size_pts, 3.0), size_find, size_rec))

    # -------------------------------------------------------------------------
    # 4. Links (15 pts)
    # -------------------------------------------------------------------------
    links = soup.find_all("a", href=True)
    clean_links: List[str] = []
    for l in links:
        href = l.get("href", "").strip()
        if href and not href.startswith(("mailto:", "tel:", "javascript:", "#")):
            clean_links.append(urljoin(base_url, href))

    # Broken link scan (8 pts)
    test_links = list(dict.fromkeys(clean_links))[:MAX_LINKS_TO_CHECK]
    healthy_links = 0
    for target in test_links:
        try:
            head_res = requests.head(
                target,
                headers={"User-Agent": USER_AGENT},
                timeout=LINK_CHECK_TIMEOUT,
                allow_redirects=True,
            )
            # Accept any 2xx or 3xx status
            if head_res.status_code < 400:
                healthy_links += 1
            else:
                # Retry with GET in case HEAD was blocked by CDN
                get_res = requests.get(
                    target,
                    headers={"User-Agent": USER_AGENT},
                    timeout=LINK_CHECK_TIMEOUT,
                    stream=True,
                )
                if get_res.status_code < 400:
                    healthy_links += 1
                get_res.close()
        except Exception:
            pass

    if len(test_links) == 0:
        broken_pts = 8.0
        broken_find = "No external or internal links found to test."
    else:
        health_ratio = healthy_links / len(test_links)
        broken_pts = round(8.0 * health_ratio, 2)
        broken_find = f"Link sample health: {healthy_links}/{len(test_links)} reachable (tested {len(test_links)} links)."
    broken_rec = "Fix or remove any broken links that return 4xx or 5xx status codes."
    checks.append(AuditCheck("Broken Link Scan", "Links", broken_pts, 8.0, get_status(broken_pts, 8.0), broken_find, broken_rec))

    # Anchor text quality (4 pts)
    generic_count = 0
    total_valid_anchors = len(links)
    for a in links:
        text = a.get_text().strip().lower()
        if not text or text in GENERIC_ANCHOR_TEXTS:
            generic_count += 1

    generic_ratio = (generic_count / total_valid_anchors) if total_valid_anchors > 0 else 0.0
    if generic_ratio < 0.20:
        anchor_pts = 4.0
        anchor_find = f"Anchor text quality is strong ({generic_ratio * 100:.1f}% generic anchors)."
    else:
        anchor_pts = 0.0
        anchor_find = f"{generic_ratio * 100:.1f}% of link anchors are generic or empty."
    anchor_rec = "Use informative anchor texts instead of 'click here', 'read more', or empty icons."
    checks.append(AuditCheck("Anchor Text Quality", "Links", anchor_pts, 4.0, get_status(anchor_pts, 4.0), anchor_find, anchor_rec))

    # External links rel attributes (3 pts)
    external_links = [l for l in links if urlparse(urljoin(base_url, l.get("href", ""))).netloc != parsed_base.netloc]
    if len(external_links) == 0:
        ext_pts = 3.0
        ext_find = "No external links on page."
    else:
        secure_ext = 0
        for l in external_links:
            rel = (l.get("rel") or [])
            rel_str = " ".join(rel) if isinstance(rel, list) else str(rel)
            if "noopener" in rel_str or "nofollow" in rel_str:
                secure_ext += 1
        ext_ratio = secure_ext / len(external_links)
        ext_pts = round(3.0 * ext_ratio, 2)
        ext_find = f"{secure_ext} of {len(external_links)} ({ext_ratio * 100:.1f}%) external links use noopener or nofollow."
    ext_rec = "Add rel='noopener' or rel='nofollow' to all outgoing third-party links."
    checks.append(AuditCheck("External Link Security", "Links", ext_pts, 3.0, get_status(ext_pts, 3.0), ext_find, ext_rec))

    # -------------------------------------------------------------------------
    # 5. Performance (15 pts)
    # -------------------------------------------------------------------------
    # HTML Document size (5 pts)
    doc_size_kb = len(response.content) / 1024.0
    if doc_size_kb < 100.0:
        doc_pts = 5.0
        doc_find = f"HTML document size is optimal ({doc_size_kb:.1f} KB < 100 KB)."
    elif doc_size_kb < 300.0:
        doc_pts = 3.0
        doc_find = f"HTML document size is acceptable ({doc_size_kb:.1f} KB < 300 KB)."
    else:
        doc_pts = 0.0
        doc_find = f"HTML document size is heavy ({doc_size_kb:.1f} KB >= 300 KB)."
    doc_rec = "Keep base HTML size under 100KB through minification and lazy loading."
    checks.append(AuditCheck("HTML Document Size", "Performance", doc_pts, 5.0, get_status(doc_pts, 5.0), doc_find, doc_rec))

    # External scripts (4 pts)
    ext_scripts = [s for s in soup.find_all("script") if s.get("src")]
    script_count = len(ext_scripts)
    if script_count <= 8:
        script_pts = 4.0
    else:
        scale = max(0.0, 1.0 - ((script_count - 8) / 16.0))
        script_pts = round(4.0 * scale, 2)
    script_find = f"Found {script_count} external script files."
    script_rec = "Bundle or defer external scripts to keep total script tags below 8."
    checks.append(AuditCheck("External Scripts", "Performance", script_pts, 4.0, get_status(script_pts, 4.0), script_find, script_rec))

    # External stylesheets (3 pts)
    ext_styles = [link for link in soup.find_all("link", rel=re.compile(r"\bstylesheet\b", re.I)) if link.get("href")]
    style_count = len(ext_styles)
    if style_count <= 4:
        style_pts = 3.0
    else:
        scale = max(0.0, 1.0 - ((style_count - 4) / 8.0))
        style_pts = round(3.0 * scale, 2)
    style_find = f"Found {style_count} external stylesheet files."
    style_rec = "Combine CSS stylesheets and inline critical styles to stay at or below 4 files."
    checks.append(AuditCheck("External Stylesheets", "Performance", style_pts, 3.0, get_status(style_pts, 3.0), style_find, style_rec))

    # HTTP Compression (3 pts)
    encoding = response.headers.get("Content-Encoding", "").lower()
    comp_pts = 3.0 if any(enc in encoding for enc in ["gzip", "br", "deflate", "zstd"]) else 0.0
    comp_find = f"Compression detected ({encoding})." if comp_pts == 3.0 else "No HTTP compression header detected."
    comp_rec = "Enable gzip or Brotli compression on your web server or CDN."
    checks.append(AuditCheck("Server Compression", "Performance", comp_pts, 3.0, get_status(comp_pts, 3.0), comp_find, comp_rec))

    # -------------------------------------------------------------------------
    # 6. Security (10 pts)
    # -------------------------------------------------------------------------
    # Served over HTTPS (6 pts)
    is_https = parsed_base.scheme == "https"
    https_pts = 6.0 if is_https else 0.0
    https_find = "Page is served over HTTPS." if is_https else "Page is not served over HTTPS."
    https_rec = "Install an SSL/TLS certificate and force redirect to HTTPS."
    checks.append(AuditCheck("HTTPS Protocol", "Security", https_pts, 6.0, get_status(https_pts, 6.0), https_find, https_rec))

    # Mixed Content (4 pts)
    if not is_https:
        mixed_pts = 0.0
        mixed_find = "Site is HTTP; secure context cannot be verified."
    else:
        insecure_res = []
        for tag, attr in [("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src")]:
            for elem in soup.find_all(tag):
                res_url = elem.get(attr, "")
                if res_url.startswith("http://"):
                    insecure_res.append(res_url)
        if len(insecure_res) == 0:
            mixed_pts = 4.0
            mixed_find = "No mixed HTTP resources found on HTTPS page."
        else:
            mixed_pts = 0.0
            mixed_find = f"Detected {len(insecure_res)} insecure HTTP resources on HTTPS page."
    mixed_rec = "Update all resource URLs to use HTTPS or protocol-relative paths."
    checks.append(AuditCheck("Mixed Content Scan", "Security", mixed_pts, 4.0, get_status(mixed_pts, 4.0), mixed_find, mixed_rec))

    # -------------------------------------------------------------------------
    # 7. Content (10 pts)
    # -------------------------------------------------------------------------
    body = soup.find("body")
    text_content = body.get_text(separator=" ", strip=True) if body else ""
    words = re.findall(r"\b\w+\b", text_content)
    word_count = len(words)

    # Word count >= 300 (5 pts)
    if word_count >= 300:
        wc_pts = 5.0
        wc_find = f"Substantial content length detected ({word_count} words)."
    elif word_count >= 100:
        wc_pts = 2.5
        wc_find = f"Thin content detected ({word_count} words; target is 300+)."
    else:
        wc_pts = 0.0
        wc_find = f"Extremely low text content ({word_count} words)."
    wc_rec = "Provide at least 300 words of informative, relevant copy."
    checks.append(AuditCheck("Text Content Volume", "Content", wc_pts, 5.0, get_status(wc_pts, 5.0), wc_find, wc_rec))

    # Uses H2 subheadings for structure (3 pts)
    h2_tags = soup.find_all("h2")
    h2_pts = 3.0 if len(h2_tags) >= 1 else 0.0
    h2_find = f"Found {len(h2_tags)} H2 subheading(s) structuring content." if h2_pts == 3.0 else "No H2 subheadings found."
    h2_rec = "Break up long copy into logical sections using H2 headings."
    checks.append(AuditCheck("H2 Structural Subheadings", "Content", h2_pts, 3.0, get_status(h2_pts, 3.0), h2_find, h2_rec))

    # Readability proxy - average sentence length < 25 words (2 pts)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text_content) if len(s.strip()) > 3]
    if len(sentences) > 0:
        avg_sentence_len = word_count / len(sentences)
        read_pts = 2.0 if avg_sentence_len < 25.0 else 0.0
        read_find = f"Average sentence length is {avg_sentence_len:.1f} words."
    else:
        avg_sentence_len = 0.0
        read_pts = 2.0 if word_count < 25 else 0.0
        read_find = "Insufficient text structure to measure sentence distribution."
    read_rec = "Keep sentences concise (under 25 words per sentence) for better readability."
    checks.append(AuditCheck("Sentence Readability", "Content", read_pts, 2.0, get_status(read_pts, 2.0), read_find, read_rec))

    # -------------------------------------------------------------------------
    # Aggregate Category Scores and Final Tally
    # -------------------------------------------------------------------------
    categories = ["Meta & Head", "Headings", "Images", "Links", "Performance", "Security", "Content"]
    cat_summary = {}
    total_score = 0.0

    for cat in categories:
        cat_checks = [c for c in checks if c.category == cat]
        cat_earned = sum(c.earned for c in cat_checks)
        cat_max = sum(c.maximum for c in cat_checks)
        cat_summary[cat] = {
            "earned": round(cat_earned, 2),
            "max": round(cat_max, 2),
            "pct": round((cat_earned / cat_max) * 100 if cat_max > 0 else 0.0, 1),
        }
        total_score += cat_earned

    total_score = min(100.0, max(0.0, round(total_score, 1)))
    letter = calculate_letter_grade(total_score)

    raw_stats = {
        "html_size_kb": round(doc_size_kb, 1),
        "total_images": total_imgs,
        "total_links": len(links),
        "total_headings": len(all_headings),
        "word_count": word_count,
        "avg_sentence_words": round(avg_sentence_len, 1),
        "external_scripts": script_count,
        "external_styles": style_count,
        "encoding": encoding or "none",
    }

    return AuditReport(
        url=base_url,
        status_code=response.status_code,
        response_time=response.elapsed.total_seconds(),
        total_score=total_score,
        letter_grade=letter,
        category_scores=cat_summary,
        checks=checks,
        raw_stats=raw_stats,
    )

# -----------------------------------------------------------------------------
# Markdown Report Builder
# -----------------------------------------------------------------------------
def build_markdown_report(rep: AuditReport) -> str:
    """Render the full audit as a downloadable Markdown document."""
    status_icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    lines = [
        "# 🔍 RankPilot Audit Report",
        "",
        f"- **URL:** {rep.url}",
        f"- **Date:** {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
        f"- **Score:** {rep.total_score:.1f}/100 (Grade {rep.letter_grade})",
        f"- **HTTP:** {rep.status_code} in {rep.response_time:.2f}s",
        "",
        "## Category scores",
        "",
        "| Category | Score | % |",
        "|---|---|---|",
    ]
    for cat, data in rep.category_scores.items():
        lines.append(f"| {cat} | {data['earned']}/{data['max']} | {data['pct']}% |")
    lines += ["", "## All checks", ""]
    for c in rep.checks:
        lines += [
            f"### {status_icon.get(c.status, '')} {c.name} ({c.category}) — {c.earned}/{c.maximum} pts",
            f"- Finding: {c.finding}",
            f"- Fix: {c.recommendation}",
            "",
        ]
    lines += ["## Priority fixes", ""]
    priority = [c for c in rep.checks if c.status in ("fail", "warn")]
    priority.sort(key=lambda x: (0 if x.status == "fail" else 1, -(x.maximum - x.earned)))
    for i, c in enumerate(priority, 1):
        lines.append(f"{i}. **{c.name}** ({c.category}): {c.recommendation}")
    lines += ["", "---", "RankPilot — data-driven SEO audits."]
    return "\n".join(lines)

# -----------------------------------------------------------------------------
# Streamlit User Interface
# -----------------------------------------------------------------------------
def render_badge(status: str) -> str:
    color_map = {
        "pass": ("#10b981", "#ecfdf5", "PASS"),
        "warn": ("#f59e0b", "#fffbeb", "WARN"),
        "fail": ("#ef4444", "#fef2f2", "FAIL"),
    }
    border, bg, text = color_map.get(status, ("#6b7280", "#f9fafb", status.upper()))
    return f"""
    <span style="
        background-color: {bg};
        color: {border};
        border: 1px solid {border};
        padding: 2px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.75rem;
        display: inline-block;
    ">{text}</span>
    """

def main():
    st.set_page_config(
        page_title="RankPilot — SEO & Technical Website Auditor",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom styling
    st.markdown(
        """
        <style>
        .metric-card {
            background-color: #0e1117;
            border: 1px solid #262730;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }
        .grade-pill {
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
            margin: 10px 0;
        }
        .grade-A { color: #10b981; }
        .grade-B { color: #3b82f6; }
        .grade-C { color: #f59e0b; }
        .grade-D { color: #f97316; }
        .grade-F { color: #ef4444; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🧭 RankPilot")
    st.caption("Data-Driven SEO & Technical Website Auditor • 100% Deterministic • Zero External APIs")

    # Sidebar
    with st.sidebar:
        st.header("Audit Controls")
        input_url = st.text_input("Target URL", value="https://example.com", placeholder="https://yourdomain.com")
        run_btn = st.button("Run Audit", type="primary", use_container_width=True)

        st.markdown("---")
        st.subheader("Auditing Rules")
        st.markdown(
            """
            - **Weights**: Sum to 100 points
            - **Pass**: Score ≥ 80%
            - **Warn**: 40% ≤ Score < 80%
            - **Fail**: Score < 40%
            - **Grades**: A (90+), B (80+), C (70+), D (60+), F (<60)
            """
        )

    if run_btn:
        valid_url = normalize_url(input_url)
        with st.spinner(f"Fetching and analyzing {valid_url}..."):
            t0 = time.time()
            response, err_msg = fetch_page(valid_url)

            if err_msg:
                st.error(f"Audit could not proceed: {err_msg}")
                return

            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                st.error(
                    "Audit could not proceed: the URL did not return HTML content "
                    f"(Content-Type: {content_type or 'unknown'})."
                )
                return

            report = run_audit(valid_url, response)
            st.session_state["report"] = report

    if "report" in st.session_state:
        rep: AuditReport = st.session_state["report"]

        # Hero Metric Overview
        col1, col2, col3, col4, col5 = st.columns([1.5, 1.2, 1.2, 1.2, 1.5])

        with col1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div style="font-size: 0.85rem; color: #9ca3af;">Overall Score</div>
                    <div class="grade-pill grade-{rep.letter_grade}">{rep.total_score:.1f}</div>
                    <div style="font-size: 0.9rem; font-weight: 600;">Grade: {rep.letter_grade}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        pass_count = sum(1 for c in rep.checks if c.status == "pass")
        warn_count = sum(1 for c in rep.checks if c.status == "warn")
        fail_count = sum(1 for c in rep.checks if c.status == "fail")

        with col2:
            st.metric("Passed Checks", f"{pass_count}", delta=f"{pass_count}/{len(rep.checks)}")
        with col3:
            st.metric("Warnings", f"{warn_count}")
        with col4:
            st.metric("Failed Checks", f"{fail_count}")
        with col5:
            st.metric("Response Time", f"{rep.response_time:.2f}s", f"HTTP {rep.status_code}")

        st.markdown("---")

        # Tabs for categorized views
        tab_cats, tab_fixes, tab_all, tab_meta = st.tabs(
            ["📊 Category Scores", "🚨 Prioritized Fix List", "🔍 All Checks Details", "📈 Technical Metrics"]
        )

        # Tab 1: Category Scores
        with tab_cats:
            st.subheader("Sub-Score Performance Breakdown")
            c_cols = st.columns(len(rep.category_scores))
            for idx, (cat_name, data) in enumerate(rep.category_scores.items()):
                with c_cols[idx]:
                    st.metric(
                        label=cat_name,
                        value=f"{data['earned']}/{data['max']}",
                        delta=f"{data['pct']}%",
                    )
                    st.progress(data["pct"] / 100.0)

            st.write("")
            st.markdown("#### Category Summaries")
            for cat_name, data in rep.category_scores.items():
                with st.expander(f"{cat_name} — {data['earned']} / {data['max']} pts ({data['pct']}%)"):
                    cat_items = [c for c in rep.checks if c.category == cat_name]
                    for item in cat_items:
                        st.markdown(
                            f"**{item.name}** {render_badge(item.status)} — `{item.earned} / {item.maximum} pts`",
                            unsafe_allow_html=True,
                        )
                        st.write(f"- **Finding**: {item.finding}")
                        st.write(f"- **Recommendation**: {item.recommendation}")
                        st.write("")

        # Tab 2: Prioritized Fix List
        with tab_fixes:
            st.subheader("Action Plan: Prioritized Technical Fixes")
            st.caption("Ordered by issue severity: Fails first, followed by Warnings.")

            priority_checks = [c for c in rep.checks if c.status in ("fail", "warn")]
            priority_checks.sort(key=lambda x: (0 if x.status == "fail" else 1, -(x.maximum - x.earned)))

            if not priority_checks:
                st.success("🎉 Outstanding! No critical issues or warnings detected on this page.")
            else:
                for idx, issue in enumerate(priority_checks, 1):
                    loss = issue.maximum - issue.earned
                    badge = render_badge(issue.status)
                    st.markdown(
                        f"""
                        <div style="border-left: 4px solid {'#ef4444' if issue.status == 'fail' else '#f59e0b'}; padding-left: 12px; margin-bottom: 14px;">
                            <strong>#{idx} {issue.name}</strong> ({issue.category}) {badge}
                            <span style="color: #9ca3af; font-size: 0.85rem; margin-left: 8px;">Score deficit: -{loss:.1f} pts</span>
                            <br/>
                            <div style="margin-top: 4px;"><strong>Issue:</strong> {issue.finding}</div>
                            <div style="color: #60a5fa; margin-top: 2px;"><strong>Action:</strong> {issue.recommendation}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Tab 3: All Checks Detailed View
        with tab_all:
            st.subheader("Complete Inspection Ledger")
            filter_status = st.multiselect("Filter by status", ["pass", "warn", "fail"], default=["pass", "warn", "fail"])
            filtered = [c for c in rep.checks if c.status in filter_status]

            for check in filtered:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(
                        f"**{check.name}** &nbsp; {render_badge(check.status)} &nbsp; <span style='color: gray; font-size: 0.85rem;'>[{check.category}]</span>",
                        unsafe_allow_html=True,
                    )
                    st.write(check.finding)
                    st.caption(f"Recommendation: {check.recommendation}")
                with col_b:
                    st.metric("Points", f"{check.earned} / {check.maximum}")
                st.divider()

        # Tab 4: Technical Metrics Summary
        with tab_meta:
            st.subheader("Page Characteristics and Crawl Artifacts")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("HTML Size", f"{rep.raw_stats['html_size_kb']} KB")
            m2.metric("Total Images", f"{rep.raw_stats['total_images']}")
            m3.metric("Total Links", f"{rep.raw_stats['total_links']}")
            m4.metric("Word Count", f"{rep.raw_stats['word_count']}")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("Avg Sentence Length", f"{rep.raw_stats['avg_sentence_words']} words")
            m6.metric("Scripts (Ext)", f"{rep.raw_stats['external_scripts']}")
            m7.metric("Stylesheets (Ext)", f"{rep.raw_stats['external_styles']}")
            m8.metric("Compression", f"{rep.raw_stats['encoding']}")

            st.json(rep.raw_stats)

        # Report download + footer
        st.markdown("---")
        st.download_button(
            "⬇️ Download full report (Markdown)",
            build_markdown_report(rep),
            file_name="rankpilot-report.md",
            mime="text/markdown",
        )
        st.markdown(
            "<p style='text-align:center;color:#6b7280;font-size:0.85rem;margin-top:2rem;'>RankPilot — data-driven SEO audits.</p>",
            unsafe_allow_html=True,
        )

if __name__ == "__main__":
    main()
