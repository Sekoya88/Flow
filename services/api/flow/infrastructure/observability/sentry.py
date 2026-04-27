from __future__ import annotations


def setup_sentry(dsn: str | None) -> None:
    if not dsn:
        return
    import sentry_sdk
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
