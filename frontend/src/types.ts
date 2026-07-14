export interface Brand {
  id: string
  name: string
  vision: string | null
  goal: string | null
  moat: string | null
  created_at: string
  updated_at: string
}

export interface BrandInput {
  name: string
  vision?: string | null
  goal?: string | null
  moat?: string | null
}

export interface Variant {
  id: string
  label: string
  description: string | null
  position: number
}

export interface VariantInput {
  label: string
  description?: string | null
}

export interface Persona {
  id: string
  brand_id: string
  name: string
  user_type: string | null
  business_size: string | null
  region: string | null
  pain_points: string | null
  current_platforms: string | null
  main_goal: string | null
  position: number
  variants: Variant[]
  created_at: string
  updated_at: string
}

export interface PersonaInput {
  name: string
  user_type?: string | null
  business_size?: string | null
  region?: string | null
  pain_points?: string | null
  current_platforms?: string | null
  main_goal?: string | null
  variants?: VariantInput[]
}

export const USER_TYPES = ['Accountant', 'CA', 'Business owner'] as const
export const BUSINESS_SIZES = ['Small', 'SME'] as const

export interface BrandContext {
  brand: Brand
  personas: Persona[]
}

export interface CompetitorScope {
  id: string
  brand_id: string
  regions: string[]
  created_at: string
  updated_at: string
}

export type CompetitorStatus = 'pending' | 'considered' | 'rejected'
export type CompetitorSource = 'tailored' | 'general'

export interface CompetitorAnalysis {
  name: string
  revenue_usd: string
  revenue_inr: string
  revenue_source: string
  users: string
  users_source: string
  moats: string[]
  social: {
    instagram: boolean
    blog: boolean
    facebook: boolean
    x: boolean
    thirdparty: string
  }
  features: { feature: string; sample_marketing: string; source: string }[]
  marketing_copy?: { copy: string; source: string }[]
  ad_libraries?: { meta: string; google: string; playstore: string }
  marketing_image?: { image: string; feature: string | null; page: string } | null
}

export interface Competitor {
  id: string
  brand_id: string
  name: string
  website: string | null
  description: string | null
  source: CompetitorSource
  status: CompetitorStatus
  is_primary: boolean
  analysis: CompetitorAnalysis | null
  position: number
}

export const MAX_PERSONAS = 5

// Stage 4 — Content creation
export type ContentForm = 'long' | 'short'

export interface ContentThemesInput {
  form: ContentForm
  content_format: string
  platform: string
  inspiration?: string
  liked_features?: string[]
}

export interface ContentTheme {
  title: string
  angle: string
}

export interface ContentThemesResult {
  themes: ContentTheme[]
}

export interface ContentGenerateInput {
  form: ContentForm
  content_format: string
  platform: string
  theme_title?: string
  theme_angle?: string
  inspiration?: string
  liked_features?: string[]
}

export interface ContentResult {
  script: string
}

// Brand Voice — writing-style samples + banned words
export interface VoiceSample {
  label: string
  text: string
}

export interface BrandVoice {
  id: string
  brand_id: string
  voice_samples: VoiceSample[]
  banned_words: string[]
  created_at: string
  updated_at: string
}

export interface BrandVoiceInput {
  voice_samples: VoiceSample[]
  banned_words: string[]
}
