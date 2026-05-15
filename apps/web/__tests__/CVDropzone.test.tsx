import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { CVDropzone } from '@/components/preferences/CVDropzone'

describe('CVDropzone', () => {
  const onImported = vi.fn()
  const workspaceId = 'ws-123'

  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders dropzone text', () => {
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    expect(screen.getByText(/Drop your résumé here/i)).toBeInTheDocument()
  })

  it('rejects non-PDF/DOCX files', async () => {
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    const input = screen.getByTestId('cv-file-input')
    const file = new File(['content'], 'resume.txt', { type: 'text/plain' })
    Object.defineProperty(file, 'size', { value: 1000 })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText('Only PDF or DOCX files are supported')).toBeInTheDocument()
    )
  })

  it('rejects files over 5 MB', async () => {
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    const input = screen.getByTestId('cv-file-input')
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 6_000_000 })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText('File must be under 5 MB')).toBeInTheDocument()
    )
  })

  it('shows uploading state during fetch', async () => {
    vi.stubGlobal('fetch', () => new Promise(() => {}))
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    const input = screen.getByTestId('cv-file-input')
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 1000 })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText('Uploading...')).toBeInTheDocument()
    )
  })

  it('shows preview after successful upload', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ extracted: 3, preview: [] }),
      })
    )
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    const input = screen.getByTestId('cv-file-input')
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 1000 })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText('Imported 3 preferences')).toBeInTheDocument()
    )
    expect(onImported).toHaveBeenCalledWith(3, [])
  })

  it('shows error on fetch failure', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new Error('network error')))
    render(<CVDropzone workspaceId={workspaceId} onImported={onImported} />)
    const input = screen.getByTestId('cv-file-input')
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 1000 })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(screen.getByText('Upload failed. Please try again.')).toBeInTheDocument()
    )
  })
})
