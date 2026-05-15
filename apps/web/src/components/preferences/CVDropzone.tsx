'use client'

import React, { useRef, useState } from 'react'
import { getApiBase } from '@/lib/api'
import { getToken } from '@/lib/auth'

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
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      style={{
        border: '2px dashed #ccc',
        borderRadius: 8,
        padding: 32,
        textAlign: 'center',
        opacity: uploading ? 0.6 : 1,
        pointerEvents: uploading ? 'none' : 'auto',
      }}
    >
      <p>Drop your résumé here (PDF or DOCX)</p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        Browse
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        style={{ display: 'none' }}
        data-testid="cv-file-input"
        onChange={handleChange}
      />
      {uploading && <p>Uploading...</p>}
      {error && <p>{error}</p>}
      {importedCount !== null && !uploading && (
        <p>Imported {importedCount} preferences</p>
      )}
    </div>
  )
}
