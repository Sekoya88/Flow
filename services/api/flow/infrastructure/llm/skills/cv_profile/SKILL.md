---
name: cv-profile-facets
description: Use when extracting user profile preferences from résumé or CV text for the Flow workspace. Defines allowed facet classes, value style, and limits.
---

# CV profile extraction (Flow)

## Allowed preference classes

Map extracted signals only to these `class` values when emitting structured preference rows downstream:

- `tooling` — languages, frameworks, runtimes, clouds, databases, major tools
- `domain` — industry, role family, product area (short phrases)
- `goal` — learning intent, current focus, career direction
- `style` — answer formatting preferences implied by the CV (concise, technical depth, etc.)
- `veto` — technologies or patterns the candidate clearly avoids or dislikes (only if explicit)
- `channel` — how they prefer artifacts (docs, code samples, diagrams) when inferable

## Value rules

- Short declarative English phrases, **max ~10 words** each
- No PII beyond what is already in the CV (no invented contact info)
- Deduplicate near-duplicates (e.g. "React" vs "React.js" → one canonical form)
- OCR noise: drop fragments shorter than 2 characters or obvious garbage tokens

## Volume limits

- Tooling list: prefer **≤ 30** strongest signals
- Domain / goal / style: **≤ 5** each unless the CV clearly supports more
- Veto / channel: **≤ 5** each; omit if unclear

## Language

- CV may be French or English; **emit facet values in English** for consistency with the rest of the product DB
