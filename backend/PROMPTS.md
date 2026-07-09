# AIMark — LLM Prompts

Every prompt AIMark sends to the LLM. **Single source of truth for prompt review.**

- All calls live in [`app/services/llm.py`](app/services/llm.py) — the only module that talks to the LLM.
- Provider: **Qwen served by Ollama** (`POST /api/chat`). Endpoint `OLLAMA_URL`, model `OLLAMA_MODEL` (default `qwen3.5:9b`), set in `backend/.env`. No API key.
- Every request sends `think: false` (Qwen is a thinking model — this keeps replies fast and free of `<think>` preamble) and `stream: false`.
- `{curly}` = values interpolated at call time. This file mirrors the code — **update it whenever a prompt in `llm.py` changes.**

## How structured (JSON) output is forced

The competitor, theme and analysis calls need JSON. Two things are combined:

1. The request sets `format: "json"` (Ollama's grammar mode → syntactically valid JSON).
2. The **system prompt** has this instruction appended (`_json_instruction`), where `{example}` is a concrete example object (NOT a JSON Schema — a small local model reproduces an example reliably but echoes schema meta-keys when handed a raw schema):

```
Respond with ONLY a single valid JSON object with EXACTLY this shape — same keys, with the values replaced by your answer. Keep the arrays but use as many items as appropriate. Use double quotes on every key and string value. Output no markdown, no code fences, no extra keys and no commentary:
{example}
```

The examples (`{example}`) used per call:

- **Competitors** — `{"competitors": [{"name": "Example Co", "website": "example.com", "description": "one sentence on what they do and why they compete"}]}`
- **Themes** — `{"themes": [{"title": "short specific title", "angle": "one-to-two sentence angle explaining the idea"}]}`
- **Analysis** — `{"name": "Example Co", "revenue_usd": "$1.2B (FY2025)", "revenue_inr": "₹10,000 crore", "revenue_source": "publisher or NA", "users": "2M businesses", "users_source": "publisher or NA", "moats": ["primary advantage 1", "primary advantage 2"], "social": {"instagram": true, "blog": true, "facebook": true, "x": true, "thirdparty": "YouTube or NA"}, "features": [{"feature": "feature name", "sample_marketing": "one-line marketing message in their style", "source": "product/landing page or NA"}]}`

## Shared prompt fragments

**`_persona_line`** — how each persona is rendered into one line (bracketed meta and the `— pain:` part are omitted when empty):

```
{name} ({user_type}, {business_size}, {region}) — pain: {pain_points}
```

**`{length_rule}`**
- `long` → `LONG-FORM: develop the idea fully with a clear structure (headline, sections / paragraphs), depth and a strong close.`
- `short` → `SHORT-FORM: tight, punchy and scannable — every line earns its place.`

**`{comp_text}`** (`_competitor_block`) — one line per *considered* competitor: `- {name} (primary) — strengths: {top 3 moats}`; falls back to `- (none shortlisted)`.

**`{platform_guideline}`** — looked up by lowercased platform name; unknown platforms get the fallback:

| Platform | Guideline |
|---|---|
| `whatsapp` | WhatsApp Business message. Warm, personal, 1:1 conversational tone. Keep it short (ideally under ~700 characters). Open with a hook line, use short line breaks (NO markdown headings or tables), emojis are fine in moderation, and end with ONE clear call to action or link. Avoid ALL-CAPS and spammy phrasing. |
| `rcs` | RCS Business Message. A short, branded rich message: a bold title line, 1-3 short benefit-led paragraphs, and a suggested action/button label such as 'Get started'. Concise, friendly and mobile-first. |
| `google ad` (also `google ads`) | Google Responsive Search Ad. Output EXACTLY as labelled lines: 3-5 'Headline N:' lines (each <= 30 characters) and 2-4 'Description N:' lines (each <= 90 characters). Benefit-led, keyword-relevant, each with a clear CTA. No emojis and no excessive punctuation. |
| *(other / custom)* | Follow the standard best practices and format conventions for {platform}: match the tone, length and structure typical of high-performing content there, and end with a clear call to action. |

### Brand Voice fragments (themes + content only)

Injected into the theme and content **user** prompts when the brand has a saved Brand Voice.

**`{voice_block}`** (`_voice_block`) — present only when there are samples; up to 6 samples, each capped at 2000 chars, joined by `\n\n---\n`:

```
BRAND VOICE SAMPLES (examples of how this brand writes its external posts — match this tone, vocabulary, rhythm and formatting; do NOT copy them verbatim):
{sample 1}
---
{sample 2}
```

**`{banned_line}`** (`_banned_line`) — present only when there are banned words:

```
BANNED WORDS — these words (and their obvious variants) must NEVER appear anywhere in your output. Rephrase to avoid them entirely: {comma-separated words}
```

After generation, banned words are also **enforced in code** (`_find_banned`, whole-word/case-insensitive): themes containing one are dropped; content triggers one corrective rewrite (see §5).

---

## 1. Fetch competitors — Tailored

- **Function:** `fetch_competitors(..., general=False)`
- **Endpoint:** `POST /api/brands/{id}/competitors/fetch?kind=tailored`
- **Transport:** `chat` · `format:"json"` · temperature `0.3` · Output parsed as `competitors[] = {name, website, description}`

**System** (`_SYSTEM_TAILORED` + the JSON instruction from the top of this file)
```
You are a market-research analyst. Given a brand's strategy, target personas, and the regions it wants to operate in, identify real, currently-operating competitors this brand would realistically face given its positioning and those personas. Return only genuine companies you are confident exist. For each: a short website domain (or empty string if unsure) and a one-sentence description of what they do and why they compete.
```

**User**
```
Brand: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / edge: {moat or "—"}
Operating region(s): {region_text}

Target personas:
{persona_text}

Suggest up to {limit} competitors this brand would realistically face in those regions. Exclude these already-listed competitors: {exclude_text}.
```

---

## 2. Fetch competitors — General

- **Function:** `fetch_competitors(..., general=True)`
- **Endpoint:** `POST /api/brands/{id}/competitors/fetch?kind=general`
- **Transport:** `chat` · `format:"json"` · temperature `0.3` · same output shape

**System** (`_SYSTEM_GENERAL` + JSON instruction)
```
You are a market-research analyst. Identify the major, well-known competitors and market leaders in this brand's overall product category / industry that operate in the given regions — the broad competitive set, NOT narrowed to the specific personas. Return only genuine companies you are confident exist. For each: a short website domain (or empty string if unsure) and a one-sentence description of what they do and why they compete.
```

**User** — same template as Tailored, but the instruction line is:
```
List up to {limit} of the biggest, most established competitors in this brand's category operating in those regions. Exclude these already-listed competitors: {exclude_text}.
```

---

## 3. Analyze competitor

- **Function:** `analyze_competitor(...)`
- **Endpoint:** `POST /api/competitors/{id}/analyze`
- **Transport:** `chat` · `format:"json"` · temperature `0.2` · Output = full analysis object (name, revenue_usd, revenue_inr, revenue_source, users, users_source, moats[], social{instagram,blog,facebook,x,thirdparty}, features[]{feature,sample_marketing,source})
- **Note:** Qwen via Ollama has **no web search** — revenue/users come from the model's own knowledge (`"NA"` when unknown), not a live sourced lookup.

**System** (`_ANALYSIS_SYSTEM` + JSON instruction)
```
You are a competitive-intelligence analyst. Produce a structured analysis of the given competitor from your own knowledge (you do not have live web access).
- revenue: the company's latest known annual revenue, expressed as THE SAME figure in both US dollars (revenue_usd, e.g. '$9.4B (FY2025)') and Indian rupees (revenue_inr, e.g. '₹78,000 crore') — convert using a recent exchange rate. If you know the publisher/source, put it in revenue_source, else 'NA'.
- users: the best known figure/estimate of users or customers; put any known publisher/source in users_source, else 'NA'.
- If a figure is genuinely unknown to you, set that field and its source to the exact string "NA". Never invent precise numbers.
- moats: up to 5 primary defensible advantages (most important first).
- social: true/false for a known presence on instagram, blog, facebook, x (twitter); thirdparty = name of any other notable channel (YouTube, LinkedIn, TikTok, …) or "NA".
- features: the key features/products the company markets, each with a one-line sample marketing message in their style, and a `source` = the publisher + URL of the page where that feature/message is found (the product, landing, pricing or docs page, e.g. 'Zoho Books (https://www.zoho.com/books/features/)'). Use "NA" only if no source URL can be found.
Keep revenue and users as clean values with no inline citation markup — the citation belongs only in the *_source fields.
```

**User**
```
Competitor to analyze: {name}
Website: {website or "unknown"}
Known context: {description or "—"}

Using your own knowledge, give this company's most recent known annual revenue
and its number of users/customers, citing a source for each where you know one.
Produce the full structured analysis. Use "NA" only when a figure is genuinely
unknown to you.
```

---

## 4. Suggest content themes (Stage 5)

- **Function:** `suggest_content_themes(...)`
- **Endpoint:** `POST /api/brands/{id}/content/themes`
- **Transport:** `chat` · `format:"json"` · temperature `0.6` · Output = `themes[] = {title, angle}` (asks for 5)
- Post-filter: any theme whose title/angle contains a banned word is dropped.

**System** (`_THEMES_SYSTEM` + JSON instruction)
```
You are a senior brand marketing strategist. Given a brand's strategy, its target personas and how it is differentiated from competitors, propose distinct, ready-to-develop content ideas (themes) for a specific format and platform. Each theme has a short, specific title and a one-to-two sentence angle explaining what it covers and why it resonates with the personas or sets the brand apart. Make the themes genuinely different from one another and appropriate for the platform's guidelines. Never invent statistics.
```

**User**
```
Propose {count} distinct content themes for a {content_format} to be published on {platform}, for the brand below.

BRAND
Name: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / differentiation: {moat or "—"}

TARGET PERSONAS
{persona_text}

COMPETITIVE CONTEXT (differentiate against these where relevant)
{comp_text}

FORMAT: {content_format}
LENGTH: {length_rule}
PLATFORM GUIDELINES ({platform}): {platform_guideline}{voice_block}{banned_line}

Return {count} clearly distinct themes, each with a short specific title and a one-to-two sentence angle.
```
(`{voice_block}` and `{banned_line}` are the Brand Voice fragments above — present only when set.)

---

## 5. Generate content (Stage 5)

- **Function:** `generate_content(...)`
- **Endpoint:** `POST /api/brands/{id}/content/generate`
- **Transport:** `chat` · free-form text (no `format`) · temperature `0.7`
- Optionally written to a chosen theme (from §4).
- Banned-word enforcement: if the draft contains a banned word, ONE corrective rewrite is requested at temperature `0.5` (the retry prompt is the same user prompt plus the block below); the rewrite is kept only if it is actually clean.

**System** (`_CONTENT_SYSTEM`)
```
You are a senior brand marketing copywriter. You write publish-ready content grounded in the brand's strategy, its target personas, and how it is differentiated from its competitors. You strictly follow the target platform's guidelines and the requested format and length. Write in the brand's voice, make specific and credible claims (never invent statistics), and return ONLY the content itself — ready to paste — using light markdown for structure where the platform allows it. No preamble, notes or explanations.
```

**User**
```
Write a {content_format} for the brand below, to be published on {platform}.

BRAND
Name: {brand_name}
Vision: {vision or "—"}
Goal: {goal or "—"}
Moat / differentiation: {moat or "—"}

TARGET PERSONAS
{persona_text}

COMPETITIVE CONTEXT (differentiate against these where relevant)
{comp_text}

FORMAT: {content_format}
LENGTH: {length_rule}
PLATFORM GUIDELINES ({platform}): {platform_guideline}{voice_block}{banned_line}
CHOSEN THEME: {theme_title} — {theme_angle}       ← only when a theme was picked
Write specifically to this theme.                  ← only when a theme was picked

Write the {content_format} now. Return only the content, ready to publish.
```

**Corrective-rewrite addendum** (only when a banned word slipped into the draft) — appended to the same user prompt:
```
Your previous draft used these BANNED words: {offending words}. Rewrite the {content_format} so NONE of the banned words (or their variants) appear, keeping the same meaning, tone and format. Return only the content.
```
