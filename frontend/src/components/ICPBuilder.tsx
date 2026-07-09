import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  MAX_PERSONAS,
  type Brand,
  type Persona,
  type PersonaInput,
  type VariantInput,
} from '../types'

interface Draft {
  name: string
  user_type: string
  business_size: string
  region: string
  pain_points: string
  current_platforms: string
  main_goal: string
  variants: { label: string; description: string }[]
}

type ScalarField = Exclude<keyof Draft, 'variants'>

const EMPTY_DRAFT: Draft = {
  name: '',
  user_type: '',
  business_size: '',
  region: '',
  pain_points: '',
  current_platforms: '',
  main_goal: '',
  variants: [],
}

function toDraft(p: Persona): Draft {
  return {
    name: p.name,
    user_type: p.user_type ?? '',
    business_size: p.business_size ?? '',
    region: p.region ?? '',
    pain_points: p.pain_points ?? '',
    current_platforms: p.current_platforms ?? '',
    main_goal: p.main_goal ?? '',
    variants: p.variants.map((v) => ({ label: v.label, description: v.description ?? '' })),
  }
}

function toPayload(d: Draft): PersonaInput {
  const opt = (s: string) => s.trim() || null
  const variants: VariantInput[] = d.variants
    .filter((v) => v.label.trim())
    .map((v) => ({ label: v.label.trim(), description: v.description.trim() || null }))
  return {
    name: d.name.trim(),
    user_type: opt(d.user_type),
    business_size: opt(d.business_size),
    region: opt(d.region),
    pain_points: opt(d.pain_points),
    current_platforms: opt(d.current_platforms),
    main_goal: opt(d.main_goal),
    variants,
  }
}

export function ICPBuilder() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [brandId, setBrandId] = useState<string>('')
  const [personas, setPersonas] = useState<Persona[]>([])
  const [editingId, setEditingId] = useState<string | null>(null) // persona id or 'new'
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listBrands().then(setBrands)
  }, [])

  useEffect(() => {
    if (!brandId) {
      setPersonas([])
      return
    }
    setEditingId(null)
    api.listPersonas(brandId).then(setPersonas).catch((e) => setError(e.message))
  }, [brandId])

  function startNew() {
    setEditingId('new')
    setDraft(EMPTY_DRAFT)
    setError(null)
  }

  function startEdit(p: Persona) {
    setEditingId(p.id)
    setDraft(toDraft(p))
    setError(null)
  }

  function cancel() {
    setEditingId(null)
    setDraft(EMPTY_DRAFT)
    setError(null)
  }

  const setField = (key: ScalarField, value: string) =>
    setDraft((d) => ({ ...d, [key]: value }))

  function setVariant(i: number, key: 'label' | 'description', value: string) {
    setDraft((d) => ({
      ...d,
      variants: d.variants.map((v, idx) => (idx === i ? { ...v, [key]: value } : v)),
    }))
  }
  const addVariant = () =>
    setDraft((d) => ({ ...d, variants: [...d.variants, { label: '', description: '' }] }))
  const removeVariant = (i: number) =>
    setDraft((d) => ({ ...d, variants: d.variants.filter((_, idx) => idx !== i) }))

  async function save() {
    if (!draft.name.trim()) {
      setError('Persona name is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = toPayload(draft)
      if (editingId === 'new') await api.createPersona(brandId, payload)
      else if (editingId) await api.updatePersona(editingId, payload)
      setPersonas(await api.listPersonas(brandId))
      cancel()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(p: Persona) {
    if (!confirm(`Delete persona "${p.name}"?`)) return
    await api.deletePersona(p.id)
    setPersonas((prev) => prev.filter((x) => x.id !== p.id))
  }

  const atCap = personas.length >= MAX_PERSONAS

  return (
    <div className="phase-body">
      <header className="phase-head">
        <span className="phase-tag">Phase 2 · User provides</span>
        <h1>ICP builder</h1>
        <p>Who you sell to — up to five core personas, each defined by who they are, their pains, tools, and goal.</p>
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
        {brandId && (
          <div className="cap-row">
            <span className="count-pill">{personas.length} / {MAX_PERSONAS} personas</span>
            <button onClick={startNew} disabled={atCap || editingId === 'new'}>
              + Add persona
            </button>
          </div>
        )}
      </div>

      {!brandId && (
        <div className="card muted">
          {brands.length === 0
            ? <>Create a brand in <strong>Brand inputs</strong> first, then build its personas here.</>
            : <>Select a brand above to build its personas.</>}
        </div>
      )}

      {brandId && (
        <div className="persona-stack">
          {editingId === 'new' && (
            <PersonaEditor
              draft={draft}
              busy={busy}
              error={error}
              title="New persona"
              onField={setField}
              onVariant={setVariant}
              onAddVariant={addVariant}
              onRemoveVariant={removeVariant}
              onSave={save}
              onCancel={cancel}
            />
          )}

          {personas.length === 0 && editingId !== 'new' && (
            <div className="card muted">No personas yet. Add your first buyer type.</div>
          )}

          {personas.map((p) =>
            editingId === p.id ? (
              <PersonaEditor
                key={p.id}
                draft={draft}
                busy={busy}
                error={error}
                title="Edit persona"
                onField={setField}
                onVariant={setVariant}
                onAddVariant={addVariant}
                onRemoveVariant={removeVariant}
                onSave={save}
                onCancel={cancel}
              />
            ) : (
              <PersonaCard key={p.id} p={p} onEdit={() => startEdit(p)} onDelete={() => remove(p)} />
            )
          )}
        </div>
      )}
    </div>
  )
}

function PersonaCard({ p, onEdit, onDelete }: { p: Persona; onEdit: () => void; onDelete: () => void }) {
  const meta = [p.user_type, p.business_size, p.region].filter(Boolean).join(' · ')
  const parts: [string, string | null][] = [
    ['Pain points', p.pain_points],
    ['Marketing platforms used', p.current_platforms],
    ['Main goal', p.main_goal],
  ]
  return (
    <div className="card persona-card">
      <div className="persona-card-head">
        <div>
          <h3>{p.name}</h3>
          {meta && <p className="muted persona-meta">{meta}</p>}
        </div>
        <div className="row-actions">
          <button className="ghost" onClick={onEdit}>Edit</button>
          <button className="ghost danger" onClick={onDelete}>Delete</button>
        </div>
      </div>

      <dl className="persona-parts">
        {parts.map(([label, value]) =>
          value ? (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ) : null
        )}
      </dl>

      {p.variants.length > 0 && (
        <ul className="variant-list">
          {p.variants.map((v) => (
            <li key={v.id}>
              <strong>{v.label}</strong>
              {v.description && <span> — {v.description}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

interface EditorProps {
  draft: Draft
  busy: boolean
  error: string | null
  title: string
  onField: (key: ScalarField, value: string) => void
  onVariant: (i: number, key: 'label' | 'description', value: string) => void
  onAddVariant: () => void
  onRemoveVariant: (i: number) => void
  onSave: () => void
  onCancel: () => void
}

function PersonaEditor(p: EditorProps) {
  const d = p.draft
  return (
    <form
      className="card form persona-editor"
      onSubmit={(e) => {
        e.preventDefault()
        p.onSave()
      }}
    >
      <h3>{p.title}</h3>

      <label className="field">
        <span className="field-label">Persona name *</span>
        <input
          value={d.name}
          onChange={(e) => p.onField('name', e.target.value)}
          placeholder="e.g. Solo accountant"
        />
      </label>

      <div className="field">
        <span className="field-label">Define the user</span>
        <span className="field-why">Who they are, at a glance.</span>
        <div className="define-user">
          <input
            value={d.user_type}
            onChange={(e) => p.onField('user_type', e.target.value)}
            placeholder="User type (e.g. Accountant)"
          />
          <input
            value={d.business_size}
            onChange={(e) => p.onField('business_size', e.target.value)}
            placeholder="Business size (e.g. Small)"
          />
          <input
            value={d.region}
            onChange={(e) => p.onField('region', e.target.value)}
            placeholder="Region (e.g. North India)"
          />
        </div>
      </div>

      <label className="field">
        <span className="field-label">What are their pain points?</span>
        <textarea
          rows={2}
          value={d.pain_points}
          onChange={(e) => p.onField('pain_points', e.target.value)}
          placeholder="e.g. Manual data entry, chasing clients for documents."
        />
      </label>

      <label className="field">
        <span className="field-label">Which marketing platforms do they currently use?</span>
        <textarea
          rows={2}
          value={d.current_platforms}
          onChange={(e) => p.onField('current_platforms', e.target.value)}
          placeholder="e.g. WhatsApp, Instagram, LinkedIn, email newsletters."
        />
      </label>

      <label className="field">
        <span className="field-label">What is their main goal of using this product?</span>
        <textarea
          rows={2}
          value={d.main_goal}
          onChange={(e) => p.onField('main_goal', e.target.value)}
          placeholder="e.g. Automate invoice capture and save time."
        />
      </label>

      <div className="variants-block">
        <div className="variants-head">
          <span className="field-label">Variants</span>
          <span className="field-why">Sub-groups within this persona for slightly different situations.</span>
        </div>
        {d.variants.map((v, i) => (
          <div className="variant-row" key={i}>
            <input
              value={v.label}
              onChange={(e) => p.onVariant(i, 'label', e.target.value)}
              placeholder="Variant label (e.g. Tier-2 city solo practice)"
            />
            <input
              value={v.description}
              onChange={(e) => p.onVariant(i, 'description', e.target.value)}
              placeholder="Optional detail"
            />
            <button type="button" className="ghost danger" onClick={() => p.onRemoveVariant(i)}>
              ✕
            </button>
          </div>
        ))}
        <button type="button" className="ghost" onClick={p.onAddVariant}>
          + Add variant
        </button>
      </div>

      {p.error && <div className="alert">{p.error}</div>}
      <div className="actions">
        <button type="submit" disabled={p.busy}>
          {p.busy ? 'Saving…' : 'Save persona'}
        </button>
        <button type="button" className="ghost" onClick={p.onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
