'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, CheckCircle2, Code2, Layout, Loader2, Sparkles, Wand2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { SkillEditor } from '@/components/agents/SkillEditor'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

const CATEGORIES = ['General', 'Research', 'Code', 'Communication', 'Analysis', 'Memory', 'Planning']

const CATEGORY_COLORS: Record<string, string> = {
  Research: 'border-blue-500/40 text-blue-400',
  Code: 'border-emerald-500/40 text-emerald-400',
  Communication: 'border-violet-500/40 text-violet-400',
  Analysis: 'border-amber-500/40 text-amber-400',
  Memory: 'border-pink-500/40 text-pink-400',
  Planning: 'border-cyan-500/40 text-cyan-400',
  General: 'border-flow-800 text-muted-foreground',
}

interface AgentOption {
  id: string
  name: string
}

interface SkillTemplate {
  name: string
  category: string
  description: string
  content_md: string
}

interface CreateSkillSheetProps {
  open: boolean
  workspaceId: string
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

type Mode = 'template' | 'vibe' | 'library'
type VibeState = 'idle' | 'streaming' | 'done' | 'error'

export function CreateSkillSheet({ open, workspaceId, onOpenChange, onCreated }: CreateSkillSheetProps) {
  const [mode, setMode] = useState<Mode>('template')
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [agentId, setAgentId] = useState<string>('')
  const [category, setCategory] = useState('General')

  // Library state
  const [templates, setTemplates] = useState<SkillTemplate[]>([])
  const [templateSearch, setTemplateSearch] = useState('')
  const [savingTemplate, setSavingTemplate] = useState<string | null>(null)

  // Vibe state
  const [vibePrompt, setVibePrompt] = useState('')
  const [vibeState, setVibeState] = useState<VibeState>('idle')
  const [vibeContent, setVibeContent] = useState('')
  const [candidateSkillId, setCandidateSkillId] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)
  const [activated, setActivated] = useState(false)
  const vibeScrollRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (!workspaceId) return
    apiFetch<{ agents: AgentOption[] }>(`/api/v1/workspaces/${workspaceId}/agents`)
      .then(r => {
        setAgents(r.agents ?? [])
        if (r.agents?.length) setAgentId(r.agents[0].id)
      })
      .catch(() => {})
    apiFetch<{ templates: SkillTemplate[] }>('/api/v1/skills/templates')
      .then(r => setTemplates(r.templates ?? []))
      .catch(() => {})
  }, [workspaceId])

  useEffect(() => {
    if (vibeScrollRef.current) {
      vibeScrollRef.current.scrollTop = vibeScrollRef.current.scrollHeight
    }
  }, [vibeContent])

  const handleTemplateSave = useCallback(async (content: string, name: string) => {
    if (!agentId) return
    await apiFetch('/api/v1/skills', {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, agent_id: agentId, name, content_md: content }),
    })
    onCreated()
    onOpenChange(false)
  }, [agentId, workspaceId, onCreated, onOpenChange])

  const handleVibeSubmit = useCallback(async () => {
    if (!agentId || !vibePrompt.trim()) return
    setVibeState('streaming')
    setVibeContent('')
    setCandidateSkillId(null)
    setActivated(false)

    try {
      const res = await fetch(`/api/v1/skills/vibe-create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('flow_token')}` },
        body: JSON.stringify({ workspace_id: workspaceId, agent_id: agentId, prompt: vibePrompt, category }),
      })
      if (!res.body) throw new Error('no stream')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(line.slice(6))
            if (ev.token) setVibeContent(p => p + ev.token)
            if (ev.done && ev.skill_id) {
              setCandidateSkillId(ev.skill_id)
              setVibeState('done')
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch {
      setVibeState('error')
    }
  }, [agentId, workspaceId, vibePrompt, category])

  const handleActivateNow = useCallback(async () => {
    if (!candidateSkillId) return
    setActivating(true)
    try {
      await apiFetch(`/api/v1/skills/${candidateSkillId}/activate`, { method: 'POST' })
      setActivated(true)
      onCreated()
    } finally {
      setActivating(false)
    }
  }, [candidateSkillId, onCreated])

  const handleSubmitForReview = useCallback(async () => {
    if (!candidateSkillId) return
    setActivating(true)
    try {
      await apiFetch(`/api/v1/skills/${candidateSkillId}/improve`, { method: 'POST' }).catch(() => {})
      setActivated(true)
      onCreated()
    } finally {
      setActivating(false)
    }
  }, [candidateSkillId, onCreated])

  const handleInstallTemplate = useCallback(async (tmpl: SkillTemplate) => {
    if (!agentId) return
    setSavingTemplate(tmpl.name)
    try {
      await apiFetch('/api/v1/skills', {
        method: 'POST',
        body: JSON.stringify({
          workspace_id: workspaceId,
          agent_id: agentId,
          name: tmpl.name,
          content_md: tmpl.content_md,
        }),
      })
      onCreated()
      onOpenChange(false)
    } finally {
      setSavingTemplate(null)
    }
  }, [agentId, workspaceId, onCreated, onOpenChange])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full max-w-2xl overflow-y-auto">
        <SheetHeader className="mb-4">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-flow-violet" />
            New Skill
          </SheetTitle>
        </SheetHeader>

        {/* Agent + Category selectors */}
        <div className="mb-4 flex flex-wrap gap-3">
          <div className="flex-1 min-w-[180px] space-y-1">
            <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Agent</Label>
            <Select value={agentId} onValueChange={v => setAgentId(v ?? '')}>
              <SelectTrigger>
                <Bot className="mr-1.5 h-3 w-3 text-muted-foreground" />
                <SelectValue placeholder="Select agent…" />
              </SelectTrigger>
              <SelectContent>
                {agents.map(a => (
                  <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-[140px] space-y-1">
            <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Category</Label>
            <Select value={category} onValueChange={v => setCategory(v ?? 'General')}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Mode toggle */}
        <div className="mb-4 flex gap-1 rounded-[6px] border border-flow-800 p-1 w-fit">
          <button
            onClick={() => setMode('template')}
            className={cn(
              'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs transition-colors',
              mode === 'template' ? 'bg-flow-violet/20 text-flow-violet' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Code2 className="h-3 w-3" />
            Template
          </button>
          <button
            onClick={() => setMode('vibe')}
            className={cn(
              'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs transition-colors',
              mode === 'vibe' ? 'bg-flow-violet/20 text-flow-violet' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Wand2 className="h-3 w-3" />
            Vibe
          </button>
          <button
            onClick={() => setMode('library')}
            className={cn(
              'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs transition-colors',
              mode === 'library' ? 'bg-flow-violet/20 text-flow-violet' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Layout className="h-3 w-3" />
            Library
          </button>
        </div>

        {/* Template mode */}
        {mode === 'template' && (
          <SkillEditor
            onSave={handleTemplateSave}
            onCancel={() => onOpenChange(false)}
          />
        )}

        {/* Vibe mode */}
        {mode === 'vibe' && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">What should this skill do?</Label>
              <Textarea
                value={vibePrompt}
                onChange={e => setVibePrompt(e.target.value)}
                placeholder="e.g. Help the agent summarize Slack threads and extract action items with owners and deadlines…"
                rows={4}
                className="resize-none text-sm"
                disabled={vibeState === 'streaming'}
              />
            </div>

            {vibeState === 'idle' && (
              <Button
                onClick={handleVibeSubmit}
                disabled={!vibePrompt.trim() || !agentId}
                className="gap-1.5"
                size="sm"
              >
                <Wand2 className="h-3.5 w-3.5" />
                Generate skill
              </Button>
            )}

            {vibeState === 'streaming' && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Generating SKILL.md…
              </div>
            )}

            {(vibeState === 'streaming' || vibeState === 'done') && vibeContent && (
              <pre
                ref={vibeScrollRef}
                className="max-h-96 overflow-y-auto rounded-[6px] border border-flow-800 bg-muted/20 p-4 font-mono text-xs leading-relaxed text-foreground/80 whitespace-pre-wrap"
              >
                {vibeContent}
              </pre>
            )}

            {vibeState === 'done' && !activated && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleActivateNow}
                  disabled={activating}
                  className="gap-1.5"
                >
                  {activating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  Activate now
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSubmitForReview}
                  disabled={activating}
                  className="gap-1.5 border-flow-800"
                >
                  Submit for review
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => { setVibeState('idle'); setVibeContent('') }}
                  className="text-muted-foreground"
                >
                  Discard
                </Button>
              </div>
            )}

            {vibeState === 'done' && activated && (
              <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Skill saved successfully
              </div>
            )}

            {vibeState === 'error' && (
              <p className="text-xs text-destructive">Generation failed. Check API key configuration.</p>
            )}
          </div>
        )}

        {/* Library mode */}
        {mode === 'library' && (
          <div className="space-y-3">
            <Input
              value={templateSearch}
              onChange={e => setTemplateSearch(e.target.value)}
              placeholder="Search templates…"
              className="text-sm"
            />
            {templates.length === 0 && (
              <p className="text-xs text-muted-foreground">Loading templates…</p>
            )}
            <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
              {templates
                .filter(t =>
                  !templateSearch.trim() ||
                  t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
                  t.category.toLowerCase().includes(templateSearch.toLowerCase()) ||
                  t.description.toLowerCase().includes(templateSearch.toLowerCase())
                )
                .map(tmpl => (
                  <div
                    key={tmpl.name}
                    className="flow-card flex items-start justify-between gap-3 rounded-[6px] border border-flow-800 p-3"
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-foreground truncate">
                          {tmpl.name}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn('shrink-0 text-[9px] px-1.5 py-0', CATEGORY_COLORS[tmpl.category] ?? CATEGORY_COLORS.General)}
                        >
                          {tmpl.category}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                        {tmpl.description}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0 h-7 gap-1 text-xs border-flow-violet/40 text-flow-violet"
                      disabled={!agentId || savingTemplate === tmpl.name}
                      onClick={() => handleInstallTemplate(tmpl)}
                    >
                      {savingTemplate === tmpl.name
                        ? <Loader2 className="h-3 w-3 animate-spin" />
                        : 'Add'
                      }
                    </Button>
                  </div>
                ))
              }
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
