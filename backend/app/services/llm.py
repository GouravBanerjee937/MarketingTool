"""LLM-backed features: competitor discovery/analysis and content generation.

Provider-isolated: this module is the only place that talks to an LLM, so
swapping providers is a one-file change. It targets a **Qwen** model served by
**Ollama** (``/api/chat``) — no API key required; the endpoint and model are set
via ``OLLAMA_URL`` / ``OLLAMA_MODEL`` in ``backend/.env``.

Every prompt sent from here is documented in ``backend/PROMPTS.md`` — keep that
file in sync whenever a system/user prompt below changes.
"""
import json
import re

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services import run_log


class LLMNotConfigured(RuntimeError):
    """Raised when the LLM endpoint is not configured."""


# --- Ollama transport --------------------------------------------------

# Ollama honours a `format:"json"` grammar that guarantees syntactically valid
# JSON; we still spell out the target schema in the prompt so the *structure* is
# right. Qwen3.5 is a thinking model — `think:false` keeps replies fast and free
# of <think> preamble.
async def _chat(
    *, system: str, user: str, json_mode: bool = False, temperature: float = 0.4
) -> str:
    settings = get_settings()
    if not settings.ollama_url:
        raise LLMNotConfigured(
            "OLLAMA_URL is not set. Add it to backend/.env to enable this feature."
        )

    body: dict = {
        "model": settings.ollama_model,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature},
    }
    if json_mode:
        body["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(settings.ollama_url, json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        raise LLMNotConfigured(f"Ollama request failed: {e}") from e

    content = (data.get("message") or {}).get("content") or ""
    run_log.record(system=system, user=user, response=content)
    return content


def _loads(text: str) -> dict:
    """Parse a JSON object out of a model reply, tolerating stray fences/prose."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start : end + 1]
    return json.loads(t or "{}")


def _json_instruction(example: dict) -> str:
    """Instruction appended to a system prompt to force example-shaped JSON.

    We give a concrete *example* of the target shape (not a JSON Schema): small
    local models reproduce an example reliably but tend to echo schema meta-keys
    (``type``/``properties``/``required``) when handed a raw JSON Schema.
    """
    return (
        "\n\nRespond with ONLY a single valid JSON object with EXACTLY this shape "
        "— same keys, with the values replaced by your answer. Keep the arrays but "
        "use as many items as appropriate. Use double quotes on every key and "
        "string value. Output no markdown, no code fences, no extra keys and no "
        "commentary:\n" + json.dumps(example)
    )


# Concrete output examples (shape only) handed to the model per feature.
_EXAMPLE_COMPETITORS = {
    "competitors": [
        {"name": "Example Co", "website": "example.com",
         "description": "one sentence on what they do and why they compete"}
    ]
}
_EXAMPLE_THEMES = {
    "themes": [
        {"title": "short specific title",
         "angle": "one-to-two sentence angle explaining the idea"}
    ]
}
# Qwen produces the analysis up to social presence (features come from OpenAI).
_EXAMPLE_ANALYSIS = {
    "name": "Example Co",
    "revenue_usd": "$1.2B (FY2025)",
    "revenue_inr": "₹10,000 crore",
    "revenue_source": "publisher or NA",
    "users": "2M businesses",
    "users_source": "publisher or NA",
    "moats": ["primary advantage 1", "primary advantage 2"],
    "social": {"instagram": True, "blog": True, "facebook": True, "x": True,
               "thirdparty": "YouTube or NA"},
}

# OpenAI (ChatGPT) produces the features-marketed part.
_EXAMPLE_FEATURES = {
    "features": [
        {"feature": "feature name",
         "sample_marketing": "one-line marketing message in their style",
         "source": "product/landing page URL or NA"}
    ],
}


_COMPETITOR_SCHEMA = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "website", "description"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["competitors"],
    "additionalProperties": False,
}

_SYSTEM_TAILORED = (
    "You are a market-research analyst. Given a brand's strategy, target personas, "
    "and the regions it wants to operate in, identify real, currently-operating "
    "competitors this brand would realistically face given its positioning and "
    "those personas. Return only genuine companies you are confident exist. For "
    "each: a short website domain (or empty string if unsure) and a one-sentence "
    "description of what they do and why they compete."
)

_SYSTEM_GENERAL = (
    "You are a market-research analyst. Identify the major, well-known competitors "
    "and market leaders in this brand's overall product category / industry that "
    "operate in the given regions — the broad competitive set, NOT narrowed to the "
    "specific personas. Return only genuine companies you are confident exist. For "
    "each: a short website domain (or empty string if unsure) and a one-sentence "
    "description of what they do and why they compete."
)


def _persona_line(p) -> str:
    bits = [p.name]
    meta = [x for x in (p.user_type, p.business_size, p.region) if x]
    if meta:
        bits.append("(" + ", ".join(meta) + ")")
    if p.pain_points:
        bits.append(f"— pain: {p.pain_points}")
    return " ".join(bits)


async def fetch_competitors(
    *,
    brand_name: str,
    vision: str | None,
    goal: str | None,
    moat: str | None,
    personas: list,
    regions: list[str],
    exclude_names: set[str],
    general: bool = False,
    limit: int = 8,
) -> list[dict]:
    persona_text = "\n".join(f"- {_persona_line(p)}" for p in personas) or "- (none provided)"
    region_text = ", ".join(regions) if regions else "(no regions specified)"
    exclude_text = ", ".join(sorted(exclude_names)) if exclude_names else "(none)"

    ask = (
        f"List up to {limit} of the biggest, most established competitors in this "
        f"brand's category operating in those regions."
        if general
        else f"Suggest up to {limit} competitors this brand would realistically "
        f"face in those regions."
    )
    user = f"""Brand: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / edge: {moat or "—"}
Operating region(s): {region_text}

Target personas:
{persona_text}

{ask} Exclude these already-listed competitors: {exclude_text}."""

    system = (_SYSTEM_GENERAL if general else _SYSTEM_TAILORED) + _json_instruction(_EXAMPLE_COMPETITORS)
    content = await _chat(system=system, user=user, json_mode=True, temperature=0.3)
    items = _loads(content).get("competitors", [])

    cleaned: list[dict] = []
    seen = {n.lower() for n in exclude_names}
    for it in items:
        name = (it.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        cleaned.append(
            {
                "name": name,
                "website": (it.get("website") or "").strip() or None,
                "description": (it.get("description") or "").strip() or None,
            }
        )
    return cleaned


_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "revenue_usd": {"type": "string"},
        "revenue_inr": {"type": "string"},
        "revenue_source": {"type": "string"},
        "users": {"type": "string"},
        "users_source": {"type": "string"},
        "moats": {"type": "array", "items": {"type": "string"}},
        "social": {
            "type": "object",
            "properties": {
                "instagram": {"type": "boolean"},
                "blog": {"type": "boolean"},
                "facebook": {"type": "boolean"},
                "x": {"type": "boolean"},
                "thirdparty": {"type": "string"},
            },
            "required": ["instagram", "blog", "facebook", "x", "thirdparty"],
            "additionalProperties": False,
        },
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature": {"type": "string"},
                    "sample_marketing": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["feature", "sample_marketing", "source"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "name", "revenue_usd", "revenue_inr", "revenue_source",
        "users", "users_source", "moats", "social", "features",
    ],
    "additionalProperties": False,
}

_ANALYSIS_SYSTEM = (
    "You are a competitive-intelligence analyst. Produce a structured analysis of "
    "the given competitor from your own knowledge (you do not have live web "
    "access).\n"
    "- revenue: the company's latest known annual revenue, expressed as THE SAME "
    "figure in both US dollars (revenue_usd, e.g. '$9.4B (FY2025)') and Indian "
    "rupees (revenue_inr, e.g. '₹78,000 crore') — convert using a recent exchange "
    "rate. If you know the publisher/source, put it in revenue_source, else 'NA'.\n"
    "- users: the best known figure/estimate of users or customers; put any known "
    "publisher/source in users_source, else 'NA'.\n"
    "- If a figure is genuinely unknown to you, set that field and its source to "
    "the exact string \"NA\". Never invent precise numbers.\n"
    "- moats: up to 5 primary defensible advantages (most important first).\n"
    "- social: true/false for a known presence on instagram, blog, facebook, x "
    "(twitter); thirdparty = name of any other notable channel (YouTube, LinkedIn, "
    "TikTok, …) or \"NA\".\n"
    "Keep revenue and users as clean values with no inline citation markup — the "
    "citation belongs only in the *_source fields."
)

# OpenAI (ChatGPT) — features + top-3 marketing copy, with REAL links via web search.
_FEATURES_SCHEMA = {
    "type": "object",
    "properties": {
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature": {"type": "string"},
                    "sample_marketing": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["feature", "sample_marketing", "source"],
                "additionalProperties": False,
            },
        },
        "marketing_copy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "copy": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["copy", "source"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["features", "marketing_copy"],
    "additionalProperties": False,
}

_FEATURES_SYSTEM = (
    "You are a competitive-intelligence analyst WITH WEB SEARCH. Search the web for "
    "the given company and return two things:\n"
    "1) features: 5-8 key features/products it markets. For each: a short feature "
    "name, a one-line 'sample_marketing' message in that company's marketing "
    "style, and 'source' = the actual URL you found (a working product/landing/"
    "pricing/docs page).\n"
    "2) marketing_copy: the company's TOP 3 real marketing copy lines — taglines, "
    "ad headlines or hero-section copy actually used by the brand. For each: the "
    "'copy' text and 'source' = the URL where you found it.\n"
    "Use ONLY URLs you actually found via search — never guess, pattern-complete, "
    "or invent a URL. If you cannot find a real source, set that source to 'NA'."
)


# --- Content generation (stage 4) --------------------------------------

# Posting guidelines the model must respect per target platform.
_PLATFORM_GUIDELINES = {
    "whatsapp": (
        "WhatsApp Business message. Warm, personal, 1:1 conversational tone. Keep "
        "it short (ideally under ~700 characters). Open with a hook line, use short "
        "line breaks (NO markdown headings or tables), emojis are fine in "
        "moderation, and end with ONE clear call to action or link. Avoid ALL-CAPS "
        "and spammy phrasing."
    ),
    "rcs": (
        "RCS Business Message. A short, branded rich message: a bold title line, "
        "1-3 short benefit-led paragraphs, and a suggested action/button label such "
        "as 'Get started'. Concise, friendly and mobile-first."
    ),
    "google ad": (
        "Google Responsive Search Ad. Output EXACTLY as labelled lines: 3-5 "
        "'Headline N:' lines (each <= 30 characters) and 2-4 'Description N:' lines "
        "(each <= 90 characters). Benefit-led, keyword-relevant, each with a clear "
        "CTA. No emojis and no excessive punctuation."
    ),
}


def _platform_guideline(platform: str) -> str:
    key = platform.strip().lower()
    if key == "google ads":
        key = "google ad"
    if key in _PLATFORM_GUIDELINES:
        return _PLATFORM_GUIDELINES[key]
    return (
        f"Follow the standard best practices and format conventions for {platform}: "
        "match the tone, length and structure typical of high-performing content "
        "there, and end with a clear call to action."
    )


def _length_rule(form: str) -> str:
    return (
        "LONG-FORM: develop the idea fully with a clear structure (headline, "
        "sections / paragraphs), depth and a strong close."
        if form == "long"
        else "SHORT-FORM: tight, punchy and scannable — every line earns its place."
    )


def _persona_block(personas: list) -> str:
    return "\n".join(f"- {_persona_line(p)}" for p in personas) or "- (none captured)"


def _competitor_block(competitors: list[dict]) -> str:
    lines = []
    for c in competitors:
        tag = " (primary)" if c.get("is_primary") else ""
        moats = ", ".join((c.get("moats") or [])[:3])
        extra = f" — strengths: {moats}" if moats else ""
        lines.append(f"- {c['name']}{tag}{extra}")
    return "\n".join(lines) or "- (none shortlisted)"


def _inspiration_block(inspiration: str | None, liked_features: list[str] | None) -> str:
    """Optional 'inspiration brand' + liked competitor features to weave in."""
    parts = []
    if inspiration and inspiration.strip():
        parts.append(
            f"Take inspiration from how {inspiration.strip()} approaches its marketing "
            "(tone, angles, positioning) — adapt it to this brand, do NOT copy."
        )
    feats = [f.strip() for f in (liked_features or []) if f and f.strip()]
    if feats:
        parts.append(
            "Highlight / echo these liked competitor features where they fit: "
            + ", ".join(feats) + "."
        )
    return "\n\nINSPIRATION\n" + "\n".join(parts) if parts else ""


# --- Brand Voice: writing-style samples + banned words -----------------

def _voice_block(voice_samples: list[str] | None) -> str:
    """Render brand writing samples so the model can mimic tone/style."""
    samples = [s.strip() for s in (voice_samples or []) if s and s.strip()]
    if not samples:
        return ""
    # Cap each sample so a few long docs don't blow the context window.
    joined = "\n\n---\n".join(s[:2000] for s in samples[:6])
    return (
        "\n\nBRAND VOICE SAMPLES (examples of how this brand writes its external "
        "posts — match this tone, vocabulary, rhythm and formatting; do NOT copy "
        "them verbatim):\n" + joined
    )


def _banned_line(banned_words: list[str] | None) -> str:
    words = [w.strip() for w in (banned_words or []) if w and w.strip()]
    if not words:
        return ""
    return (
        "\n\nBANNED WORDS — these words (and their obvious variants) must NEVER "
        "appear anywhere in your output. Rephrase to avoid them entirely: "
        + ", ".join(words)
    )


def _find_banned(text: str, banned_words: list[str] | None) -> list[str]:
    """Return the banned words that actually appear in ``text`` (whole word, case-insensitive)."""
    hits: list[str] = []
    for w in banned_words or []:
        w = (w or "").strip()
        if not w:
            continue
        pattern = r"(?<!\w)" + re.escape(w) + r"(?!\w)"
        if re.search(pattern, text or "", re.IGNORECASE):
            hits.append(w)
    return hits


_THEMES_SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "angle": {"type": "string"},
                },
                "required": ["title", "angle"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["themes"],
    "additionalProperties": False,
}

_THEMES_SYSTEM = (
    "You are a senior brand marketing strategist. Given a brand's strategy, its "
    "target personas and how it is differentiated from competitors, propose "
    "distinct, ready-to-develop content ideas (themes) for a specific format and "
    "platform. The themes are FOR the given brand ONLY — each must promote THAT "
    "brand; competitors and any inspiration brand are reference only, never the "
    "subject. Each theme has a short, specific title and a one-to-two sentence "
    "angle explaining what it covers and why it resonates with the personas or "
    "sets the brand apart. Make the themes genuinely different from one another "
    "and appropriate for the platform's guidelines. Never invent statistics."
)


async def suggest_content_themes(
    *,
    brand_name: str,
    vision: str | None,
    goal: str | None,
    moat: str | None,
    personas: list,
    competitors: list[dict],
    form: str,
    content_format: str,
    platform: str,
    voice_samples: list[str] | None = None,
    banned_words: list[str] | None = None,
    inspiration: str | None = None,
    liked_features: list[str] | None = None,
    count: int = 5,
) -> list[dict]:
    user = f"""Propose {count} distinct content themes for a {content_format} to be published on {platform}, for the brand below.

BRAND
Name: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / differentiation: {moat or "—"}

TARGET PERSONAS
{_persona_block(personas)}

COMPETITIVE CONTEXT (differentiate against these where relevant)
{_competitor_block(competitors)}

FORMAT: {content_format}
LENGTH: {_length_rule(form)}
PLATFORM GUIDELINES ({platform}): {_platform_guideline(platform)}{_voice_block(voice_samples)}{_banned_line(banned_words)}{_inspiration_block(inspiration, liked_features)}

Return {count} clearly distinct themes, each with a short specific title and a one-to-two sentence angle."""

    system = _THEMES_SYSTEM + _json_instruction(_EXAMPLE_THEMES)
    content = await _chat(system=system, user=user, json_mode=True, temperature=0.6)
    themes = _loads(content).get("themes", [])
    cleaned = [
        {"title": (t.get("title") or "").strip(), "angle": (t.get("angle") or "").strip()}
        for t in themes
        if (t.get("title") or "").strip()
    ]
    # Hard gate: drop any theme that still slipped a banned word into title/angle.
    if banned_words:
        cleaned = [
            t
            for t in cleaned
            if not _find_banned(f"{t['title']} {t['angle']}", banned_words)
        ]
    return cleaned


_CONTENT_SYSTEM = (
    "You are a senior brand marketing copywriter. You write publish-ready content "
    "grounded in the brand's strategy, its target personas, and how it is "
    "differentiated from its competitors. The content is FOR and ABOUT the given "
    "brand ONLY — promote THAT brand, name it, speak in its voice. NEVER write the "
    "content as, for, or promoting a competitor or the inspiration brand; those are "
    "reference only (for angle/tone/positioning). You strictly follow the target "
    "platform's guidelines and the requested format and length, make specific and "
    "credible claims (never invent statistics), and return ONLY the content itself "
    "— ready to paste — using light markdown where the platform allows it. No "
    "preamble, notes or explanations."
)


async def generate_content(
    *,
    brand_name: str,
    vision: str | None,
    goal: str | None,
    moat: str | None,
    personas: list,
    competitors: list[dict],
    form: str,
    content_format: str,
    platform: str,
    theme_title: str | None = None,
    theme_angle: str | None = None,
    voice_samples: list[str] | None = None,
    banned_words: list[str] | None = None,
    inspiration: str | None = None,
    liked_features: list[str] | None = None,
) -> str:
    theme_line = ""
    if theme_title:
        angle = f" — {theme_angle}" if theme_angle else ""
        theme_line = f"\nCHOSEN THEME: {theme_title}{angle}\nWrite specifically to this theme."

    user = f"""Write a {content_format} for the brand below, to be published on {platform}.

BRAND
Name: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / differentiation: {moat or "—"}

TARGET PERSONAS
{_persona_block(personas)}

COMPETITIVE CONTEXT (differentiate against these where relevant)
{_competitor_block(competitors)}

FORMAT: {content_format}
LENGTH: {_length_rule(form)}
PLATFORM GUIDELINES ({platform}): {_platform_guideline(platform)}{_voice_block(voice_samples)}{_banned_line(banned_words)}{_inspiration_block(inspiration, liked_features)}{theme_line}

Write the {content_format} now. Return only the content, ready to publish."""

    content = (
        await _chat(system=_CONTENT_SYSTEM, user=user, json_mode=False, temperature=0.7)
    ).strip()

    # Hard gate on banned words: if any slipped through, ask for one clean rewrite.
    hits = _find_banned(content, banned_words)
    if hits:
        fix_user = (
            f"{user}\n\nYour previous draft used these BANNED words: "
            f"{', '.join(hits)}. Rewrite the {content_format} so NONE of the banned "
            "words (or their variants) appear, keeping the same meaning, tone and "
            "format. Return only the content."
        )
        retry = (
            await _chat(
                system=_CONTENT_SYSTEM, user=fix_user, json_mode=False, temperature=0.5
            )
        ).strip()
        # Keep the rewrite only if it is actually cleaner.
        if retry and not _find_banned(retry, banned_words):
            content = retry
    return content


async def _openai_extras(
    *, name: str, website: str | None, description: str | None
) -> dict:
    """Features marketed + top-3 marketing copy — generated by OpenAI (ChatGPT web
    search). Returns {"features": [...], "marketing_copy": [...]}."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMNotConfigured(
            "OPENAI_API_KEY is not set — features/marketing copy use ChatGPT. "
            "Add it to backend/.env to enable it."
        )
    user = (
        f"Company: {name}\nWebsite: {website or 'unknown'}\n"
        f"Context: {description or '—'}\n\n"
        "Search the web for (1) the key features this company markets — each with a "
        "one-line sample marketing message in their style and the REAL page URL — "
        "and (2) its top 3 real marketing copy lines/taglines with the URL where "
        "each is found. Use NA for any source you can't find."
    )
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.responses.create(
        model=settings.openai_model,
        tools=[{"type": "web_search"}],
        input=[
            {"role": "system", "content": _FEATURES_SYSTEM},
            {"role": "user", "content": user},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "competitor_extras",
                "schema": _FEATURES_SCHEMA,
                "strict": True,
            }
        },
    )
    content = resp.output_text or "{}"
    run_log.record(system=_FEATURES_SYSTEM, user=user, response=content)  # capture for the report
    data = json.loads(content)

    features = []
    for f in data.get("features", []):
        feat = (f.get("feature") or "").strip()
        if not feat:
            continue
        features.append({
            "feature": feat,
            "sample_marketing": (f.get("sample_marketing") or "").strip(),
            "source": _clean_url((f.get("source") or "NA").strip() or "NA"),
        })

    marketing_copy = []
    for c in data.get("marketing_copy", [])[:3]:
        copy = (c.get("copy") or "").strip()
        if not copy:
            continue
        marketing_copy.append({
            "copy": copy,
            "source": _clean_url((c.get("source") or "NA").strip() or "NA"),
        })

    return {"features": features, "marketing_copy": marketing_copy}


def _ad_library_links(name: str, website: str | None) -> dict:
    """Deterministic links to public ad libraries for this competitor (no LLM)."""
    from urllib.parse import quote_plus

    q = quote_plus(name)
    return {
        "meta": (
            "https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
            f"&country=ALL&q={q}&search_type=keyword_unordered"
        ),
        "google": f"https://adstransparency.google.com/?region=anywhere&query={q}",
        "playstore": f"https://play.google.com/store/search?q={q}&c=apps",
    }


async def _fetch_og_image(page_url: str) -> str | None:
    """Fetch a page and return its og:image (or twitter:image) URL, resolved."""
    from urllib.parse import urljoin

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        ) as client:
            html = (await client.get(page_url)).text
    except Exception:  # noqa: BLE001
        return None
    for prop in ("og:image", "twitter:image", "og:image:url"):
        m = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I,
        ) or re.search(
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
            html, re.I,
        )
        if m:
            return urljoin(page_url, m.group(1).strip())
    return None


async def _loads_as_image(client: httpx.AsyncClient, url: str) -> bool:
    """True only if the URL returns a real image (HTTP 200 + image/* content-type)."""
    try:
        r = await client.get(url)
    except Exception:  # noqa: BLE001
        return False
    return r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")


async def _fetch_feature_image(page_url: str, hint: str | None = None) -> str | None:
    """Return a REAL content image from the page that best illustrates the feature:
    scans <img>/srcset, filters out logos/icons/svg, ranks by the feature name, and
    only falls back to og:image if no content image is found."""
    import html as _html
    from urllib.parse import urljoin

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        ) as client:
            html = (await client.get(page_url)).text
    except Exception:  # noqa: BLE001
        return None

    candidates: list[tuple[str, str]] = []
    for tag in re.findall(r"<img[^>]+>", html, re.I):
        src = None
        for attr in ("data-src", "data-lazy-src", "src"):
            m = re.search(rf'{attr}=["\']([^"\']+)["\']', tag, re.I)
            if m:
                src = m.group(1)
                break
        if not src:
            m = re.search(r'srcset=["\']([^"\']+)["\']', tag, re.I)
            if m:  # take the last (largest) entry of the srcset
                src = m.group(1).split(",")[-1].strip().split(" ")[0]
        if not src:
            continue
        alt = ""
        am = re.search(r'alt=["\']([^"\']*)["\']', tag, re.I)
        if am:
            alt = am.group(1)
        candidates.append((urljoin(page_url, _html.unescape(src.strip())), alt))

    _BAD = ("logo", "icon", "sprite", "favicon", "avatar", "badge", "pixel",
            "1x1", "spacer", "loader", "placeholder", "blank")

    def ok(url: str) -> bool:
        u = url.lower()
        if not u.startswith("http") or u.startswith("data:") or u.endswith(".svg"):
            return False
        return not any(b in u for b in _BAD)

    good = [(u, a) for (u, a) in candidates if ok(u)]
    if hint:
        words = [w.lower() for w in re.findall(r"\w+", hint) if len(w) > 2]
        good.sort(
            key=lambda it: sum(1 for w in words if w in (it[0] + " " + it[1]).lower()),
            reverse=True,
        )
    # Return the first candidate that ACTUALLY loads as an image, so the UI never
    # commits to a broken URL (e.g. a homepage's dynamic og:image that 404s and
    # leaves the picture blank — the caller can then fall back to another page).
    async with httpx.AsyncClient(
        timeout=8.0, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    ) as client:
        for url, _alt in good[:8]:
            if await _loads_as_image(client, url):
                return url
        og = await _fetch_og_image(page_url)
        if og and await _loads_as_image(client, og):
            return og
    return None


async def _marketing_image(features: list[dict], website: str | None) -> dict | None:
    """Pick a real marketing image that illustrates one of the listed features:
    the og:image of a feature's source page (fallback: the homepage)."""
    for f in features:
        src = f.get("source") or ""
        if src.startswith("http"):
            img = await _fetch_og_image(src)
            if img:
                return {"image": img, "feature": f.get("feature"), "page": src}
    if website:
        home = website if website.startswith("http") else f"https://{website}"
        img = await _fetch_og_image(home)
        if img:
            return {"image": img, "feature": None, "page": home}
    return None


# Tracking params that search tools tack on (Bing/Google/etc.) — strip them so
# the source URL is the clean canonical page.
_TRACKING_PARAMS = {
    "msockid", "gclid", "fbclid", "mc_cid", "mc_eid", "yclid", "_hsenc", "_hsmi",
}


def _clean_url(url: str) -> str:
    if not url or not url.startswith("http"):
        return url
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    try:
        parts = urlsplit(url)
        kept = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))
    except Exception:  # noqa: BLE001
        return url


async def analyze_competitor(
    *, name: str, website: str | None, description: str | None
) -> dict:
    # Qwen: analysis up to social media presence.
    user = f"""Competitor to analyze: {name}
Website: {website or "unknown"}
Known context: {description or "—"}

Using your own knowledge, give this company's most recent known annual revenue
and its number of users/customers, citing a source for each where you know one.
Produce the structured analysis up to social presence. Use "NA" only when a
figure is genuinely unknown to you."""

    system = _ANALYSIS_SYSTEM + _json_instruction(_EXAMPLE_ANALYSIS)
    content = await _chat(system=system, user=user, json_mode=True, temperature=0.2)
    result = _loads(content)

    # OpenAI (ChatGPT web search): features marketed + top-3 marketing copy.
    try:
        extras = await _openai_extras(name=name, website=website, description=description)
        result["features"] = extras["features"]
        result["marketing_copy"] = extras["marketing_copy"]
    except Exception:  # noqa: BLE001 — analysis still returns; these stay empty
        result.setdefault("features", [])
        result.setdefault("marketing_copy", [])

    # Deterministic ad-library links (Meta / Google / Play Store) — no LLM.
    result["ad_libraries"] = _ad_library_links(name, website)

    # Marketing image: og:image of one listed feature's page (real, illustrates it).
    try:
        result["marketing_image"] = await _marketing_image(result.get("features") or [], website)
    except Exception:  # noqa: BLE001
        result["marketing_image"] = None
    return result
