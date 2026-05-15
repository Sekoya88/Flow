'use client'

import React, { useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, FileUp, Loader2 } from 'lucide-react'
import { getApiBase } from '@/lib/api'
import { getToken } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface CVDropzoneProps {
  workspaceId: string
  onImported: (count: number, preview: { class: string; value: string }[]) => void
}

const MAX_SIZE = 5 * 1024 * 1024
const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

function isValidType(file: File): boolean {
  return (
    ALLOWED_MIME.includes(file.type) &&
    (file.name.endsWith('.pdf') || file.name.endsWith('.docx'))
  )
}

export function CVDropzone({ workspaceId, onImported }: CVDropzoneProps) {
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [importedCount, setImportedCount] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    setError(null)
    setImportedCount(null)

    if (!isValidType(file)) {
      setError('Only PDF or DOCX files are supported')
      return
    }

    if (file.size > MAX_SIZE) {
      setError('File must be under 5 MB')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('workspace_id', workspaceId)

      const token = getToken()
      const res = await fetch(`${getApiBase()}/api/v1/preferences/import-cv`, {
        method: 'POST',
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })

      if (!res.ok) {
        throw new Error('Upload failed')
      }

      const data = await res.json()
      setImportedCount(data.extracted)
      onImported(data.extracted, data.preview)
    } catch {
      setError('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'surface-glass relative rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-300',
          dragOver
            ? 'border-flow-brand/70 bg-flow-brand/[0.05] shadow-md shadow-flow-brand/10 scale-[1.01]'
            : 'border-border/50 hover:border-flow-brand/40 hover:bg-flow-brand/[0.02]',
          uploading && 'pointer-events-none opacity-60',
        )}
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-flow-brand/10 transition-transform duration-300">
          <FileUp
            className={cn(
              'h-7 w-7 text-flow-brand transition-transform duration-300',
              dragOver && 'scale-110',
            )}
          />
        </div>
        <p className="mt-4 text-sm font-medium text-foreground">
          Drop your résumé here
        </p>
        <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-muted-foreground/60">
          PDF · DOCX · max 5 MB
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="mt-4 rounded-full border-border/60 bg-card/60 px-4 text-xs font-medium hover:border-flow-brand/50 hover:bg-flow-brand/10"
        >
          Choose file
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          data-testid="cv-file-input"
          onChange={handleChange}
        />
      </div>

      {uploading && (
        <div className="flex items-center gap-2 rounded-xl border border-border/50 bg-muted/30 px-4 py-2.5 text-sm text-muted-foreground animate-fade-in">
          <Loader2 className="h-4 w-4 animate-spin text-flow-brand" />
          <span>Uploading...</span>
          <span className="font-mono text-[11px] text-muted-foreground/60">
            extracting preferences
          </span>
        </div>
      )}

      {error && !uploading && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive animate-fade-in"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {importedCount !== null && !uploading && !error && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-500 animate-fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>Imported {importedCount} preferences</span>
        </div>
      )}
    </div>
  )
}
