import { useState } from 'react'
import { BrandInputs } from './components/BrandInputs'
import { ICPBuilder } from './components/ICPBuilder'
import { CompetitorAgent } from './components/CompetitorAgent'
import { ContentCreator } from './components/ContentCreator'
import { AnalysisExport } from './components/AnalysisExport'
import './App.css'

const STEPS = [
  { key: 'brand-inputs', label: 'Brand inputs', render: () => <BrandInputs /> },
  { key: 'icp-builder', label: 'ICP builder', render: () => <ICPBuilder /> },
  { key: 'competitors', label: 'Competitors', render: () => <CompetitorAgent /> },
  { key: 'content', label: 'Content creation', render: () => <ContentCreator /> },
  { key: 'analysis', label: 'Analysis', render: () => <AnalysisExport /> },
] as const

export default function App() {
  const [step, setStep] = useState(0)
  const isFirst = step === 0
  const isLast = step === STEPS.length - 1

  const go = (i: number) => {
    setStep(i)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app">
      <main className="stage">
        <div className="topbar">
          <div className="topbar-brand">
            AIMark<span>Brand Brain</span>
          </div>
          <nav className="tabs" aria-label="Stages">
            {STEPS.map((s, i) => (
              <button
                key={s.key}
                className={i === step ? 'tab active' : 'tab'}
                onClick={() => go(i)}
              >
                <span className="step-num">{i + 1}</span>
                {s.label}
              </button>
            ))}
          </nav>
        </div>

        {STEPS[step].render()}

        <div className="stepper-nav">
          <button className="ghost" disabled={isFirst} onClick={() => go(step - 1)}>
            ← Previous
          </button>
          <span className="step-count">
            Step {step + 1} of {STEPS.length}
          </span>
          {isLast ? (
            <button className="ghost" disabled>
              Done ✓
            </button>
          ) : (
            <button onClick={() => go(step + 1)}>Next: {STEPS[step + 1].label} →</button>
          )}
        </div>
      </main>
    </div>
  )
}
