import type {
  Brand,
  BrandContext,
  BrandInput,
  BrandVoice,
  BrandVoiceInput,
  Competitor,
  CompetitorScope,
  CompetitorStatus,
  ContentGenerateInput,
  ContentResult,
  ContentThemesInput,
  ContentThemesResult,
  Persona,
  PersonaInput,
} from './types'

const BASE = '/api'

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const api = {
  listBrands: () => fetch(`${BASE}/brands`).then(handle<Brand[]>),

  getBrand: (id: string) => fetch(`${BASE}/brands/${id}`).then(handle<Brand>),

  createBrand: (data: BrandInput) =>
    fetch(`${BASE}/brands`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<Brand>),

  updateBrand: (id: string, data: Partial<BrandInput>) =>
    fetch(`${BASE}/brands/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<Brand>),

  // Phase 2 — ICP builder
  listPersonas: (brandId: string) =>
    fetch(`${BASE}/brands/${brandId}/personas`).then(handle<Persona[]>),

  createPersona: (brandId: string, data: PersonaInput) =>
    fetch(`${BASE}/brands/${brandId}/personas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<Persona>),

  updatePersona: (personaId: string, data: Partial<PersonaInput>) =>
    fetch(`${BASE}/personas/${personaId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<Persona>),

  deletePersona: (personaId: string) =>
    fetch(`${BASE}/personas/${personaId}`, { method: 'DELETE' }).then((res) => {
      if (!res.ok) throw new Error('Failed to delete persona')
    }),

  // Competitors
  getBrandContext: (brandId: string) =>
    fetch(`${BASE}/brands/${brandId}/context`).then(handle<BrandContext>),

  getCompetitorScope: (brandId: string) =>
    fetch(`${BASE}/brands/${brandId}/competitor-scope`).then(handle<CompetitorScope>),

  putCompetitorScope: (brandId: string, regions: string[]) =>
    fetch(`${BASE}/brands/${brandId}/competitor-scope`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ regions }),
    }).then(handle<CompetitorScope>),

  listCompetitors: (brandId: string) =>
    fetch(`${BASE}/brands/${brandId}/competitors`).then(handle<Competitor[]>),

  fetchCompetitors: (brandId: string, kind: 'tailored' | 'general' = 'tailored') =>
    fetch(`${BASE}/brands/${brandId}/competitors/fetch?kind=${kind}`, {
      method: 'POST',
    }).then(handle<Competitor[]>),

  addCompetitor: (
    brandId: string,
    data: { name: string; website?: string | null; source: 'tailored' | 'general' },
  ) =>
    fetch(`${BASE}/brands/${brandId}/competitors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<Competitor>),

  setCompetitorStatus: (id: string, status: CompetitorStatus) =>
    fetch(`${BASE}/competitors/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }).then(handle<Competitor>),

  deleteCompetitor: (id: string) =>
    fetch(`${BASE}/competitors/${id}`, { method: 'DELETE' }).then((res) => {
      if (!res.ok) throw new Error('Failed to delete competitor')
    }),

  pickCompetitor: (id: string) =>
    fetch(`${BASE}/competitors/${id}/pick`, { method: 'POST' }).then(
      handle<Competitor[]>,
    ),

  analyzeCompetitor: (id: string) =>
    fetch(`${BASE}/competitors/${id}/analyze`, { method: 'POST' }).then(
      handle<Competitor>,
    ),

  // Stage 4 — Content creation
  suggestContentThemes: (brandId: string, data: ContentThemesInput) =>
    fetch(`${BASE}/brands/${brandId}/content/themes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<ContentThemesResult>),

  generateContent: (brandId: string, data: ContentGenerateInput) =>
    fetch(`${BASE}/brands/${brandId}/content/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<ContentResult>),

  // Brand Voice — writing-style samples + banned words
  getBrandVoice: (brandId: string) =>
    fetch(`${BASE}/brands/${brandId}/brand-voice`).then(handle<BrandVoice>),

  putBrandVoice: (brandId: string, data: BrandVoiceInput) =>
    fetch(`${BASE}/brands/${brandId}/brand-voice`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(handle<BrandVoice>),
}
