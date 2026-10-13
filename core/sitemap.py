import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Set
import requests


def _normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    clean = urllib.parse.urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return clean.rstrip("/") if path != "/" else clean


def _is_same_domain(netloc_a: str, netloc_b: str) -> bool:
    def strip_port_and_www(host: str) -> str:
        h = host.split(":")[0].lower()
        if h.startswith("www."):
            h = h[4:]
        return h
    return strip_port_and_www(netloc_a) == strip_port_and_www(netloc_b)


def _extract_loc_tags(xml_bytes: bytes) -> List[str]:
    urls: List[str] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        text = xml_bytes.decode("utf-8", errors="ignore")
        return re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", text, re.IGNORECASE)

    # ElementTree handles namespace prefixes via wildcard or strip
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag.lower() == "loc" and elem.text:
            cleaned = elem.text.strip()
            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                urls.append(cleaned)
    return urls


def fetch_sitemap_urls(base_url: str, max_pages: int = 25) -> List[str]:
    """
    Discovers URLs from /sitemap.xml for base_url.
    Follows child sitemaps in sitemap indexes for the same domain.
    Caps results at max_pages. Returns [base_url] on any unrecoverable failure.
    """
    normalized_base = _normalize_url(base_url)
    parsed_base = urllib.parse.urlparse(normalized_base)
    if not parsed_base.netloc:
        return [base_url]

    sitemap_root_url = urllib.parse.urljoin(
        f"{parsed_base.scheme}://{parsed_base.netloc}", "/sitemap.xml"
    )

    discovered_page_urls: List[str] = []
    visited_sitemaps: Set[str] = set()
    sitemaps_to_crawl: List[str] = [sitemap_root_url]
    seen_urls: Set[str] = set()

    session = requests.Session()
    session.headers.update({"User-Agent": "RankPilot-Crawler/1.0"})

    try:
        while sitemaps_to_crawl and len(discovered_page_urls) < max_pages:
            current_sitemap = sitemaps_to_crawl.pop(0)
            if current_sitemap in visited_sitemaps:
                continue
            visited_sitemaps.add(current_sitemap)

            try:
                resp = session.get(current_sitemap, timeout=8, allow_redirects=True)
                if resp.status_code != 200 or not resp.content:
                    continue
            except Exception:
                continue

            extracted = _extract_loc_tags(resp.content)
            for loc in extracted:
                norm_loc = _normalize_url(loc)
                parsed_loc = urllib.parse.urlparse(norm_loc)
                if not _is_same_domain(parsed_base.netloc, parsed_loc.netloc):
                    continue

                # Check whether target looks like a child sitemap
                is_sub_sitemap = (
                    norm_loc.endswith(".xml")
                    or "sitemap" in parsed_loc.path.lower()
                    or "sitemap" in parsed_loc.query.lower()
                )

                if is_sub_sitemap:
                    if norm_loc not in visited_sitemaps and norm_loc not in sitemaps_to_crawl:
                        sitemaps_to_crawl.append(norm_loc)
                else:
                    if norm_loc not in seen_urls:
                        seen_urls.add(norm_loc)
                        discovered_page_urls.append(norm_loc)
                        if len(discovered_page_urls) >= max_pages:
                            break

        if not discovered_page_urls:
            return [normalized_base]

        return discovered_page_urls[:max_pages]

    except Exception:
        return [normalized_base]