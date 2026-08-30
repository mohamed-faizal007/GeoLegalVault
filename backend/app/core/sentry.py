"""Sentry initialization (Plan Part 32). A no-op when SENTRY_DSN is unset —
local/dev and CI never need a Sentry account to run the app or the tests."""

from app.core.config import get_settings


def init_sentry() -> None:
    settings = get_settings()
    if not settings.SENTRY_DSN:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
