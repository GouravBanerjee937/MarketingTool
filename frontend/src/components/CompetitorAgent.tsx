import { useEffect, useState } from 'react'
import { api } from '../api'
import type {
  Brand,
  BrandContext,
  Competitor,
  CompetitorAnalysis,
  CompetitorStatus,
} from '../types'

export function CompetitorAgent() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [brandId, setBrandId] = useState('')
  const [context, setContext] = useState<BrandContext | null>(null)
  const [competitors, setCompetitors] = useState<Competitor[]>([])
  const [fetchingKind, setFetchingKind] = useState<'tailored' | 'general' | null>(null)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [bulkAnalyzing, setBulkAnalyzing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listBrands().then(setBrands)
  }, [])

  useEffect(() => {
    if (!brandId) {
      setContext(null)
      setCompetitors([])
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      api.getBrandContext(brandId),
      api.listCompetitors(brandId),
    ])
      .then(([ctx, comps]) => {
        setContext(ctx)
        setCompetitors(comps)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [brandId])

  async function fetchCompetitors(kind: 'tailored' | 'general') {
    setFetchingKind(kind)
    setError(null)
    try {
      setCompetitors(await api.fetchCompetitors(brandId, kind))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setFetchingKind(null)
    }
  }

  async function setStatus(id: string, status: CompetitorStatus) {
    const updated = await api.setCompetitorStatus(id, status)
    setCompetitors((cs) => cs.map((c) => (c.id === id ? updated : c)))
  }

  async function addCompetitor(source: 'tailored' | 'general', name: string, website: string) {
    const created = await api.addCompetitor(brandId, {
      name,
      website: website.trim() || null,
      source,
    })
    setCompetitors((cs) => [...cs, created])
  }

  async function analyze(id: string) {
    setAnalyzingId(id)
    setError(null)
    try {
      const updated = await api.analyzeCompetitor(id)
      setCompetitors((cs) => cs.map((c) => (c.id === id ? updated : c)))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAnalyzingId(null)
    }
  }

  async function pick(id: string) {
    const list = await api.pickCompetitor(id)
    setCompetitors(list)
    // Auto-analyse the newly picked competitor if not analysed yet.
    const primary = list.find((c) => c.is_primary)
    if (primary && !primary.analysis) analyze(primary.id)
  }

  // Analyse considered competitors one at a time (progress visible per company).
  // force=false → only those not analysed yet; force=true → re-analyse all.
  async function analyzeAll(force = false) {
    const ids = competitors
      .filter((c) => c.status === 'considered' && (force || !c.analysis))
      .map((c) => c.id)
    if (ids.length === 0) return
    setBulkAnalyzing(true)
    setError(null)
    try {
      for (const id of ids) {
        setAnalyzingId(id)
        try {
          const updated = await api.analyzeCompetitor(id)
          setCompetitors((cs) => cs.map((c) => (c.id === id ? updated : c)))
        } catch (e) {
          setError((e as Error).message) // keep going with the rest
        }
      }
    } finally {
      setAnalyzingId(null)
      setBulkAnalyzing(false)
    }
  }

  return (
    <div className="phase-body">
      <header className="phase-head">
        <span className="phase-tag">Phase 4 · Competitors</span>
        <h1>Competitors</h1>
        <p>Pick a brand to pull in its context, then fetch and shortlist the competitors you want to focus on.</p>
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

      {!brandId && (
        <div className="card muted">
          {brands.length === 0
            ? <>Create a brand in <strong>Brand inputs</strong> first.</>
            : <>Select a brand above to begin.</>}
        </div>
      )}

      {brandId && !loading && context && (
        <div className="voice-stack">
          <BrandContextPanel context={context} />

          {error && <div className="alert">{error}</div>}

          <section className="card">
            <div className="comp-fetch-head">
              <div>
                <h3>Competitors</h3>
                <p className="field-why">
                  <strong>Tailored</strong> uses this brand's vision, goal, moat &amp; personas; <strong>general</strong> pulls the big players in your category. Tick to consider, cross to reject.
                </p>
              </div>
              <div className="fetch-buttons">
                <button onClick={() => fetchCompetitors('tailored')} disabled={fetchingKind !== null}>
                  {fetchingKind === 'tailored' ? 'Fetching…' : 'Fetch tailored'}
                </button>
                <span className="fetch-divider" aria-hidden="true" />
                <button className="ghost" onClick={() => fetchCompetitors('general')} disabled={fetchingKind !== null}>
                  {fetchingKind === 'general' ? 'Fetching…' : 'Fetch general'}
                </button>
              </div>
            </div>

            {competitors.length === 0 && fetchingKind === null && (
              <p className="muted">No competitors yet. Fetch a tailored or general list.</p>
            )}

            <CompetitorGroup
              title="To review · tailored to your brand"
              items={competitors.filter((c) => c.status === 'pending' && c.source === 'tailored')}
              gate
              onSet={setStatus}
              onAdd={(name, website) => addCompetitor('tailored', name, website)}
            />
            <hr className="group-divider" />
            <CompetitorGroup
              title="To review · general market"
              items={competitors.filter((c) => c.status === 'pending' && c.source === 'general')}
              gate
              onSet={setStatus}
              onAdd={(name, website) => addCompetitor('general', name, website)}
            />
            <CompetitorGroup
              title="Rejected"
              accent="rejected"
              items={competitors.filter((c) => c.status === 'rejected')}
              onSet={setStatus}
            />
          </section>

          <ConsideredPanel
            items={competitors.filter((c) => c.status === 'considered')}
            onSet={setStatus}
            onPick={pick}
          />

          <AnalysisPanel
            considered={competitors.filter((c) => c.status === 'considered')}
            analyzingId={analyzingId}
            bulkBusy={bulkAnalyzing}
            onAnalyze={analyze}
            onAnalyzeAll={() => analyzeAll(false)}
            onReanalyzeAll={() => analyzeAll(true)}
          />
        </div>
      )}
    </div>
  )
}

const Tick = ({ on }: { on: boolean }) =>
  on ? <span className="tick-yes">✓</span> : <span className="tick-no">✕</span>

function Source({ text }: { text: string }) {
  if (!text || text === 'NA') return null
  const url = text.match(/https?:\/\/[^\s)]+/)?.[0]
  const label = text.replace(/\s*\(?https?:\/\/[^\s)]+\)?/, '').trim() || 'source'
  return (
    <div className="source-line">
      source:{' '}
      {url ? (
        <a href={url} target="_blank" rel="noreferrer">{label}</a>
      ) : (
        <span>{text}</span>
      )}
    </div>
  )
}

// Inline (in-cell) source: renders the citation as a link, no "source:" prefix.
function SourceCell({ text }: { text: string }) {
  if (!text || text === 'NA') return <span className="muted">NA</span>
  const url = text.match(/https?:\/\/[^\s)]+/)?.[0]
  const label = text.replace(/\s*\(?https?:\/\/[^\s)]+\)?/, '').trim() || 'link'
  if (!url) return <span>{text}</span>
  return (
    <a href={url} target="_blank" rel="noreferrer">{label}</a>
  )
}

function AnalysisPanel({
  considered,
  analyzingId,
  bulkBusy,
  onAnalyze,
  onAnalyzeAll,
  onReanalyzeAll,
}: {
  considered: Competitor[]
  analyzingId: string | null
  bulkBusy: boolean
  onAnalyze: (id: string) => void
  onAnalyzeAll: () => void
  onReanalyzeAll: () => void
}) {
  const [viewId, setViewId] = useState('')

  // Keep the dropdown selection valid as the considered list changes; default
  // to the primary, else the first considered competitor.
  useEffect(() => {
    if (considered.length === 0) {
      if (viewId) setViewId('')
      return
    }
    if (!considered.some((c) => c.id === viewId)) {
      const primary = considered.find((c) => c.is_primary)
      setViewId(primary ? primary.id : considered[0].id)
    }
  }, [considered, viewId])

  if (considered.length === 0) {
    return (
      <section className="card muted">
        Consider at least one competitor above, then analyse the shortlist here.
      </section>
    )
  }

  const selected = considered.find((c) => c.id === viewId) ?? considered[0]
  const busy = analyzingId === selected.id
  const a: CompetitorAnalysis | null = selected.analysis
  const analyzedCount = considered.filter((c) => c.analysis).length
  const allAnalyzed = analyzedCount === considered.length

  return (
    <section className="card">
      <div className="comp-fetch-head">
        <div>
          <h3>Analysis</h3>
          <p className="field-why">
            Every considered competitor is analysed — pick one below to view it. “NA” where a
            figure is unavailable. <strong>{analyzedCount}/{considered.length}</strong> analysed.
          </p>
        </div>
        <div className="fetch-buttons">
          <button onClick={onAnalyzeAll} disabled={bulkBusy || analyzingId !== null || allAnalyzed}>
            {bulkBusy ? 'Analysing all…' : allAnalyzed ? 'All analysed' : 'Analyse all'}
          </button>
          <button
            className="ghost"
            onClick={onReanalyzeAll}
            disabled={bulkBusy || analyzingId !== null || analyzedCount === 0}
            title="Re-run analysis on every considered competitor, including already-analysed ones"
          >
            {bulkBusy ? 'Analysing all…' : 'Reanalyse all'}
          </button>
        </div>
      </div>

      <div className="analysis-picker">
        <label className="brand-select">
          <span>View competitor</span>
          <select value={selected.id} onChange={(e) => setViewId(e.target.value)}>
            {considered.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.is_primary ? ' ★' : ''}
                {c.analysis ? '' : ' — not analysed'}
              </option>
            ))}
          </select>
        </label>
        <button className="ghost" onClick={() => onAnalyze(selected.id)} disabled={busy || bulkBusy}>
          {busy ? 'Analysing…' : a ? 'Re-analyse' : 'Analyse'}
        </button>
      </div>

      <h4 className="analysis-name">
        {selected.name}
        {selected.is_primary && <span className="primary-badge">★ Primary</span>}
      </h4>

      {!a && !busy && <p className="muted">Not analysed yet — use “Analyse” or “Analyse all”.</p>}
      {busy && <p className="muted">Analysing {selected.name}…</p>}

      {a && (
        <div className="analysis">
          <table className="atable">
            <tbody>
              <tr><th>Name</th><td>{a.name || 'NA'}</td></tr>
              <tr>
                <th>Revenue (USD)</th>
                <td>{a.revenue_usd || 'NA'}</td>
              </tr>
              <tr>
                <th>Revenue (INR)</th>
                <td>{a.revenue_inr || 'NA'}<Source text={a.revenue_source} /></td>
              </tr>
              <tr>
                <th>Users (estimate)</th>
                <td>{a.users || 'NA'}<Source text={a.users_source} /></td>
              </tr>
            </tbody>
          </table>

          <h4>Primary moat (top 5)</h4>
          {a.moats.length ? (
            <ol className="moat-list">
              {a.moats.slice(0, 5).map((m, i) => <li key={i}>{m}</li>)}
            </ol>
          ) : (
            <p className="muted">NA</p>
          )}

          <h4>Social media presence</h4>
          <table className="atable">
            <tbody>
              <tr><th>Instagram</th><td><Tick on={a.social.instagram} /></td></tr>
              <tr><th>Blog</th><td><Tick on={a.social.blog} /></td></tr>
              <tr><th>Facebook</th><td><Tick on={a.social.facebook} /></td></tr>
              <tr><th>X (Twitter)</th><td><Tick on={a.social.x} /></td></tr>
              <tr>
                <th>Third-party</th>
                <td>{a.social.thirdparty && a.social.thirdparty !== 'NA' ? a.social.thirdparty : 'NA'}</td>
              </tr>
            </tbody>
          </table>

          <h4>Features marketed &amp; sample marketing</h4>
          {a.features.length ? (
            <table className="atable feature-table">
              <thead>
                <tr><th>Feature</th><th>Sample marketing</th><th>Source</th></tr>
              </thead>
              <tbody>
                {a.features.map((f, i) => (
                  <tr key={i}>
                    <td>{f.feature || 'NA'}</td>
                    <td>{f.sample_marketing || 'NA'}</td>
                    <td><SourceCell text={f.source} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">NA</p>
          )}
        </div>
      )}
    </section>
  )
}

function ConsideredPanel({
  items,
  onSet,
  onPick,
}: {
  items: Competitor[]
  onSet: (id: string, status: CompetitorStatus) => void
  onPick: (id: string) => void
}) {
  const primary = items.find((c) => c.is_primary)
  return (
    <section className="card">
      <div className="context-head">
        <h3>Considered competitors</h3>
        <span className="context-sub">your shortlist · {items.length}</span>
      </div>
      <p className="field-why">
        The competitors you ticked. <strong>Pick one</strong> as your primary competitor to focus on.
      </p>
      {primary && (
        <div className="primary-banner">
          Primary competitor: <strong>{primary.name}</strong>
        </div>
      )}
      {items.length === 0 ? (
        <p className="muted">Nothing considered yet — tick a competitor above.</p>
      ) : (
        <div className="considered-list">
          {items.map((c) => (
            <div className={`diff-row confirmed ${c.is_primary ? 'is-primary' : ''}`} key={c.id}>
              <div className="diff-body">
                <strong>
                  {c.is_primary && <span className="primary-badge">★ Primary</span>}
                  {c.name}
                  {c.source === 'general' && <span className="source-tag">general</span>}
                </strong>
                {c.description && <span>{c.description}</span>}
                {c.website && (
                  <a
                    className="diff-src"
                    href={c.website.startsWith('http') ? c.website : `https://${c.website}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {c.website}
                  </a>
                )}
              </div>
              <div className="diff-actions">
                {c.is_primary ? (
                  <span className="picked-label">Picked</span>
                ) : (
                  <button className="ghost keep" onClick={() => onPick(c.id)}>
                    Pick
                  </button>
                )}
                <button className="ghost" onClick={() => onSet(c.id, 'pending')}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function CompetitorGroup({
  title,
  items,
  gate,
  accent,
  onSet,
  onAdd,
}: {
  title: string
  items: Competitor[]
  gate?: boolean
  accent?: 'considered' | 'rejected'
  onSet: (id: string, status: CompetitorStatus) => void
  onAdd?: (name: string, website: string) => Promise<void> | void
}) {
  // Groups without an add control (e.g. Rejected) stay hidden when empty.
  if (items.length === 0 && !onAdd) return null
  return (
    <div className="diff-group">
      <div className={`diff-group-title ${accent === 'considered' ? 'kept' : ''}`}>
        <span>{title} · {items.length}</span>
        {onAdd && <AddCompetitorInline onAdd={onAdd} />}
      </div>
      {items.length === 0 && (
        <p className="muted diff-empty">Nothing here yet — fetch, or add one with +.</p>
      )}
      {items.map((c) => (
        <div className={`diff-row ${accent === 'considered' ? 'confirmed' : ''}`} key={c.id}>
          <div className="diff-body">
            <strong>{c.name}</strong>
            {c.description && <span>{c.description}</span>}
            {c.website && (
              <a
                className="diff-src"
                href={c.website.startsWith('http') ? c.website : `https://${c.website}`}
                target="_blank"
                rel="noreferrer"
              >
                {c.website}
              </a>
            )}
          </div>
          <div className="diff-actions">
            {gate ? (
              <>
                <button className="ghost keep" title="Consider" onClick={() => onSet(c.id, 'considered')}>
                  ✓ Consider
                </button>
                <button className="ghost danger" title="Reject" onClick={() => onSet(c.id, 'rejected')}>
                  ✕ Reject
                </button>
              </>
            ) : (
              <button className="ghost" onClick={() => onSet(c.id, 'pending')}>
                Undo
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function AddCompetitorInline({
  onAdd,
}: {
  onAdd: (name: string, website: string) => Promise<void> | void
}) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  function close() {
    setOpen(false)
    setName('')
    setWebsite('')
    setErr(null)
  }

  async function submit() {
    if (!name.trim()) {
      setErr('Company name is required.')
      return
    }
    setBusy(true)
    setErr(null)
    try {
      await onAdd(name.trim(), website)
      close()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button type="button" className="add-comp-btn" title="Add a competitor" onClick={() => setOpen(true)}>
        +
      </button>
    )
  }

  return (
    <div className="add-comp-form" onClick={(e) => e.stopPropagation()}>
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Company name"
      />
      <input
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Website URL (optional)"
      />
      <button type="button" className="keep" onClick={submit} disabled={busy}>
        {busy ? 'Adding…' : 'Add'}
      </button>
      <button type="button" className="ghost" onClick={close} disabled={busy}>
        Cancel
      </button>
      {err && <span className="add-comp-err">{err}</span>}
    </div>
  )
}

function BrandContextPanel({ context }: { context: BrandContext }) {
  const { brand, personas } = context
  const rows: [string, string | null][] = [
    ['Vision', brand.vision],
    ['Goal', brand.goal],
    ['Moat', brand.moat],
  ]
  return (
    <section className="card context-panel">
      <div className="context-head">
        <h3>Brand context</h3>
        <span className="context-sub">pulled from earlier stages</span>
      </div>

      <dl className="persona-parts">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value || <span className="muted">— not set</span>}</dd>
          </div>
        ))}
        <div>
          <dt>Personas ({personas.length})</dt>
          <dd>
            {personas.length
              ? personas.map((p) => p.name).join(', ')
              : <span className="muted">none yet</span>}
          </dd>
        </div>
      </dl>
    </section>
  )
}
