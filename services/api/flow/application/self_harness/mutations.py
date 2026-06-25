"""Apply a HarnessEdit to an agent_config — the missing "apply" layer.

Pure functions: the input config is never mutated; a deep-copied, edited config
is returned. Only the four config surfaces are handled here; "skill" edits are
DB-backed and routed elsewhere by the orchestrator.
"""

from __future__ import annotations

import copy

from flow.application.self_harness.types import CONFIG_SURFACES, HarnessEdit


def apply_edit(config: dict, edit: HarnessEdit) -> dict:
    """Return a new agent_config with ``edit`` applied. Does not mutate ``config``.

    Raises ValueError for surfaces this function does not handle (e.g. "skill").
    """
    if edit.surface not in CONFIG_SURFACES:
        raise ValueError(f"apply_edit does not handle surface {edit.surface!r}")

    new = copy.deepcopy(config) if config else {}

    if edit.surface == "system_prompt":
        new["system_prompt"] = str(edit.payload.get("system_prompt", new.get("system_prompt", "")))

    elif edit.surface == "loops":
        # target is "loops:<key>" — e.g. loops:max_tool_iters
        key = edit.target.split(":", 1)[1] if ":" in edit.target else edit.target
        loops = dict(new.get("loops") or {})
        loops[key] = edit.payload.get("value")
        new["loops"] = loops

    elif edit.surface == "tools":
        # target is "tool:<name>"
        name = edit.target.split(":", 1)[1] if ":" in edit.target else edit.target
        tools = dict(new.get("tools") or {})
        tools[name] = bool(edit.payload.get("enabled"))
        new["tools"] = tools

    elif edit.surface == "temperature":
        temp = float(edit.payload.get("value"))
        # agent_config carries the model under "llm_config" or legacy "model".
        for key in ("llm_config", "model"):
            sub = new.get(key)
            if isinstance(sub, dict):
                sub = dict(sub)
                sub["temperature"] = temp
                new[key] = sub
                break
        else:
            new["llm_config"] = {"temperature": temp}

    return new
