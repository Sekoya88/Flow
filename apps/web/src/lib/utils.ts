import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function agentDisplayName(a: { name: string; template?: string; id: string }): string {
  const isUuid = (s: string) => UUID_RE.test(s ?? '')
  const name = a.name || ''
  const template = a.template || ''
  if (!isUuid(name)) return name || (isUuid(template) ? `Agent ${a.id.slice(0, 6)}` : template) || `Agent ${a.id.slice(0, 6)}`
  if (template && !isUuid(template)) return template
  return `Agent ${a.id.slice(0, 6)}`
}
