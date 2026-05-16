"""Time/date utilities: date_lookup."""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


async def run_date_lookup(
    expression: str = "now",
    from_tz: str = "UTC",
    to_tz: str = "UTC",
    output_format: str = "%Y-%m-%d %H:%M:%S %Z",
) -> dict:
    """Parse, convert, or format a date/time expression.

    Args:
        expression: Date string to parse, or "now" / "today" for current time.
        from_tz: Source timezone (IANA name, e.g. "America/New_York"). Default "UTC".
        to_tz: Target timezone for conversion. Default "UTC".
        output_format: strftime format string for the result.

    Returns:
        {"iso": str, "formatted": str, "timestamp_utc": float, "weekday": str}
    """
    try:
        src_tz = ZoneInfo(from_tz)
    except ZoneInfoNotFoundError:
        return {"error": f"Unknown timezone: {from_tz}"}
    try:
        dst_tz = ZoneInfo(to_tz)
    except ZoneInfoNotFoundError:
        return {"error": f"Unknown timezone: {to_tz}"}

    expr = expression.strip().lower()
    now = datetime.datetime.now(tz=src_tz)

    if expr in ("now", "today"):
        dt = now
    else:
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d %B %Y",
            "%B %d, %Y",
        ]
        dt = None
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(expression.strip(), fmt)
                dt = dt.replace(tzinfo=src_tz)
                break
            except ValueError:
                continue
        if dt is None:
            return {"error": f"Could not parse date expression: {expression!r}"}

    dt_converted = dt.astimezone(dst_tz)

    return {
        "iso": dt_converted.isoformat(),
        "formatted": dt_converted.strftime(output_format),
        "timestamp_utc": dt_converted.timestamp(),
        "weekday": dt_converted.strftime("%A"),
    }
