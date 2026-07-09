import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Brand, BrandVoiceInput, ContentForm, ContentTheme, VoiceSample } from '../types'

const PLATFORMS_BY_FORM: Record<ContentForm, string[]> = {
  long: ['Blogs', 'Instagram scripts'],
  short: ['WhatsApp', 'RCS', 'Google Ads'],
}
// The content format the LLM writes, derived from the chosen platform.
const FORMAT_FOR_PLATFORM: Record<string, string> = {
  Blogs: 'Blog post',
  'Instagram scripts': 'Instagram script',
  WhatsApp: 'WhatsApp message',
  RCS: 'RCS message',
  'Google Ads': 'Google ad',
}
const OTHER = 'Other'

export function ContentCreator() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [brandId, setBrandId] = useState('')

  const [form, setForm] = useState<ContentForm | ''>('')
  const [platform, setPlatform] = useState<string>('')
  const [customPlatform, setCustomPlatform] = useState('')

  const [themes, setThemes] = useState<ContentTheme[]>([])
  const [themesLoading, setThemesLoading] = useState(false)
  const [selectedTheme, setSelectedTheme] = useState<number | null>(null)

  const [script, setScript] = useState('')
  const [generated, setGenerated] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  // Brand Voice
  const [voice, setVoice] = useState<BrandVoiceInput>({ voice_samples: [], banned_words: [] })
  const [voiceOpen, setVoiceOpen] = useState(false)

  useEffect(() => {
    api.listBrands().then(setBrands)
  }, [])

  // Load the selected brand's saved voice (samples + banned words).
  useEffect(() => {
    if (!brandId) {
      setVoice({ voice_samples: [], banned_words: [] })
      return
    }
    let alive = true
    api
      .getBrandVoice(brandId)
      .then((v) => {
        if (alive) setVoice({ voice_samples: v.voice_samples, banned_words: v.banned_words })
      })
      .catch(() => {
        if (alive) setVoice({ voice_samples: [], banned_words: [] })
      })
    return () => {
      alive = false
    }
  }, [brandId])

  const effectivePlatform = platform === OTHER ? customPlatform.trim() : platform
  const contentFormat =
    platform === OTHER ? customPlatform.trim() : FORMAT_FOR_PLATFORM[platform] ?? platform
  const inputsReady = !!brandId && !!form && !!effectivePlatform

  // Any change to the inputs invalidates previously suggested themes + script.
  function resetDownstream() {
    setThemes([])
    setSelectedTheme(null)
    setScript('')
    setGenerated(false)
    setError(null)
  }

  async function suggestThemes() {
    if (!inputsReady || themesLoading) return
    setThemesLoading(true)
    setSelectedTheme(null)
    setScript('')
    setGenerated(false)
    setError(null)
    try {
      const res = await api.suggestContentThemes(brandId, {
        form: form as ContentForm,
        content_format: contentFormat,
        platform: effectivePlatform,
      })
      setThemes(res.themes)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setThemesLoading(false)
    }
  }

  async function generate() {
    if (selectedTheme === null || generating) return
    const theme = themes[selectedTheme]
    setGenerating(true)
    setError(null)
    try {
      const res = await api.generateContent(brandId, {
        form: form as ContentForm,
        content_format: contentFormat,
        platform: effectivePlatform,
        theme_title: theme.title,
        theme_angle: theme.angle,
      })
      setScript(res.script)
      setGenerated(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(script)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="phase-body">
      <header className="phase-head">
        <span className="phase-tag">Phase 5 · Content creation</span>
        <h1>Content creation</h1>
        <p>
          Pick a brand, choose the kind of content and where it will run. We suggest themes
          grounded in your brand, personas, competitors &amp; the platform's guidelines — choose one,
          then generate an editable script with a live preview.
        </p>
      </header>

      <div className="icp-toolbar">
        <label className="brand-select">
          <span>Brand</span>
          <select value={brandId} onChange={(e) => setBrandId(e.target.value)}>
            <option value="">{brands.length === 0 ? 'No brands yet' : 'Select a brand…'}</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!brandId ? (
        <div className="card muted">
          {brands.length === 0
            ? <>Create a brand in <strong>Brand inputs</strong> first.</>
            : <>Select a brand above to begin.</>}
        </div>
      ) : (
        <>
          <section className="card">
            <h3>Content type</h3>
            <p className="field-why">Is this a long-form piece or a short-form one?</p>
            <label className="brand-select">
              <span>Content type</span>
              <select
                value={form}
                onChange={(e) => {
                  setForm(e.target.value as ContentForm)
                  setPlatform('')
                  setCustomPlatform('')
                  resetDownstream()
                }}
              >
                <option value="">Select…</option>
                <option value="long">Long form</option>
                <option value="short">Short form</option>
              </select>
            </label>
          </section>

          {form && (
            <section className="card">
              <h3>Where will it be posted?</h3>
              <p className="field-why">
                Options depend on your content type — its guidelines shape the output. Pick
                <strong> Other…</strong> to enter your own platform.
              </p>
              <label className="brand-select">
                <span>Platform</span>
                <select
                  value={platform}
                  onChange={(e) => {
                    setPlatform(e.target.value)
                    resetDownstream()
                  }}
                >
                  <option value="">Select…</option>
                  {PLATFORMS_BY_FORM[form].map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                  <option value={OTHER}>Other…</option>
                </select>
              </label>
              {platform === OTHER && (
                <input
                  className="text-input"
                  value={customPlatform}
                  onChange={(e) => {
                    setCustomPlatform(e.target.value)
                    resetDownstream()
                  }}
                  placeholder="Enter platform (e.g. LinkedIn, Email, Telegram)"
                  style={{ marginTop: 10 }}
                />
              )}
            </section>
          )}

          {error && <div className="alert">{error}</div>}

          {inputsReady && (
            <section className="card">
              <div className="comp-fetch-head">
                <div>
                  <h3>Content themes</h3>
                  <p className="field-why">
                    {themes.length
                      ? 'Pick the direction you like, then generate the script for it.'
                      : `Theme ideas for your ${contentFormat} on ${effectivePlatform}, drawn from your brand, personas, competitors & the platform's guidelines.`}
                  </p>
                  <p className="field-why voice-summary">
                    Brand Voice:{' '}
                    {voice.voice_samples.length === 0 && voice.banned_words.length === 0 ? (
                      <span className="muted">not set</span>
                    ) : (
                      <>
                        <strong>{voice.voice_samples.length}</strong> sample
                        {voice.voice_samples.length === 1 ? '' : 's'} ·{' '}
                        <strong>{voice.banned_words.length}</strong> banned word
                        {voice.banned_words.length === 1 ? '' : 's'}
                      </>
                    )}
                  </p>
                </div>
                <div className="fetch-buttons">
                  <button className="ghost" onClick={() => setVoiceOpen(true)}>
                    Brand Voice
                  </button>
                  <button onClick={suggestThemes} disabled={themesLoading || generating}>
                    {themesLoading ? 'Analysing…' : themes.length ? 'Re-suggest' : 'Suggest themes'}
                  </button>
                </div>
              </div>

              {themesLoading && (
                <p className="muted">Analysing brand, personas, competitors &amp; {effectivePlatform} guidelines…</p>
              )}
              {!themesLoading && themes.length === 0 && (
                <p className="muted">No themes yet — click “Suggest themes”.</p>
              )}

              {themes.length > 0 && (
                <>
                  <div className="theme-grid">
                    {themes.map((t, i) => (
                      <button
                        type="button"
                        key={i}
                        className={`theme-card ${selectedTheme === i ? 'active' : ''}`}
                        onClick={() => setSelectedTheme(i)}
                      >
                        <span className="theme-num">{i + 1}</span>
                        <h4>{t.title}</h4>
                        <p>{t.angle}</p>
                      </button>
                    ))}
                  </div>
                  <div className="actions">
                    <button onClick={generate} disabled={selectedTheme === null || generating}>
                      {generating ? 'Generating…' : generated ? 'Regenerate script' : 'Generate script →'}
                    </button>
                    {selectedTheme === null && !generating && (
                      <span className="saved">Select a theme to continue.</span>
                    )}
                    {generating && <span className="saved">Writing your {contentFormat}…</span>}
                  </div>
                </>
              )}
            </section>
          )}

          {generated && (
            <section className="card">
              <div className="comp-fetch-head">
                <div>
                  <h3>Script &amp; preview</h3>
                  <p className="field-why">
                    {selectedTheme !== null && themes[selectedTheme] && (
                      <>Theme: <strong>{themes[selectedTheme].title}</strong>. </>
                    )}
                    Edit on the left — the {effectivePlatform} preview updates as you type.
                  </p>
                </div>
                <button className="ghost" onClick={copy}>{copied ? 'Copied ✓' : 'Copy'}</button>
              </div>
              <div className="content-panes">
                <div className="pane">
                  <div className="pane-label">Script (editable)</div>
                  <textarea
                    className="script-editor"
                    value={script}
                    onChange={(e) => setScript(e.target.value)}
                    spellCheck
                  />
                </div>
                <div className="pane">
                  <div className="pane-label">Preview · {effectivePlatform}</div>
                  <ContentPreview platform={effectivePlatform} text={script} brandName={brands.find((b) => b.id === brandId)?.name ?? 'Your brand'} />
                </div>
              </div>
            </section>
          )}

          {voiceOpen && (
            <BrandVoiceModal
              initial={voice}
              onClose={() => setVoiceOpen(false)}
              onSave={async (next) => {
                const saved = await api.putBrandVoice(brandId, next)
                setVoice({ voice_samples: saved.voice_samples, banned_words: saved.banned_words })
                setVoiceOpen(false)
              }}
            />
          )}
        </>
      )}
    </div>
  )
}

// --- Brand Voice modal -------------------------------------------------

function BrandVoiceModal({
  initial,
  onClose,
  onSave,
}: {
  initial: BrandVoiceInput
  onClose: () => void
  onSave: (next: BrandVoiceInput) => Promise<void>
}) {
  const [samples, setSamples] = useState<VoiceSample[]>(initial.voice_samples)
  const [banned, setBanned] = useState<string[]>(initial.banned_words)
  const [pasteText, setPasteText] = useState('')
  const [wordInput, setWordInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  async function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const added: VoiceSample[] = []
    for (const f of Array.from(files)) {
      try {
        const text = (await f.text()).trim()
        if (text) added.push({ label: f.name, text })
      } catch {
        setErr(`Could not read ${f.name}`)
      }
    }
    if (added.length) setSamples((s) => [...s, ...added])
    if (fileRef.current) fileRef.current.value = ''
  }

  function addPaste() {
    const t = pasteText.trim()
    if (!t) return
    setSamples((s) => [...s, { label: `Pasted text ${s.filter((x) => !x.label || x.label.startsWith('Pasted')).length + 1}`, text: t }])
    setPasteText('')
  }

  function removeSample(i: number) {
    setSamples((s) => s.filter((_, idx) => idx !== i))
  }

  function addWords(raw: string) {
    const parts = raw.split(/[,\n]/).map((w) => w.trim()).filter(Boolean)
    if (parts.length === 0) return
    setBanned((prev) => {
      const seen = new Set(prev.map((w) => w.toLowerCase()))
      const next = [...prev]
      for (const p of parts) {
        if (!seen.has(p.toLowerCase())) {
          seen.add(p.toLowerCase())
          next.push(p)
        }
      }
      return next
    })
    setWordInput('')
  }

  function removeWord(i: number) {
    setBanned((b) => b.filter((_, idx) => idx !== i))
  }

  async function save() {
    setSaving(true)
    setErr(null)
    try {
      await onSave({ voice_samples: samples, banned_words: banned })
    } catch (e) {
      setErr((e as Error).message)
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Brand Voice</h3>
          <button className="modal-x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="field-why">
          Teach the model how your brand writes, and list words it must never use. Applied
          whenever you suggest themes or generate content for this brand.
        </p>

        <div className="modal-body">
          <section className="modal-section">
            <h4>Sample documents</h4>
            <p className="field-why">
              Upload example posts (multiple) or paste text — used to learn your brand's writing
              style. Text files (.txt, .md, .csv, .html) read best.
            </p>
            <div className="voice-upload">
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".txt,.md,.markdown,.csv,.html,.htm,.json,text/*"
                onChange={(e) => onFiles(e.target.files)}
              />
            </div>
            <textarea
              className="script-editor voice-paste"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="…or paste a sample post here"
            />
            <div className="actions">
              <button className="ghost" onClick={addPaste} disabled={!pasteText.trim()}>
                Add pasted text
              </button>
            </div>

            {samples.length === 0 ? (
              <p className="muted">No samples yet.</p>
            ) : (
              <ul className="voice-list">
                {samples.map((s, i) => (
                  <li key={i} className="voice-item">
                    <div className="voice-item-main">
                      <strong>{s.label || `Sample ${i + 1}`}</strong>
                      <span className="muted voice-preview">{s.text.slice(0, 120)}</span>
                    </div>
                    <button className="ghost danger" onClick={() => removeSample(i)}>
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="modal-section">
            <h4>Banned words</h4>
            <p className="field-why">
              These words (and obvious variants) will not appear in any generated theme or
              content. Press Enter or comma to add.
            </p>
            <input
              className="text-input"
              value={wordInput}
              onChange={(e) => setWordInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault()
                  addWords(wordInput)
                }
              }}
              placeholder="e.g. cheap, guaranteed, revolutionary"
            />
            {banned.length === 0 ? (
              <p className="muted">No banned words yet.</p>
            ) : (
              <div className="chip-row">
                {banned.map((w, i) => (
                  <span key={i} className="chip">
                    {w}
                    <button className="chip-x" onClick={() => removeWord(i)} aria-label={`Remove ${w}`}>
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </section>
        </div>

        {err && <div className="alert">{err}</div>}

        <div className="modal-foot">
          <button className="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Brand Voice'}
          </button>
        </div>
      </div>
    </div>
  )
}

// --- Preview -----------------------------------------------------------

function ContentPreview({ platform, text, brandName }: { platform: string; text: string; brandName: string }) {
  const key = platform.trim().toLowerCase()
  if (!text.trim()) return <div className="preview-empty muted">Nothing to preview yet.</div>

  if (key === 'whatsapp') {
    return (
      <div className="pv-whatsapp">
        <div className="pv-wa-header">{brandName}</div>
        <div className="pv-wa-body">
          <div className="pv-wa-bubble">{renderBlocks(text)}</div>
        </div>
      </div>
    )
  }
  if (key === 'rcs') {
    return (
      <div className="pv-rcs">
        <div className="pv-rcs-brand">{brandName} · Verified business</div>
        <div className="pv-rcs-card">{renderBlocks(text)}</div>
      </div>
    )
  }
  if (key === 'google ad' || key === 'google ads') {
    return <GoogleAdPreview text={text} brandName={brandName} />
  }
  // Default / custom / long-form: a clean document preview.
  return <div className="pv-doc">{renderBlocks(text)}</div>
}

function GoogleAdPreview({ text, brandName }: { text: string; brandName: string }) {
  const headlines: string[] = []
  const descriptions: string[] = []
  const other: string[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const h = line.match(/^headline\s*\d*\s*[:\-]\s*(.+)$/i)
    const d = line.match(/^description\s*\d*\s*[:\-]\s*(.+)$/i)
    if (h) headlines.push(h[1].trim())
    else if (d) descriptions.push(d[1].trim())
    else other.push(line)
  }
  const title = headlines.length ? headlines.slice(0, 3).join(' | ') : other[0] ?? 'Your headline'
  const body = descriptions.length ? descriptions.join(' ') : other.slice(1).join(' ')
  const domain = brandName.toLowerCase().replace(/[^a-z0-9]+/g, '') || 'yourbrand'
  return (
    <div className="pv-ad">
      <div className="pv-ad-row">
        <span className="pv-ad-badge">Ad</span>
        <span className="pv-ad-url">www.{domain}.com</span>
      </div>
      <div className="pv-ad-title">{title}</div>
      <div className="pv-ad-desc">{body || '—'}</div>
    </div>
  )
}

// Minimal, safe markdown-ish renderer (headings, bullets, bold). No raw HTML.
function renderBlocks(text: string) {
  const lines = text.split('\n')
  const out: React.ReactNode[] = []
  let bullets: string[] = []

  const flush = () => {
    if (bullets.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="pv-ul">
          {bullets.map((b, i) => <li key={i}>{renderInline(b)}</li>)}
        </ul>,
      )
      bullets = []
    }
  }

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd()
    const t = line.trim()
    if (!t) { flush(); return }
    if (/^#{3}\s+/.test(t)) { flush(); out.push(<h5 key={idx} className="pv-h3">{renderInline(t.replace(/^#{3}\s+/, ''))}</h5>); return }
    if (/^#{2}\s+/.test(t)) { flush(); out.push(<h4 key={idx} className="pv-h2">{renderInline(t.replace(/^#{2}\s+/, ''))}</h4>); return }
    if (/^#\s+/.test(t)) { flush(); out.push(<h3 key={idx} className="pv-h1">{renderInline(t.replace(/^#\s+/, ''))}</h3>); return }
    if (/^[-*]\s+/.test(t)) { bullets.push(t.replace(/^[-*]\s+/, '')); return }
    flush()
    out.push(<p key={idx} className="pv-p">{renderInline(t)}</p>)
  })
  flush()
  return out
}

// Bold (**text**) inline; everything else plain text.
function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    /^\*\*[^*]+\*\*$/.test(p) ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>,
  )
}
