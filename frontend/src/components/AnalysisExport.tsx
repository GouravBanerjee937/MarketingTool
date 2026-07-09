import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Brand } from '../types'

export function AnalysisExport() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [brandId, setBrandId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listBrands().then(setBrands)
  }, [])

  async function download() {
    if (!brandId || busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/brands/${brandId}/analysis.xlsx`)
      if (!res.ok) throw new Error(`Export failed (HTTP ${res.status})`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const name = brands.find((b) => b.id === brandId)?.name ?? 'brand'
      a.href = url
      a.download = `analysis-${name.replace(/[^a-z0-9._-]+/gi, '_')}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="phase-body">
      <header className="phase-head">
        <span className="phase-tag">Analysis</span>
        <h1>Analysis</h1>
        <p>
          Export the full run for a brand as an Excel file — stage inputs (what you wrote),
          the exact system prompts &amp; responses recorded for every LLM call, the competitor
          segregation, up to 3 competitor analyses, and the content-generation prompts &amp; output.
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
            : <>Select a brand above to export its analysis.</>}
        </div>
      ) : (
        <section className="card">
          <h3>Export analysis workbook</h3>
          <p className="field-why">
            One <strong>.xlsx</strong> with sheets: Overview · Brand inputs · Personas (ICP) ·
            Competitors (segregation) · Competitor analysis (max 3) · LLM prompts &amp; responses.
          </p>
          {error && <div className="alert">{error}</div>}
          <div className="actions">
            <button onClick={download} disabled={busy}>
              {busy ? 'Building…' : 'Analysis ⬇'}
            </button>
            <span className="field-why" style={{ margin: 0 }}>
              Tip: the LLM prompt/response sheet fills in as you run the Competitors &amp; Content stages.
            </span>
          </div>
        </section>
      )}
    </div>
  )
}
