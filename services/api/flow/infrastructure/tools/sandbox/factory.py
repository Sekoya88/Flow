from __future__ import annotations

import warnings

from .base import Sandbox

_instance: Sandbox | None = None


def get_sandbox() -> Sandbox:
    global _instance
    if _instance is None:
        _instance = _build()
    return _instance


def _build() -> Sandbox:
    from flow.config import get_settings
    settings = get_settings()
    driver = settings.sandbox_driver

    if driver == "e2b":
        if not settings.e2b_api_key:
            raise RuntimeError("FLOW_E2B_API_KEY required when FLOW_SANDBOX_DRIVER=e2b")
        from .e2b_sandbox import E2BSandbox
        return E2BSandbox(api_key=settings.e2b_api_key)

    if driver == "docker":
        from .docker_sandbox import DockerSandbox
        return DockerSandbox()

    warnings.warn(
        "FLOW_SANDBOX_DRIVER=unsafe — code runs on the host with no isolation. "
        "Set FLOW_SANDBOX_DRIVER=e2b or docker for production.",
        stacklevel=2,
    )
    from .unsafe import UnsafeSandbox
    return UnsafeSandbox()
