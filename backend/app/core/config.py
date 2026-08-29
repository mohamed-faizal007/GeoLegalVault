"""Application settings, loaded from environment variables / .env.

Mirrors the env var list in .env.example exactly. In non-development
environments, placeholder values (e.g. "change_me") are rejected at
startup so the app fails fast instead of running with insecure defaults.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_VALUES = {"change_me", "0xCHANGE_ME", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Backend ---
    APP_ENV: str = "development"
    JWT_SECRET: str = "change_me"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "geolegalvault"

    # --- Storage (R2 / S3-compatible; MinIO for local dev) ---
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_REGION: str = "auto"
    STORAGE_BUCKET: str = "geolegalvault-dev"
    STORAGE_ACCESS_KEY: str = "change_me"
    STORAGE_SECRET_KEY: str = "change_me"
    STORAGE_PRESIGN_TTL_SEC: int = 60
    MAX_UPLOAD_MB: int = 10

    # --- Blockchain ---
    SEPOLIA_RPC_URL: str = "https://eth-sepolia.g.alchemy.com/v2/CHANGE_ME"
    SERVICE_WALLET_PRIVATE_KEY: str = "change_me"
    CONTRACT_ADDRESS: str = "0xCHANGE_ME"
    CHAIN_ID: int = 11155111
    ANCHOR_CONFIRMATIONS: int = 1
    # Local dev node used only for /health reachability probing (Phase 5 adds
    # real Hardhat + anchoring). Distinct from SEPOLIA_RPC_URL, the real testnet RPC.
    CHAIN_RPC_URL: str = "http://localhost:8545"

    # --- Geofence ---
    GEO_ACCURACY_MAX_M: int = 100
    GEO_FRESHNESS_MAX_SEC: int = 60

    # --- Observability ---
    SENTRY_DSN: str = ""

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _fail_fast_on_placeholders_outside_dev(self) -> "Settings":
        if self.APP_ENV == "development":
            return self

        required_non_placeholder = {
            "JWT_SECRET": self.JWT_SECRET,
            "MONGODB_URI": self.MONGODB_URI,
            "STORAGE_ACCESS_KEY": self.STORAGE_ACCESS_KEY,
            "STORAGE_SECRET_KEY": self.STORAGE_SECRET_KEY,
            "SEPOLIA_RPC_URL": self.SEPOLIA_RPC_URL,
            "SERVICE_WALLET_PRIVATE_KEY": self.SERVICE_WALLET_PRIVATE_KEY,
            "CONTRACT_ADDRESS": self.CONTRACT_ADDRESS,
        }
        placeholder_fields = [
            name
            for name, value in required_non_placeholder.items()
            if value in PLACEHOLDER_VALUES or "CHANGE_ME" in value.upper()
        ]
        if placeholder_fields:
            raise ValueError(
                f"APP_ENV={self.APP_ENV!r} requires real values for: "
                f"{', '.join(placeholder_fields)} (found placeholders)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
