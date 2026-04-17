from __future__ import annotations

import html
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from textwrap import dedent

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
BASE_URL = "https://sauditravelandleisure.com"
SITE_NAME = "Saudi Travel and Leisure"
SITE_DESCRIPTION = "Saudi-first travel guides, itineraries, transport tips, food recommendations, and practical planning help for exploring the Kingdom."
HOME_PAGE_TITLE = "Saudi Arabia Travel Guides, Itineraries, Food & Transport"
CONTACT_EMAIL = "info@sauditravelandleisure.com"
TODAY = date.today()

NON_SAUDI_PATTERN = re.compile(r"(dubai|muscat|oman|abu-dhabi|abudhabi|qatar|kuwait|uae|sharjah|doha)", re.I)
NUMERIC_SUFFIX_PATTERN = re.compile(r"-\d+$")
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}:\d{2})?")
SITE_LINK_PATTERN = re.compile(rf'href="{re.escape(BASE_URL)}/([^"]*)"')
TITLE_SUFFIX_PATTERN = re.compile(r"\s*\|\s*Saudi Travel and Leisure\s*$")
INTERNAL_PATH_PATTERN = re.compile(r'href="(/[^"#?"]*/?)"')

LINK_KEY_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}

DUPLICATE_INTENT_PREFIXES = {"can", "do", "does", "how", "is", "what", "when", "where", "why"}
DUPLICATE_INTENT_STOPWORDS = LINK_KEY_STOPWORDS | {
    "advice",
    "arabia",
    "city",
    "complete",
    "context",
    "essential",
    "essentials",
    "explained",
    "facts",
    "from",
    "go",
    "guide",
    "guides",
    "i",
    "insider",
    "insights",
    "it",
    "know",
    "local",
    "my",
    "need",
    "now",
    "our",
    "overview",
    "per",
    "practical",
    "right",
    "rules",
    "saudi",
    "smart",
    "tip",
    "tips",
    "tourist",
    "tourists",
    "travel",
    "traveler",
    "travelers",
    "travellers",
    "visit",
    "we",
    "what",
    "year",
    "you",
}

SOURCE_CACHE: dict[str, str] = {}

NAV_LINKS = [
    ("/", "Home"),
    ("/saudi-destinations/", "Destinations"),
    ("/riyadh/", "Riyadh"),
    ("/jeddah/", "Jeddah"),
    ("/makkah-madinah/", "Makkah & Madinah"),
    ("/saudi-travel-basics/", "Travel Basics"),
    ("/saudi-itineraries-and-transport/", "Itineraries & Transport"),
    ("/saudi-food-and-culture/", "Food & Culture"),
]

HUBS = {
    "saudi-destinations": {
        "title": "Saudi Destinations",
        "description": "Browse destination-led guides for Saudi Arabia's coast, desert escapes, heritage sites, and first-trip planning.",
        "intro": "Use this hub when you are deciding where to go in Saudi Arabia, which regions deserve the most time, and what each destination feels like on the ground.",
        "hero_label": "Explore Saudi Arabia",
    },
    "riyadh": {
        "title": "Riyadh Guides",
        "description": "Neighbourhood guides, first-timer advice, transport tips, local food, and planning help for Riyadh.",
        "intro": "This hub brings together our Riyadh coverage so travellers can move from broad trip planning to specific decisions on where to stay, what to eat, and how to get around.",
        "hero_label": "Plan Riyadh Well",
    },
    "jeddah": {
        "title": "Jeddah Guides",
        "description": "Coastal city guides, itineraries, neighbourhood picks, and practical Jeddah planning advice.",
        "intro": "Use this hub for Jeddah trip planning, from short itineraries to where to stay and what to prioritise on a first visit.",
        "hero_label": "Discover Jeddah",
    },
    "makkah-madinah": {
        "title": "Makkah & Madinah Guides",
        "description": "Pilgrimage planning, transport, etiquette, and practical travel information for Makkah and Madinah.",
        "intro": "This section focuses on pilgrimage-adjacent planning, transport, etiquette, and practical questions around Makkah and Madinah travel.",
        "hero_label": "Travel With Context",
    },
    "alula": {
        "title": "AlUla Guides",
        "description": "Short itineraries, destination context, and trip-planning help for AlUla and nearby desert experiences.",
        "intro": "These AlUla guides are built to help travellers understand the destination quickly, plan their time, and connect nearby experiences into a stronger trip.",
        "hero_label": "Plan AlUla",
    },
    "saudi-travel-basics": {
        "title": "Saudi Travel Basics",
        "description": "Core planning help for first-time visitors: SIM cards, money, dress code, phrases, rules, and travel logistics.",
        "intro": "Start here if you need the practical foundation for a Saudi trip. These are the guides that reduce first-timer friction before you get to the fun part.",
        "hero_label": "Start Smart",
    },
    "saudi-itineraries-and-transport": {
        "title": "Saudi Itineraries & Transport",
        "description": "Short itineraries, transfers, metro and airport guides, and getting-around advice for Saudi Arabia.",
        "intro": "This hub groups our best planning content for how long to stay, how to move between places, and how to make each day of a Saudi trip work better.",
        "hero_label": "Move Confidently",
    },
    "saudi-food-and-culture": {
        "title": "Saudi Food & Culture",
        "description": "Street food, coffee, halal dining, cultural context, and local etiquette for travellers in Saudi Arabia.",
        "intro": "Food and culture are where a Saudi trip becomes memorable. Use this hub for local dishes, dining context, and etiquette that makes the experience smoother.",
        "hero_label": "Eat & Understand",
    },
}

INDEXABLE_HUB_ORDER = [
    "saudi-destinations",
    "riyadh",
    "jeddah",
    "makkah-madinah",
    "alula",
    "saudi-travel-basics",
    "saudi-itineraries-and-transport",
    "saudi-food-and-culture",
]

RESERVED_PAGE_SLUGS = {
    "",
    "about",
    "contact",
    "editorial-policy",
    *INDEXABLE_HUB_ORDER,
}

SITE_CSS = dedent(
    """
    :root {
      --ink: #0f172a;
      --ink-soft: #334155;
      --sea: #0f766e;
      --sea-soft: #ccfbf1;
      --sand: #f8fafc;
      --sand-deep: #e2e8f0;
      --accent: #d97706;
      --accent-soft: #ffedd5;
      --text: #1e293b;
      --muted: #475569;
      --muted-soft: #64748b;
      --white: #ffffff;
      --max: 1180px;
      --shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
      --radius-lg: 28px;
      --radius-md: 18px;
      --radius-sm: 12px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      scroll-behavior: smooth;
    }

    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 28%),
        radial-gradient(circle at top right, rgba(217, 119, 6, 0.08), transparent 24%),
        var(--sand);
      line-height: 1.7;
    }

    a {
      color: var(--sea);
      text-decoration: none;
    }

    a:hover {
      text-decoration: underline;
    }

    img {
      max-width: 100%;
      height: auto;
      display: block;
    }

    .site-header {
      position: sticky;
      top: 0;
      z-index: 10;
      backdrop-filter: blur(14px);
      background: rgba(248, 250, 252, 0.92);
      border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    }

    .header-inner,
    .page-shell,
    .footer-inner {
      width: min(calc(100% - 32px), var(--max));
      margin: 0 auto;
    }

    .header-inner {
      min-height: 74px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }

    .brand {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      color: var(--ink);
      font-weight: 800;
      font-size: 1.08rem;
      letter-spacing: -0.02em;
      text-decoration: none;
    }

    .brand-mark {
      width: 40px;
      height: 40px;
      border-radius: 14px;
      background: linear-gradient(135deg, var(--sea), var(--ink));
      display: grid;
      place-items: center;
      color: var(--white);
      font-weight: 800;
      box-shadow: var(--shadow);
    }

    .main-nav {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .main-nav a {
      color: var(--muted);
      font-size: 0.95rem;
      font-weight: 600;
      padding: 10px 14px;
      border-radius: 999px;
    }

    .main-nav a:hover,
    .main-nav a.active {
      color: var(--ink);
      background: rgba(15, 118, 110, 0.08);
      text-decoration: none;
    }

    .page-shell {
      padding: 40px 0 72px;
    }

    .hero-card,
    .content-card,
    .hub-card,
    .article-card,
    .sidebar-card,
    .footer-callout,
    .feature-card,
    .grid-card,
    .notice-card {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
    }

    .hero-card,
    .content-card,
    .article-card,
    .notice-card {
      padding: 30px;
    }

    .hero-card {
      display: grid;
      grid-template-columns: 1.35fr 0.9fr;
      gap: 28px;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(217, 119, 6, 0.06)),
        rgba(255, 255, 255, 0.95);
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--sea-soft);
      color: var(--sea);
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      margin-bottom: 16px;
    }

    h1,
    h2,
    h3 {
      color: var(--ink);
      letter-spacing: -0.03em;
      line-height: 1.2;
      margin: 0 0 16px;
    }

    h1 {
      font-size: clamp(2rem, 4vw, 3.35rem);
    }

    h2 {
      font-size: clamp(1.45rem, 2vw, 2rem);
      margin-top: 34px;
    }

    h3 {
      font-size: 1.15rem;
      margin-top: 28px;
    }

    p {
      margin: 0 0 16px;
      color: var(--muted);
    }

    .hero-text p,
    .article-intro {
      font-size: 1.04rem;
    }

    .hero-visual {
      align-self: stretch;
      border-radius: 22px;
      overflow: hidden;
      border: 1px solid rgba(15, 23, 42, 0.08);
      background: linear-gradient(135deg, #dcfce7, #ecfeff 45%, #ffedd5);
    }

    .hero-visual img {
      height: 100%;
      object-fit: cover;
    }

    .section {
      margin-top: 30px;
    }

    .section-header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    .section-header p {
      max-width: 62ch;
      margin: 0;
    }

    .hub-grid,
    .card-grid,
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }

    .grid-card,
    .hub-card,
    .feature-card {
      padding: 22px;
    }

    .hub-card .count {
      display: inline-flex;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.8rem;
      font-weight: 700;
      margin-bottom: 12px;
    }

    .card-title {
      font-size: 1.06rem;
      margin-bottom: 10px;
    }

    .card-meta,
    .article-meta,
    .breadcrumbs,
    .archive-note,
    .footer-meta {
      color: var(--muted-soft);
      font-size: 0.92rem;
    }

    .card-meta,
    .article-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin-bottom: 18px;
    }

    .breadcrumbs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 18px;
    }

    .breadcrumbs span.sep {
      color: #94a3b8;
    }

    .article-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.8fr);
      gap: 24px;
      margin-top: 24px;
    }

    .article-body {
      min-width: 0;
    }

    .article-body h2:first-of-type {
      margin-top: 0;
    }

    .article-body p,
    .article-body li,
    .article-body td,
    .article-body th {
      font-size: 1rem;
    }

    .article-body ul,
    .article-body ol {
      padding-left: 1.4rem;
      margin: 0 0 16px;
      color: var(--muted);
    }

    .article-body table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid rgba(148, 163, 184, 0.25);
      background: rgba(248, 250, 252, 0.8);
    }

    .article-body th,
    .article-body td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.18);
      text-align: left;
    }

    .article-body th {
      color: var(--ink);
      background: rgba(15, 118, 110, 0.06);
    }

    .article-body .content-table {
      padding: 18px 20px 18px 34px;
      border-radius: var(--radius-md);
      background: rgba(15, 118, 110, 0.06);
    }

    .article-body img {
      border-radius: 18px;
      margin: 22px 0;
      box-shadow: var(--shadow);
    }

    .article-sidebar {
      display: grid;
      gap: 16px;
      align-content: start;
    }

    .sidebar-card {
      padding: 20px;
      border-radius: var(--radius-md);
    }

    .sidebar-card h2,
    .sidebar-card h3 {
      margin-top: 0;
      margin-bottom: 10px;
      font-size: 1.08rem;
    }

    .link-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }

    .link-list li {
      margin: 0;
    }

    .link-list a {
      font-weight: 700;
      color: var(--ink);
    }

    .archive-note {
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(217, 119, 6, 0.08);
      border: 1px solid rgba(217, 119, 6, 0.15);
    }

    .trust-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }

    .trust-pill {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(15, 118, 110, 0.08);
      color: var(--ink);
      font-weight: 700;
      font-size: 0.92rem;
    }

    .notice-card {
      margin-top: 24px;
    }

    .footer {
      padding: 28px 0 56px;
    }

    .footer-inner {
      display: grid;
      gap: 18px;
    }

    .footer-callout {
      padding: 24px;
      display: flex;
      justify-content: space-between;
      gap: 22px;
      align-items: center;
      background:
        linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(217, 119, 6, 0.06)),
        rgba(255, 255, 255, 0.95);
    }

    .footer-callout p {
      max-width: 56ch;
      margin-bottom: 0;
    }

    .footer-links {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      color: var(--muted-soft);
    }

    .footer-links a {
      color: var(--muted);
      font-weight: 600;
    }

    .muted {
      color: var(--muted-soft);
    }

    .inline-link {
      font-weight: 700;
    }

    .cta-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 13px 18px;
      border-radius: 999px;
      background: var(--ink);
      color: var(--white);
      font-weight: 700;
      box-shadow: var(--shadow);
    }

    .cta-button:hover {
      text-decoration: none;
      background: var(--sea);
    }

    @media (max-width: 1040px) {
      .hero-card,
      .article-layout {
        grid-template-columns: 1fr;
      }

      .hub-grid,
      .card-grid,
      .feature-grid,
      .trust-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .footer-callout {
        flex-direction: column;
        align-items: flex-start;
      }
    }

    @media (max-width: 760px) {
      .header-inner {
        align-items: flex-start;
        flex-direction: column;
        padding: 14px 0;
      }

      .hero-card,
      .content-card,
      .article-card,
      .notice-card {
        padding: 22px;
      }

      .hub-grid,
      .card-grid,
      .feature-grid,
      .trust-strip {
        grid-template-columns: 1fr;
      }

      .page-shell {
        padding-top: 26px;
      }

      h1 {
        font-size: 2.2rem;
      }
    }
    """
).strip()


def slug_from_path(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if rel.as_posix() == "index.html":
        return ""
    return rel.parent.as_posix()


def strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).replace("\xa0", " ").strip()


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_source(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    cached = SOURCE_CACHE.get(rel)
    if cached is not None:
        return cached
    try:
        proc = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        SOURCE_CACHE[rel] = proc.stdout
    except subprocess.CalledProcessError:
        SOURCE_CACHE[rel] = read(path)
    return SOURCE_CACHE[rel]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_title(raw: str) -> str:
    match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
    title = strip_tags(match.group(1)) if match else ""
    return TITLE_SUFFIX_PATTERN.sub("", title).strip()


def parse_meta_description(raw: str) -> str:
    match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', raw, re.I)
    return html.unescape(match.group(1)).strip() if match else ""


def parse_h1(raw: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
    return strip_tags(match.group(1)) if match else ""


def parse_article_h1(raw: str) -> str:
    match = re.search(r"<main>\s*<article>\s*<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
    if match:
        return strip_tags(match.group(1))
    match = re.search(r'<div class="article-card">.*?<h1[^>]*>(.*?)</h1>', raw, re.I | re.S)
    return strip_tags(match.group(1)) if match else ""


def parse_date(raw: str) -> date | None:
    match = re.search(r'<div class="post-meta">([^<]+)</div>', raw)
    if not match:
        return None
    date_match = DATE_PATTERN.search(match.group(1))
    if not date_match:
        return None
    return datetime.strptime(date_match.group(1), "%Y-%m-%d").date()


def parse_main_article_body(raw: str) -> str:
    article_match = re.search(r"<main>\s*<article>\s*<h1[^>]*>.*?</h1>(?:\s*<div class=\"post-meta\">.*?</div>)?(.*)</article>\s*</main>", raw, re.S)
    if article_match:
        return article_match.group(1)
    card_match = re.search(r'<div class="article-body">\s*(.*)\s*</div>\s*<aside class="article-sidebar">', raw, re.S)
    if card_match:
        return card_match.group(1)
    main_match = re.search(r"<main>(.*)</main>", raw, re.S)
    return main_match.group(1) if main_match else ""


def normalize_internal_links(content: str) -> str:
    content = SITE_LINK_PATTERN.sub(lambda match: f'href="/{match.group(1)}"', content)
    content = content.replace(f'href="{BASE_URL}"', 'href="/"')
    return content


def normalise_slug_key(slug: str) -> tuple[str, ...]:
    working = slug.lower().replace("al-ula", "alula")
    tokens = []
    for token in re.split(r"[^a-z0-9]+", working):
        if not token or token in LINK_KEY_STOPWORDS:
            continue
        token = {
            "medina": "madinah",
            "mecca": "makkah",
            "travellers": "travelers",
            "tourists": "tourist",
        }.get(token, token)
        tokens.append(token)
    return tuple(tokens)


def category_replacement(path: str) -> str:
    path_l = path.lower()
    mappings = [
        ("/category/saudi-arabia/riyadh/", "/riyadh/"),
        ("/category/saudi-arabia/jeddah/", "/jeddah/"),
        ("/category/saudi-arabia/alula/", "/alula/"),
        ("/category/saudi-arabia/makkah/", "/makkah-madinah/"),
        ("/category/saudi-arabia/madinah/", "/makkah-madinah/"),
        ("/category/saudi-arabia/", "/saudi-destinations/"),
        ("/category/food-and-drink/", "/saudi-food-and-culture/"),
        ("/category/culture/", "/saudi-food-and-culture/"),
        ("/category/travel-tips/", "/saudi-travel-basics/"),
        ("/category/things-to-do/", "/saudi-destinations/"),
        ("/category/places-to-stay/", "/saudi-destinations/"),
        ("/category/gulf/", "/"),
        ("/category/united-arab-emirates/", "/"),
        ("/category/united-ar-emirates/", "/"),
    ]
    for prefix, replacement in mappings:
        if path_l.startswith(prefix):
            return replacement
    return "/"


def build_slug_aliases(pages: dict[str, dict]) -> dict[tuple[str, ...], str]:
    grouped: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for slug in pages:
        if slug:
            grouped[normalise_slug_key(slug)].add(slug)
    return {
        key: next(iter(slugs))
        for key, slugs in grouped.items()
        if len(slugs) == 1
    }


def rewrite_internal_path(path: str, known_slugs: set[str], slug_aliases: dict[tuple[str, ...], str]) -> str:
    if path == "/":
        return path
    if path.startswith("/category/"):
        return category_replacement(path)

    slug = path.strip("/")
    if slug.endswith("index.html"):
        slug = slug[:-10].rstrip("/")
    if not slug:
        return "/"
    if slug in known_slugs or slug in RESERVED_PAGE_SLUGS:
        return f"/{slug}/"

    alias = slug_aliases.get(normalise_slug_key(slug))
    if alias:
        return f"/{alias}/"
    return path


def repair_body_links(body: str, known_slugs: set[str], slug_aliases: dict[tuple[str, ...], str]) -> str:
    return INTERNAL_PATH_PATTERN.sub(
        lambda match: f'href="{rewrite_internal_path(match.group(1), known_slugs, slug_aliases)}"',
        body,
    )


def clean_article_body(body: str) -> str:
    cleaned = body
    cleaned = normalize_internal_links(cleaned)
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.S)
    cleaned = re.sub(r"<(?:/?html|/?head|/?body)[^>]*>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<span[^>]*data-mce-fragment[^>]*>", "", cleaned, flags=re.I)
    cleaned = cleaned.replace("</span>", "")
    cleaned = cleaned.replace("Â ", " ").replace("Â", " ")
    cleaned = re.sub(r'<h2>\s*Table of Contents\s*</h2>\s*<ol class="content-table">.*?</ol>', "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r'<p[^>]*>\s*<strong>\s*subtitle:\s*</strong>.*?</p>', "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<hr\s*/?>\s*<h2>\s*Meta Description\s*</h2>\s*<p>.*?</p>\s*<hr\s*/?>", "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<hr\s*/?>\s*<h2>\s*More Related Guides\s*</h2>\s*<p>.*?</p>", "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<h2>\s*About the Author\s*</h2>\s*<p>.*?</p>", "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<p[^>]*>\s*<strong>\s*About the Author\s*</strong>\s*</p>\s*<p>.*?</p>", "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<hr\s*/?>\s*<h2>\s*Article Metadata\s*</h2>\s*<p>.*?</p>", "", cleaned, count=1, flags=re.I | re.S)
    cleaned = re.sub(r"<h3>\s*Medium Tags\s*</h3>\s*<ol>.*?</ol>", "", cleaned, count=1, flags=re.I | re.S)
    paragraph_cleanup_patterns = [
        r"<p[^>]*>(?:(?!</p>).)*newsletter(?:(?!</p>).)*subscribe now(?:(?!</p>).)*</p>",
        r"<p[^>]*>(?:(?!</p>).)*word count:(?:(?!</p>).)*</p>",
        r"<p[^>]*>(?:(?!</p>).)*medium tags:(?:(?!</p>).)*</p>",
        r"<p[^>]*>(?:(?!</p>).)*byline:(?:(?!</p>).)*</p>",
        r"<p[^>]*>(?:(?!</p>).)*(author:|author title:|published:|url slug:|reading time:)(?:(?!</p>).)*</p>",
        r"<p[^>]*>\s*-\s*#[^<]+</p>",
    ]
    for pattern in paragraph_cleanup_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.I | re.S)
    cleaned = cleaned.replace("</body></html>", "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def first_paragraph_text(body: str) -> str:
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.I | re.S):
        text = compact_text(strip_tags(match.group(1)))
        lowered = text.lower()
        if not text:
            continue
        if any(
            marker in lowered
            for marker in (
                "about the author",
                "author:",
                "author title:",
                "meta description",
                "published:",
                "reading time:",
                "subtitle:",
                "url slug:",
                "word count:",
            )
        ):
            continue
        return text
    return ""


def short_description(title: str, meta_desc: str, body: str) -> str:
    candidate = compact_text(meta_desc)
    if candidate and candidate.lower() != title.lower() and len(candidate) >= 70:
        return candidate[:158]
    first = first_paragraph_text(body)
    if first:
        if len(first) > 158:
            first = first[:155].rsplit(" ", 1)[0] + "..."
        return first
    fallback = f"{title} with practical Saudi travel planning advice, local context, and easy next steps from {SITE_NAME}."
    return fallback[:158]


def pretty_date(value: date | None) -> str:
    return value.strftime("%B %-d, %Y") if value else TODAY.strftime("%B %-d, %Y")


def iso_date(value: date | None) -> str:
    return value.isoformat() if value else TODAY.isoformat()


def tokenise_slug(slug: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", slug.lower()) if token and token not in {"in", "to", "the", "of", "a", "an", "and"}]


def hub_for_slug(slug: str) -> str:
    slug_l = slug.lower()
    if any(token in slug_l for token in ("riyadh",)):
        return "riyadh"
    if any(token in slug_l for token in ("jeddah",)):
        return "jeddah"
    if any(token in slug_l for token in ("makkah", "mecca", "madinah", "medina", "umrah", "zamzam", "kaaba", "haram")):
        return "makkah-madinah"
    if any(token in slug_l for token in ("alula", "al-ula", "ula")):
        return "alula"
    if any(token in slug_l for token in ("itinerary", "transport", "metro", "airport", "getting-from", "get-from", "mecca-to-medina", "how-far", "how-long", "taxi", "uber", "flight", "station")):
        return "saudi-itineraries-and-transport"
    if any(token in slug_l for token in ("food", "restaurant", "coffee", "halal", "street-food", "culture", "what-to-eat")):
        return "saudi-food-and-culture"
    if any(token in slug_l for token in ("sim-card", "wifi", "internet", "currency", "dress-code", "phrases", "tipping", "photography", "hostel", "rules", "guide", "tips", "first-time", "visa", "safe", "safety", "abaya")):
        return "saudi-travel-basics"
    return "saudi-destinations"


def supplementary_hubs_for_slug(slug: str) -> list[str]:
    slug_l = slug.lower()
    hubs = set()
    if any(token in slug_l for token in ("itinerary", "transport", "metro", "airport", "getting-from", "get-from", "mecca-to-medina", "how-far", "how-long", "taxi", "uber", "flight", "station")):
        hubs.add("saudi-itineraries-and-transport")
    if any(token in slug_l for token in ("food", "restaurant", "coffee", "halal", "street-food", "culture", "what-to-eat")):
        hubs.add("saudi-food-and-culture")
    if any(token in slug_l for token in ("sim-card", "wifi", "internet", "currency", "dress-code", "phrases", "tipping", "photography", "hostel", "rules", "guide", "tips", "first-time", "visa", "safe", "safety", "abaya")):
        hubs.add("saudi-travel-basics")
    return sorted(hubs)


def duplicate_intent_key(slug: str) -> str | None:
    tokens = tokenise_slug(slug.replace("al-ula", "alula"))
    if not tokens:
        return None
    if tokens[:2] == ["travel", "smart"] and len(tokens) > 2:
        tokens = tokens[2:]
    prefix = tokens[0]
    if prefix not in DUPLICATE_INTENT_PREFIXES:
        return None

    core = []
    for token in tokens[1:]:
        token = {
            "medina": "madinah",
            "mecca": "makkah",
            "travellers": "travelers",
            "tourists": "tourist",
            "americans": "american",
            "hotels": "hotel",
        }.get(token, token)
        if token in DUPLICATE_INTENT_STOPWORDS:
            continue
        core.append(token)
    if not core:
        return None
    if prefix == "can":
        core = sorted(core)
    return f"{prefix}:{'-'.join(core[:5])}"


def page_quality_score(page: dict) -> tuple[int, int, int]:
    body_length = len(strip_tags(page["body"]))
    published_score = int((page["published"] or TODAY).strftime("%Y%m%d"))
    return body_length, len(page["title"]), published_score


def mark_duplicate_pages(pages: dict[str, dict]) -> int:
    duplicate_groups: dict[str, list[dict]] = defaultdict(list)
    for page in pages.values():
        if page["noindex"]:
            continue
        key = duplicate_intent_key(page["slug"])
        if key:
            duplicate_groups[key].append(page)

    duplicates_marked = 0
    for group_pages in duplicate_groups.values():
        if len(group_pages) < 2:
            continue
        winner = max(group_pages, key=page_quality_score)
        for page in group_pages:
            if page["slug"] == winner["slug"]:
                continue
            page["noindex"] = True
            page["archive_reason"] = "duplicate"
            page["preferred_slug"] = winner["slug"]
            page["preferred_title"] = winner["title"]
            duplicates_marked += 1
    return duplicates_marked


def hub_href(hub_slug: str) -> str:
    return f"/{hub_slug}/"


def full_url(slug: str) -> str:
    return BASE_URL + ("/" if not slug else f"/{slug}/")


def nav_html(active_slug: str | None = None) -> str:
    links = []
    for href, label in NAV_LINKS:
        link_slug = href.strip("/")
        active = "active" if active_slug == link_slug else ""
        links.append(f'<a class="{active}" href="{href}">{html.escape(label)}</a>')
    links.append('<a href="/about/">About</a>')
    links.append('<a href="/contact/">Contact</a>')
    return "".join(links)


def breadcrumbs(items: list[tuple[str | None, str]]) -> str:
    parts = []
    for index, (href, label) in enumerate(items):
        if href:
            parts.append(f'<a href="{href}">{html.escape(label)}</a>')
        else:
            parts.append(f"<span>{html.escape(label)}</span>")
        if index < len(items) - 1:
            parts.append('<span class="sep">/</span>')
    return f'<nav class="breadcrumbs" aria-label="Breadcrumbs">{"".join(parts)}</nav>'


def breadcrumbs_schema(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": name,
                "item": url,
            }
            for idx, (url, name) in enumerate(items)
        ],
    }


def organization_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": SITE_NAME,
        "url": BASE_URL,
        "description": SITE_DESCRIPTION,
        "email": CONTACT_EMAIL,
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "contactType": "editorial",
                "email": CONTACT_EMAIL,
            }
        ],
    }


def json_ld(schema: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}</script>'


def page_head(
    title: str,
    description: str,
    canonical: str,
    robots: str,
    og_type: str,
    schemas: list[dict],
) -> str:
    page_title = f"{title} | {SITE_NAME}" if title != SITE_NAME else SITE_NAME
    meta_title = html.escape(page_title)
    meta_desc = html.escape(description)
    return dedent(
        f"""
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="theme-color" content="#0f172a">
          <title>{meta_title}</title>
          <meta name="description" content="{meta_desc}">
          <meta name="robots" content="{robots}">
          <link rel="canonical" href="{canonical}">
          <link rel="icon" href="/favicon.ico" sizes="any">
          <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
          <link rel="stylesheet" href="/assets/site.css">
          <meta property="og:site_name" content="{SITE_NAME}">
          <meta property="og:title" content="{meta_title}">
          <meta property="og:description" content="{meta_desc}">
          <meta property="og:url" content="{canonical}">
          <meta property="og:type" content="{og_type}">
          <meta property="og:image" content="{BASE_URL}/assets/og-default.png">
          <meta property="og:image:width" content="1200">
          <meta property="og:image:height" content="630">
          <meta property="og:image:alt" content="Saudi Travel and Leisure preview card">
          <meta name="twitter:card" content="summary_large_image">
          <meta name="twitter:title" content="{meta_title}">
          <meta name="twitter:description" content="{meta_desc}">
          <meta name="twitter:image" content="{BASE_URL}/assets/og-default.png">
          {''.join(json_ld(schema) for schema in schemas)}
        </head>
        """
    ).strip()


def page_shell(body_class: str, active_nav_slug: str | None, body_html: str, title: str) -> str:
    return dedent(
        f"""
        <body class="{body_class}">
          <header class="site-header">
            <div class="header-inner">
              <a class="brand" href="/" aria-label="{SITE_NAME} homepage">
                <span class="brand-mark">ST</span>
                <span>{SITE_NAME}</span>
              </a>
              <nav class="main-nav" aria-label="Main navigation">
                {nav_html(active_nav_slug)}
              </nav>
            </div>
          </header>
          {body_html}
          <footer class="footer">
            <div class="footer-inner">
              <section class="footer-callout">
                <div>
                  <h2>Plan better Saudi trips</h2>
                  <p>We focus on practical Saudi-first travel planning: where to go, how to move, what to know, and what matters before you book.</p>
                </div>
                <a class="cta-button" href="/saudi-travel-basics/">Start with travel basics</a>
              </section>
              <div class="footer-links">
                <a href="/">Home</a>
                <a href="/about/">About</a>
                <a href="/contact/">Contact</a>
                <a href="/editorial-policy/">Editorial policy</a>
                <a href="/saudi-destinations/">Destinations</a>
                <a href="/saudi-itineraries-and-transport/">Itineraries &amp; Transport</a>
              </div>
              <div class="footer-meta">
                <div>&copy; {TODAY.year} {SITE_NAME}. Editorial contact: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>
                <div class="muted">Saudi-first travel guidance, curated for practical planning rather than mass-indexed question pages.</div>
              </div>
            </div>
          </footer>
        </body>
        """
    ).strip()


def render_card(link: str, title: str, description: str, meta: str = "") -> str:
    meta_html = f'<div class="card-meta">{meta}</div>' if meta else ""
    return dedent(
        f"""
        <article class="grid-card">
          <h3 class="card-title"><a href="{link}">{html.escape(title)}</a></h3>
          {meta_html}
          <p>{html.escape(description)}</p>
        </article>
        """
    ).strip()


def create_image_assets() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    svg = dedent(
        """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-labelledby="title desc">
          <title id="title">Saudi Travel and Leisure favicon</title>
          <desc id="desc">A stylised desert sun above dunes.</desc>
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#0f766e"/>
              <stop offset="100%" stop-color="#0f172a"/>
            </linearGradient>
          </defs>
          <rect width="128" height="128" rx="32" fill="url(#bg)"/>
          <circle cx="74" cy="44" r="20" fill="#f59e0b"/>
          <path d="M26 88c10-8 19-11 28-11 10 0 18 3 25 8 7-5 15-8 25-8 8 0 15 2 24 8v16H26V88Z" fill="#ffffff"/>
        </svg>
        """
    ).strip()
    write(ASSETS_DIR / "favicon.svg", svg)

    og = Image.new("RGB", (1200, 630), "#0f172a")
    draw = ImageDraw.Draw(og)
    for y in range(630):
        blend = y / 629
        r = int(15 * (1 - blend) + 11 * blend)
        g = int(118 * (1 - blend) + 23 * blend)
        b = int(110 * (1 - blend) + 42 * blend)
        draw.line([(0, y), (1200, y)], fill=(r, g, b))
    draw.ellipse((830, 80, 1110, 360), fill="#f59e0b")
    draw.rounded_rectangle((70, 70, 1130, 560), radius=44, outline=(255, 255, 255, 40), width=2)
    title_font = ImageFont.load_default()
    body_font = ImageFont.load_default()
    draw.text((96, 110), "Saudi Travel and Leisure", fill="white", font=title_font)
    draw.text((96, 180), "Saudi-first travel guides,\nplanning help, and practical trip advice.", fill="#e2e8f0", font=body_font, spacing=10)
    draw.rounded_rectangle((96, 320, 430, 388), radius=24, fill="#ffffff")
    draw.text((122, 343), "Saudi-first editorial focus", fill="#0f172a", font=body_font)
    draw.text((96, 440), "Riyadh • Jeddah • AlUla • Makkah & Madinah", fill="#fef3c7", font=body_font)
    og.save(ASSETS_DIR / "og-default.png")

    favicon = og.resize((64, 64))
    favicon.save(ROOT / "favicon.ico", sizes=[(64, 64), (32, 32), (16, 16)])


def page_intro(title: str, description: str, label: str = "Saudi-first travel planning") -> str:
    return dedent(
        f"""
        <section class="page-shell">
          <div class="hero-card">
            <div class="hero-text">
              <div class="eyebrow">{html.escape(label)}</div>
              <h1>{html.escape(title)}</h1>
              <p>{html.escape(description)}</p>
              <div class="trust-strip">
                <div class="trust-pill">Saudi-first editorial scope</div>
                <div class="trust-pill">Practical travel planning</div>
                <div class="trust-pill">Clear next-step links</div>
                <div class="trust-pill">Updated static archive</div>
              </div>
            </div>
            <div class="hero-visual">
              <img src="/assets/og-default.png" alt="Saudi Travel and Leisure overview graphic" loading="eager">
            </div>
          </div>
        """
    ).strip()


def render_home(pages: dict, hub_articles: dict[str, list[dict]]) -> str:
    latest = sorted(
        [page for page in pages.values() if page.get("is_article") and not page.get("noindex")],
        key=lambda item: item.get("published") or date(2000, 1, 1),
        reverse=True,
    )[:12]
    latest_cards = "\n".join(
        render_card(
            page["href"],
            page["title"],
            page["description"],
            f"Updated {pretty_date(page['published'])} · {HUBS[page['hub']]['title']}",
        )
        for page in latest
    )

    hub_cards = "\n".join(
        dedent(
            f"""
            <article class="hub-card">
              <div class="count">{len(hub_articles[hub_slug])} guides</div>
              <h3 class="card-title"><a href="{hub_href(hub_slug)}">{html.escape(HUBS[hub_slug]['title'])}</a></h3>
              <p>{html.escape(HUBS[hub_slug]['description'])}</p>
            </article>
            """
        ).strip()
        for hub_slug in INDEXABLE_HUB_ORDER
    )

    body = dedent(
        f"""
        {page_intro("Saudi travel planning that helps you move faster and choose better.", "Start with destination hubs, core travel basics, and the planning guides that matter before you book.", "Saudi-first travel resource")}
          <section class="section content-card">
            <div class="section-header">
              <div>
                <div class="eyebrow">Topic hubs</div>
                <h2>Use the site by decision, not by archive date</h2>
              </div>
              <p>These hub pages replace the old feed-first homepage and give search engines stronger, topic-led pathways into the Saudi content that deserves to rank.</p>
            </div>
            <div class="hub-grid">
              {hub_cards}
            </div>
          </section>
          <section class="section content-card">
            <div class="section-header">
              <div>
                <div class="eyebrow">Latest Saudi guides</div>
                <h2>Recent planning content</h2>
              </div>
              <p>We prioritise pages that help travellers take the next step: where to stay, how to get around, what to know, and what to experience.</p>
            </div>
            <div class="card-grid">
              {latest_cards}
            </div>
          </section>
          <section class="section notice-card">
            <div class="section-header">
              <div>
                <div class="eyebrow">Editorial note</div>
                <h2>A tighter scope means stronger traffic potential</h2>
              </div>
            </div>
            <p>We have refocused the site around Saudi Arabia and moved a large archive of broader Gulf content out of the index. That helps search engines understand the site's strongest subject matter and improves the odds that high-value Saudi pages earn the visibility they deserve.</p>
          </section>
        </section>
        """
    ).strip()
    return body


def render_hub_page(hub_slug: str, hub_pages: list[dict]) -> str:
    cards = "\n".join(
        render_card(page["href"], page["title"], page["description"], f"Updated {pretty_date(page['published'])}")
        for page in hub_pages[:18]
    )
    hub = HUBS[hub_slug]
    crumbs = breadcrumbs([
        ("/", "Home"),
        (None, hub["title"]),
    ])
    return dedent(
        f"""
        {page_intro(hub['title'], hub['intro'], hub['hero_label'])}
          <section class="content-card section">
            {crumbs}
            <div class="section-header">
              <div>
                <div class="eyebrow">Curated Saudi coverage</div>
                <h2>{html.escape(hub['title'])}</h2>
              </div>
              <p>{html.escape(hub['description'])}</p>
            </div>
            <div class="card-grid">
              {cards}
            </div>
          </section>
        </section>
        """
    ).strip()


def render_about_page() -> str:
    crumbs = breadcrumbs([
        ("/", "Home"),
        (None, "About"),
    ])
    return dedent(
        f"""
        {page_intro("About Saudi Travel and Leisure", "We publish Saudi-first travel guidance with an editorial focus on practical planning, local context, and clear next steps for travellers.", "About the publication")}
          <section class="content-card section">
            {crumbs}
            <h2>What we cover</h2>
            <p>{SITE_NAME} is built around travel planning for Saudi Arabia: destinations, itineraries, transport, food, culture, and first-time visitor essentials. We organise the site so travellers can move from broad inspiration to specific decisions quickly.</p>
            <h2>How we work</h2>
            <p>Our editorial standard is simple: if a guide does not help someone make a better travel decision, it should not be in the primary index. We prioritise pages with practical value, clear structure, and useful connections to related Saudi planning topics.</p>
            <h2>Our current focus</h2>
            <p>We have deliberately tightened the site's indexed footprint around Saudi Arabia. Legacy broader-Gulf pages are still accessible for reference where useful, but our growth strategy and editorial energy are now concentrated on Saudi-first coverage.</p>
            <h2>Corrections and updates</h2>
            <p>If you spot an outdated fact, a transport change, or a tourism detail that needs correction, email us at <a class="inline-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We review travel information continuously and update priority pages as facts change.</p>
          </section>
        </section>
        """
    ).strip()


def render_contact_page() -> str:
    crumbs = breadcrumbs([
        ("/", "Home"),
        (None, "Contact"),
    ])
    return dedent(
        f"""
        {page_intro("Contact Saudi Travel and Leisure", "Reach the editorial team for corrections, partnerships, destination suggestions, and travel-guide updates.", "Editorial contact")}
          <section class="content-card section">
            {crumbs}
            <h2>Email the editorial team</h2>
            <p>The fastest way to reach us is <a class="inline-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. Use this address for corrections, destination suggestions, collaborations, and questions about a guide.</p>
            <h2>What to include</h2>
            <ul>
              <li>The page URL if you are reporting an update or correction.</li>
              <li>Your suggested fix and, when possible, the source or first-hand context behind it.</li>
              <li>A clear note if your message is editorial, partnership-related, or about a factual correction.</li>
            </ul>
            <h2>Editorial response</h2>
            <p>We prioritise factual corrections and updates to high-intent Saudi planning guides. If your note changes what a traveller should do in practice, we will move it up the queue.</p>
          </section>
        </section>
        """
    ).strip()


def render_editorial_page() -> str:
    crumbs = breadcrumbs([
        ("/", "Home"),
        (None, "Editorial policy"),
    ])
    return dedent(
        f"""
        {page_intro("Editorial policy", "How Saudi Travel and Leisure handles sourcing, updates, archive decisions, and Saudi-first editorial scope.", "Editorial standards")}
          <section class="content-card section">
            {crumbs}
            <h2>Our scope</h2>
            <p>{SITE_NAME} is now intentionally Saudi-first. We keep some legacy Gulf guides available for reference, but the primary indexed experience is focused on Saudi Arabia destinations, travel basics, transport, food, and cultural planning.</p>
            <h2>How guides are updated</h2>
            <p>We prioritise pages that affect real decisions: visas, airport transfers, transport, dress expectations, safety context, where to stay, and first-time planning. When a page no longer reflects the clearest version of a topic, we consolidate it rather than letting duplicate variants compete in search.</p>
            <h2>Sources and confidence</h2>
            <p>We prefer practical, decision-ready guidance over filler. That means clearer structure, fewer duplicate pages, stronger internal linking, and corrections when transport rules, destination access, or planning details change.</p>
            <h2>Corrections and archive handling</h2>
            <p>If a guide is no longer part of the primary Saudi focus, we keep it accessible as an archive reference and mark it accordingly. If a stronger page replaces a duplicate intent, we move that weaker page out of the index. Corrections can be sent to <a class="inline-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
          </section>
        </section>
        """
    ).strip()


def render_404_page() -> str:
    return dedent(
        f"""
        {page_intro("That page has moved or is no longer indexed.", "Use the Saudi topic hubs below to keep planning without losing momentum.", "Page not found")}
          <section class="content-card section">
            <div class="card-grid">
              {render_card("/saudi-destinations/", "Saudi Destinations", "Start with where to go across the Kingdom.", "")}
              {render_card("/saudi-travel-basics/", "Saudi Travel Basics", "Get the practical essentials before you book.", "")}
              {render_card("/saudi-itineraries-and-transport/", "Itineraries & Transport", "Figure out how long to stay and how to move.", "")}
            </div>
          </section>
        </section>
        """
    ).strip()


def render_article_page(page: dict, related_pages: list[dict]) -> str:
    hub = HUBS.get(page["hub"])
    breadcrumb_items = [("/", "Home")]
    if page["noindex"]:
        breadcrumb_items.append((None, "Archived guide"))
    else:
        breadcrumb_items.append((hub_href(page["hub"]), hub["title"]))
    breadcrumb_items.append((None, page["title"]))

    schema_items = [(BASE_URL + "/", "Home")]
    if not page["noindex"]:
        schema_items.append((full_url(page["hub"]), hub["title"]))
    schema_items.append((page["canonical"], page["title"]))

    related_html = "\n".join(
        f'<li><a href="{item["href"]}">{html.escape(item["title"])}</a><div class="muted">{html.escape(item["description"])}</div></li>'
        for item in related_pages
    )

    if page["noindex"] and page.get("archive_reason") == "duplicate" and page.get("preferred_slug"):
        archive_note = (
            '<div class="archive-note">This page remains available for reference, but we consolidated this search intent under '
            f'<a class="inline-link" href="/{page["preferred_slug"]}/">{html.escape(page["preferred_title"])}</a>.</div>'
        )
    elif page["noindex"]:
        archive_note = '<div class="archive-note">This guide is still available for reference, but it is no longer part of the site&apos;s primary indexed Saudi focus.</div>'
    else:
        archive_note = ""

    hub_note = (
        f'<p>Continue with the broader topic hub: <a class="inline-link" href="{hub_href(page["hub"])}">{hub["title"]}</a>.</p>'
        if not page["noindex"]
        else '<p>Use our Saudi-first hubs to continue planning with current indexed coverage.</p>'
    )

    return dedent(
        f"""
        <section class="page-shell">
          <div class="article-card">
            {breadcrumbs(breadcrumb_items)}
            <div class="eyebrow">{"Archived Gulf reference" if page["noindex"] else hub["title"]}</div>
            <h1>{html.escape(page["title"])}</h1>
            <div class="article-meta">
              <span>Updated {pretty_date(page["published"])}</span>
              <span>By {SITE_NAME} Editorial Team</span>
              <span>{"Noindex, follow" if page["noindex"] else "Indexable Saudi guide"}</span>
            </div>
            {archive_note}
            <div class="article-layout">
              <div class="article-body">
                {page["body"]}
              </div>
              <aside class="article-sidebar">
                <section class="sidebar-card">
                  <h2>Why trust this guide</h2>
                  <p>We publish Saudi-first travel content organised around real trip decisions rather than thin search variants.</p>
                  <p><a class="inline-link" href="/editorial-policy/">Read our editorial policy</a> for details on updates, archive handling, and corrections.</p>
                  {hub_note}
                </section>
                <section class="sidebar-card">
                  <h2>{"Next Saudi reads" if page["noindex"] else "Related planning guides"}</h2>
                  <ul class="link-list">
                    {related_html}
                  </ul>
                </section>
                <section class="sidebar-card">
                  <h2>Need a correction?</h2>
                  <p>Email <a class="inline-link" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> if transport, pricing, or travel requirements have changed.</p>
                </section>
              </aside>
            </div>
          </div>
        </section>
        """
    ).strip()


def article_schema(page: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": page["title"],
        "description": page["description"],
        "url": page["canonical"],
        "datePublished": iso_date(page["published"]),
        "dateModified": TODAY.isoformat(),
        "author": {"@type": "Organization", "name": f"{SITE_NAME} Editorial Team", "url": BASE_URL + "/editorial-policy/"},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": BASE_URL},
        "mainEntityOfPage": {"@type": "WebPage", "@id": page["canonical"]},
    }


def basic_page_schema(page_type: str, title: str, description: str, canonical: str) -> dict:
    schema_type = {
        "about": "AboutPage",
        "contact": "ContactPage",
        "editorial": "WebPage",
        "hub": "CollectionPage",
        "home": "WebSite",
        "404": "WebPage",
    }[page_type]
    schema = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "description": description,
        "url": canonical,
    }
    if page_type == "home":
        schema["publisher"] = {"@type": "Organization", "name": SITE_NAME, "url": BASE_URL}
    return schema


def render_document(head_html: str, body_html: str) -> str:
    return f"<!DOCTYPE html><html lang=\"en\">{head_html}{body_html}</html>"


def collect_pages() -> dict[str, dict]:
    pages: dict[str, dict] = {}
    for path in sorted(ROOT.rglob("index.html")):
        if "assets" in path.parts or "tools" in path.parts or "admin" in path.parts:
            continue
        slug = slug_from_path(path)
        if slug in RESERVED_PAGE_SLUGS:
            continue
        raw = read_source(path)
        title = parse_article_h1(raw) or parse_title(raw) or slug.replace("-", " ").title()
        body = parse_main_article_body(raw)
        cleaned = clean_article_body(body)
        published = parse_date(raw)
        noindex = bool(slug and (NON_SAUDI_PATTERN.search(slug) or NUMERIC_SUFFIX_PATTERN.search(slug)))
        is_article = path.name == "index.html"
        hub_slug = hub_for_slug(slug) if is_article and not noindex else "saudi-destinations"
        description = short_description(title, parse_meta_description(raw), cleaned)
        pages[slug] = {
            "slug": slug,
            "path": path,
            "raw": raw,
            "title": title,
            "body": cleaned,
            "published": published,
            "description": description,
            "canonical": full_url(slug),
            "href": "/" if not slug else f"/{slug}/",
            "noindex": noindex,
            "is_article": is_article,
            "hub": hub_slug,
            "secondary_hubs": supplementary_hubs_for_slug(slug) if is_article and not noindex else [],
            "tokens": Counter(tokenise_slug(slug)),
            "archive_reason": "off-focus" if noindex else "",
            "preferred_slug": "",
            "preferred_title": "",
        }
    slug_aliases = build_slug_aliases(pages)
    known_slugs = set(pages)
    for page in pages.values():
        page["body"] = repair_body_links(page["body"], known_slugs, slug_aliases)
        page["description"] = short_description(page["title"], page["description"], page["body"])
    return pages


def related_for(page: dict, pages: dict[str, dict], hub_articles: dict[str, list[dict]]) -> list[dict]:
    if page["noindex"]:
        return [
            {"href": hub_href("saudi-destinations"), "title": HUBS["saudi-destinations"]["title"], "description": HUBS["saudi-destinations"]["description"]},
            {"href": hub_href("saudi-travel-basics"), "title": HUBS["saudi-travel-basics"]["title"], "description": HUBS["saudi-travel-basics"]["description"]},
            {"href": hub_href("saudi-itineraries-and-transport"), "title": HUBS["saudi-itineraries-and-transport"]["title"], "description": HUBS["saudi-itineraries-and-transport"]["description"]},
        ]
    candidates = []
    for candidate in hub_articles[page["hub"]]:
        if candidate["slug"] == page["slug"]:
            continue
        overlap = sum((page["tokens"] & candidate["tokens"]).values())
        score = overlap * 10 + int(candidate["published"].strftime("%Y%m%d")) if candidate["published"] else overlap * 10
        candidates.append((score, candidate))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[:3]]


def rebuild_sitemap(indexable_pages: list[dict], hub_pages: list[dict]) -> None:
    entries = [
        {"loc": BASE_URL + "/", "lastmod": TODAY.isoformat(), "changefreq": "weekly", "priority": "1.0"},
        {"loc": BASE_URL + "/about/", "lastmod": TODAY.isoformat(), "changefreq": "monthly", "priority": "0.6"},
        {"loc": BASE_URL + "/contact/", "lastmod": TODAY.isoformat(), "changefreq": "monthly", "priority": "0.5"},
        {"loc": BASE_URL + "/editorial-policy/", "lastmod": TODAY.isoformat(), "changefreq": "monthly", "priority": "0.5"},
    ]
    entries.extend(
        {
            "loc": full_url(page["slug"]),
            "lastmod": (page["published"] or TODAY).isoformat(),
            "changefreq": "monthly",
            "priority": "0.8",
        }
        for page in hub_pages
    )
    entries.extend(
        {
            "loc": page["canonical"],
            "lastmod": (page["published"] or TODAY).isoformat(),
            "changefreq": "monthly",
            "priority": "0.7",
        }
        for page in indexable_pages
    )
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for entry in entries:
        xml.append(
            "<url>"
            f"<loc>{entry['loc']}</loc>"
            f"<lastmod>{entry['lastmod']}</lastmod>"
            f"<changefreq>{entry['changefreq']}</changefreq>"
            f"<priority>{entry['priority']}</priority>"
            "</url>"
        )
    xml.append("</urlset>")
    write(ROOT / "sitemap.xml", "\n".join(xml))


def rebuild_robots() -> None:
    robots = dedent(
        f"""
        User-agent: *
        Allow: /

        Sitemap: {BASE_URL}/sitemap.xml
        """
    ).strip()
    write(ROOT / "robots.txt", robots + "\n")


def build_hub_pages(pages: dict[str, dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    hub_articles: dict[str, list[dict]] = defaultdict(list)
    for page in pages.values():
        if page["is_article"] and not page["noindex"]:
            assigned_hubs = {page["hub"], *page.get("secondary_hubs", [])}
            for hub_slug in assigned_hubs:
                hub_articles[hub_slug].append(page)
    for hub_slug in hub_articles:
        hub_articles[hub_slug].sort(key=lambda item: item["published"] or date(2000, 1, 1), reverse=True)

    hub_page_records = []
    for hub_slug in INDEXABLE_HUB_ORDER:
        path = ROOT / hub_slug / "index.html"
        title = HUBS[hub_slug]["title"]
        description = HUBS[hub_slug]["description"]
        body = render_hub_page(hub_slug, hub_articles.get(hub_slug, []))
        schemas = [
            organization_schema(),
            basic_page_schema("hub", title, description, full_url(hub_slug)),
            breadcrumbs_schema([(BASE_URL + "/", "Home"), (full_url(hub_slug), title)]),
        ]
        document = render_document(
            page_head(title, description, full_url(hub_slug), "index,follow", "website", schemas),
            page_shell("template-hub", hub_slug, body, title),
        )
        write(path, document)
        hub_page_records.append(
            {
                "slug": hub_slug,
                "title": title,
                "description": description,
                "published": TODAY,
            }
        )
    return hub_articles, hub_page_records


def main() -> None:
    create_image_assets()
    write(ASSETS_DIR / "site.css", SITE_CSS + "\n")
    pages = collect_pages()
    duplicate_count = mark_duplicate_pages(pages)
    hub_articles, hub_page_records = build_hub_pages(pages)

    home_head = page_head(
        HOME_PAGE_TITLE,
        SITE_DESCRIPTION,
        BASE_URL + "/",
        "index,follow",
        "website",
        [organization_schema(), basic_page_schema("home", SITE_NAME, SITE_DESCRIPTION, BASE_URL + "/")],
    )
    home_document = render_document(home_head, page_shell("template-home", "", render_home(pages, hub_articles), SITE_NAME))
    write(ROOT / "index.html", home_document)

    about_body = render_about_page()
    about_document = render_document(
        page_head(
            "About",
            "Learn how Saudi Travel and Leisure approaches Saudi-first travel coverage, updates, and editorial focus.",
            BASE_URL + "/about/",
            "index,follow",
            "website",
            [
                organization_schema(),
                basic_page_schema("about", "About Saudi Travel and Leisure", "Saudi-first travel publication and editorial mission.", BASE_URL + "/about/"),
                breadcrumbs_schema([(BASE_URL + "/", "Home"), (BASE_URL + "/about/", "About")]),
            ],
        ),
        page_shell("template-static", None, about_body, "About"),
    )
    write(ROOT / "about" / "index.html", about_document)

    contact_body = render_contact_page()
    contact_document = render_document(
        page_head(
            "Contact",
            "Contact Saudi Travel and Leisure for corrections, editorial updates, and partnership enquiries.",
            BASE_URL + "/contact/",
            "index,follow",
            "website",
            [
                organization_schema(),
                basic_page_schema("contact", "Contact Saudi Travel and Leisure", "Editorial contact and corrections workflow.", BASE_URL + "/contact/"),
                breadcrumbs_schema([(BASE_URL + "/", "Home"), (BASE_URL + "/contact/", "Contact")]),
            ],
        ),
        page_shell("template-static", None, contact_body, "Contact"),
    )
    write(ROOT / "contact" / "index.html", contact_document)

    editorial_body = render_editorial_page()
    editorial_document = render_document(
        page_head(
            "Editorial policy",
            "Read how Saudi Travel and Leisure handles editorial scope, updates, archive decisions, and corrections.",
            BASE_URL + "/editorial-policy/",
            "index,follow",
            "website",
            [
                organization_schema(),
                basic_page_schema("editorial", "Editorial policy", "Saudi Travel and Leisure editorial policy and update standards.", BASE_URL + "/editorial-policy/"),
                breadcrumbs_schema([(BASE_URL + "/", "Home"), (BASE_URL + "/editorial-policy/", "Editorial policy")]),
            ],
        ),
        page_shell("template-static", None, editorial_body, "Editorial policy"),
    )
    write(ROOT / "editorial-policy" / "index.html", editorial_document)

    not_found_document = render_document(
        page_head(
            "Page not found",
            "The page you requested has moved or is no longer part of the primary Saudi Travel and Leisure index.",
            BASE_URL + "/404.html",
            "noindex,follow",
            "website",
            [organization_schema(), basic_page_schema("404", "Page not found", "Saudi Travel and Leisure 404 page.", BASE_URL + "/404.html")],
        ),
        page_shell("template-static", None, render_404_page(), "Page not found"),
    )
    write(ROOT / "404.html", not_found_document)

    indexable_articles = []
    for page in pages.values():
        related = related_for(page, pages, hub_articles)
        robots = "noindex,follow" if page["noindex"] else "index,follow"
        schemas = [
            organization_schema(),
            article_schema(page),
            breadcrumbs_schema(
                [(BASE_URL + "/", "Home")]
                + ([] if page["noindex"] else [(full_url(page["hub"]), HUBS[page["hub"]]["title"])])
                + [(page["canonical"], page["title"])]
            ),
        ]
        document = render_document(
            page_head(page["title"], page["description"], page["canonical"], robots, "article", schemas),
            page_shell("template-article", page["hub"] if not page["noindex"] else None, render_article_page(page, related), page["title"]),
        )
        write(page["path"], document)
        if not page["noindex"]:
            indexable_articles.append(page)

    rebuild_sitemap(indexable_articles, hub_page_records)
    rebuild_robots()
    print(
        f"Rebuilt {len(indexable_articles)} indexable Saudi article pages, "
        f"{len([page for page in pages.values() if page['archive_reason'] == 'off-focus'])} off-focus archive pages, "
        f"and {duplicate_count} duplicate-intent archive pages."
    )


if __name__ == "__main__":
    main()
