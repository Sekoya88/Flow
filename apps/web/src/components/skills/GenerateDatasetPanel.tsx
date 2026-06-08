'use client'
import { useState } from 'react'
import { ChevronDown, ChevronRight, Database, Loader2, Sparkles } from 'lucide-react'
import { useGenerateDataset } from '@/lib/useSkillCollections'

export function GenerateDatasetPanel({ skillId, onGenerated }: { skillId: string; onGenerated?: () => void }) {
  const { generate, busy, result, error } = useGenerateDataset(skillId)
  const [showPrompt, setShowPrompt] = useState(false)

  async function handle() {
    const r = await generate(5)
    if (r) onGenerated?.()
  }

  return (
    <div className="rounded-lg border border-flow-800 bg-flow-950 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-flow-500">
          <Database className="h-3 w-3" /> Generate dataset
        </span>
        <button
          disabled={busy}
          onClick={() => void handle()}
          className="inline-flex items-center gap-1.5 rounded border border-flow-violet/40 bg-flow-violet/10 px-2.5 py-1 font-mono text-[10px] text-flow-violet hover:bg-flow-violet/20 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
          {busy ? 'Generating…' : 'Generate 5 items'}
        </button>
      </div>

      {error && <p className="font-mono text-[10px] text-red-400">{error}</p>}

      {result && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] text-emerald-400">
            ✓ Created &quot;{result.set_name}&quot; · {result.items.length} items · model {result.model}
          </p>

          <button
            onClick={() => setShowPrompt((v) => !v)}
            className="flex items-center gap-1 font-mono text-[10px] text-flow-500 hover:text-flow-300"
          >
            {showPrompt ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Exact prompt sent to the model
          </button>
          {showPrompt && (
            <pre className="max-h-40 overflow-y-auto rounded border border-flow-800 bg-flow-900 p-2 font-mono text-[9px] leading-relaxed text-flow-400 whitespace-pre-wrap">
              {result.prompt_used}
            </pre>
          )}

          <div className="space-y-1.5">
            {result.items.map((it, i) => (
              <div key={i} className="rounded border border-flow-800 bg-flow-900 p-2 space-y-1">
                <p className="font-mono text-[10px] text-flow-300"><span className="text-flow-600">IN </span>{it.input_text}</p>
                <p className="font-mono text-[10px] text-emerald-400/80"><span className="text-emerald-600">OK </span>{it.expected_output}</p>
                <p className="font-mono text-[9px] text-flow-600 italic">↳ {it.scoring_criteria}</p>
                {it.rationale && <p className="font-mono text-[9px] text-flow-700">probes: {it.rationale}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
