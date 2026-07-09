import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Brand } from '../types'

const FIELDS = [
  {
    key: 'vision' as const,
    label: 'Vision — where is the brand going?',
    why: 'Sets the big-picture direction everything later points toward.',
    placeholder: 'e.g. Make home-cooked dinners the easiest part of a busy weeknight, for every household.',
  },
  {
    key: 'goal' as const,
    label: 'Goal — what is the content trying to achieve?',
    why: 'Keeps later writing aimed at a real goal, not random.',
    placeholder: 'e.g. Grow paid weekly subscriptions.',
  },
  {
    key: 'moat' as const,
    label: 'Moat — why do you win / what is defensible?',
    why: 'Used to build the pillars. No moat = generic, forgettable pillars.',
    placeholder: 'e.g. Pre-portioned local ingredients delivered same-day — nothing wasted, nothing stale.',
  },
]

type FormState = { name: string; vision: string; goal: string; moat: string }

const EMPTY: FormState = { name: '', vision: '', goal: '', moat: '' }

export function BrandInputs() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<string | null>(null)

  useEffect(() => {
    api.listBrands().then(setBrands).catch((e) => setError(e.message))
  }, [])

  function loadBrand(b: Brand) {
    setSelectedId(b.id)
    setForm({ name: b.name, vision: b.vision ?? '', goal: b.goal ?? '', moat: b.moat ?? '' })
    setSavedAt(null)
    setError(null)
  }

  function newBrand() {
    setSelectedId(null)
    setForm(EMPTY)
    setSavedAt(null)
    setError(null)
  }

  function set<K extends keyof FormState>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function save() {
    setError(null)
    if (!form.name.trim()) {
      setError('Brand name is required.')
      return
    }
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        vision: form.vision.trim() || null,
        goal: form.goal.trim() || null,
        moat: form.moat.trim() || null,
      }
      const saved = selectedId
        ? await api.updateBrand(selectedId, payload)
        : await api.createBrand(payload)
      setSelectedId(saved.id)
      setBrands((prev) => {
        const rest = prev.filter((b) => b.id !== saved.id)
        return [saved, ...rest]
      })
      setSavedAt(new Date().toLocaleTimeString())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="phase-body">
      <header className="phase-head">
        <span className="phase-tag">Phase 1 · User provides</span>
        <h1>Brand inputs</h1>
        <p>The three answers that anchor the whole brand brain. Everything downstream points back to these.</p>
      </header>

      <div className="phase-grid">
        <form
          className="card form"
          onSubmit={(e) => {
            e.preventDefault()
            save()
          }}
        >
          <label className="field">
            <span className="field-label">Brand name *</span>
            <input
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              placeholder="e.g. FreshCrate"
            />
          </label>

          {FIELDS.map((f) => (
            <label className="field" key={f.key}>
              <span className="field-label">{f.label}</span>
              <span className="field-why">{f.why}</span>
              <textarea
                value={form[f.key]}
                onChange={(e) => set(f.key, e.target.value)}
                placeholder={f.placeholder}
                rows={3}
              />
            </label>
          ))}

          {error && <div className="alert">{error}</div>}

          <div className="actions">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving…' : selectedId ? 'Update brand' : 'Save brand'}
            </button>
            {savedAt && <span className="saved">Saved at {savedAt}</span>}
          </div>
        </form>

        <aside className="card sidebar">
          <div className="sidebar-head">
            <h2>Brands</h2>
            <button className="ghost" onClick={newBrand}>
              + New
            </button>
          </div>
          {brands.length === 0 && <p className="muted">No brands yet. Save your first one.</p>}
          <ul className="brand-list">
            {brands.map((b) => (
              <li key={b.id}>
                <button
                  className={b.id === selectedId ? 'brand-item active' : 'brand-item'}
                  onClick={() => loadBrand(b)}
                >
                  <strong>{b.name}</strong>
                  <span>{b.vision ?? 'No vision yet'}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  )
}
