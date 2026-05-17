'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Copy, Play, Square } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { getApiBase } from '@/lib/api'
import { getToken } from '@/lib/auth'

interface SkillPlaygroundProps {
  skillId: string
  triggers: string[]
}

export function SkillPlayground({ skillId, triggers }: SkillPlaygroundProps) {
  const [prompt, setPrompt] = useState(triggers[0] ?? '')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
  }, [])

  const run = useCallback(async () => {
    if (!prompt.trim() || running) return
    setOutput('')
    setError(null)
    setRunning(true)

    const ac = new AbortController()
    abortRef.current = ac
    const token = getToken()

    try {
      const res = await fetch(`${getApiBase()}/api/v1/skills/${skillId}/test`, {
        method: 'POST',
        signal: ac.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ prompt: prompt.trim() }),
      })

      if (!res.ok) {
        const body = await res.text()
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`)
      }
      if (!res.body) throw new Error('no response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let idx = buffer.indexOf('\n\n')
        while (idx !== -1) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data:')) continue
            const payload = line.slice(5).trim()
            if (!payload) continue
            try {
              const parsed = JSON.parse(payload) as { token?: string; done?: boolean }
              if (parsed.token) setOutput(o => o + parsed.token)
              if (parsed.done) {
                stop()
                return
              }
            } catch {
              // ignore non-JSON frames
            }
          }
          idx = buffer.indexOf('\n\n')
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') {
        setError(e.message)
      }
    } finally {
      setRunning(false)
      abortRef.current = null
    }
  }, [prompt, running, skillId, stop])

  const copy = useCallback(() => {
    if (!output) return
    void navigator.clipboard.writeText(output)
  }, [output])

  return (
    <div className="space-y-3">
      {triggers.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60 self-center">
            try a trigger:
          </span>
          {triggers.map((t, i) => (
            <Badge
              key={`${t}-${i}`}
              variant="outline"
              className="cursor-pointer border-flow-amber/40 text-flow-amber hover:bg-flow-amber/10"
              onClick={() => setPrompt(t)}
            >
              {t}
            </Badge>
          ))}
        </div>
      )}

      <Textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        placeholder="Ask anything — the skill body becomes the system prompt"
        className="min-h-[100px] font-mono text-[12.5px] leading-relaxed"
        disabled={running}
      />

      <div className="flex items-center gap-2">
        {running ? (
          <Button type="button" variant="outline" size="sm" onClick={stop}>
            <Square className="mr-1.5 h-3.5 w-3.5" />
            Stop
          </Button>
        ) : (
          <Button type="button" size="sm" onClick={run} disabled={!prompt.trim()}>
            <Play className="mr-1.5 h-3.5 w-3.5" />
            Run
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={copy}
          disabled={!output}
        >
          <Copy className="mr-1.5 h-3.5 w-3.5" />
          Copy output
        </Button>
        {error && <span className="text-xs text-destructive">{error}</span>}
      </div>

      <pre className="flow-card min-h-[180px] max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg border border-flow-800 p-4 font-mono text-[12.5px] leading-relaxed text-foreground">
        {output || (
          <span className="text-muted-foreground/50">
            (output streams here…)
          </span>
        )}
      </pre>
    </div>
  )
}
