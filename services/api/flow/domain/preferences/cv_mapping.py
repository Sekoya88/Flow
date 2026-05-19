"""Map CV extraction shards to typed preference rows (class, value)."""

from __future__ import annotations

from flow.domain.preferences.cv_schemas import NarrativeCvShard, ToolingCvShard, VetoChannelCvShard

_MAX_VALUE_LEN = 200
_MAX_TOTAL = 80


def _clip(s: str) -> str:
    s = s.strip()
    if len(s) > _MAX_VALUE_LEN:
        return s[: _MAX_VALUE_LEN - 1].rstrip() + "…"
    return s


def _emit(class_: str, values: list[str], out: list[dict[str, str]], seen: set[tuple[str, str]]) -> None:
    for raw in values:
        val = _clip(raw)
        if not val:
            continue
        key = (class_, val.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"class": class_, "value": val})
        if len(out) >= _MAX_TOTAL:
            return


def shards_to_preference_rows(
    tooling: ToolingCvShard | None,
    narrative: NarrativeCvShard | None,
    veto_ch: VetoChannelCvShard | None,
) -> list[dict[str, str]]:
    """Flatten validated shards into {class, value} dicts ready for persistence."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    if tooling:
        _emit("tooling", tooling.items, out, seen)
    if narrative:
        _emit("domain", narrative.domains, out, seen)
        _emit("goal", narrative.goals, out, seen)
        _emit("style", narrative.style_hints, out, seen)
    if veto_ch:
        _emit("veto", veto_ch.vetoes, out, seen)
        _emit("channel", veto_ch.channels, out, seen)

    return out
