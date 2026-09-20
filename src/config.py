from __future__ import annotations

"""Configuration and environment management for Arcus trading infrastructure."""

from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file from project root if it exists
project_root = Path(__file__).resolve().parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)


class ArcusConfig(BaseSettings):
    """Arcus environment settings and credentials."""

    model_config = SettingsConfigDict(
        env_prefix="ARCUS_",
        env_file=str(env_file) if env_file.exists() else None,
        extra="ignore",
    )

    # Network & Environment
    environment: Literal["testnet", "mainnet"] = Field(
        default="testnet",
        description="Target Arcus environment ('testnet' or 'mainnet')",
    )

    testnet_rest_url: str = "https://api.testnet.arcus.xyz"
    testnet_ws_url: str = "wss://api.testnet.arcus.xyz/v1/ws"

    mainnet_rest_url: str = "https://api.arcus.xyz"
    mainnet_ws_url: str = "wss://api.arcus.xyz/v1/ws"

    # Credentials
    wallet_address: str = Field(
        default="0x0000000000000000000000000000000000000000",
        description="Master Ethereum address owning the API key",
    )
    account_index: int = Field(
        default=0, ge=0, le=9, description="Subaccount index (0-9)"
    )
    api_key: str = Field(
        default="", description="Ed25519 32-byte public key in 64-character hex"
    )
    api_private_key: str = Field(
        default="", description="Ed25519 32-byte private key in 64-character hex"
    )

    # Safety Guards
    paper_trading_mode: bool = Field(
        default=True,
        description="When true, simulate order execution and do not send mutating requests to venue",
    )
    mainnet_order_lock: bool = Field(
        default=True,
        description="Hard-coded block preventing mutating order requests on mainnet",
    )

    # Telemetry & Networking
    log_level: str = "INFO"
    request_timeout_secs: float = 10.0
    ws_ping_interval_secs: float = 30.0

    @field_validator("wallet_address")
    @classmethod
    def clean_address(cls, v: str) -> str:
        addr = v.strip().lower()
        if addr and not addr.startswith("0x"):
            addr = "0x" + addr
        return addr

    @field_validator("api_key", "api_private_key")
    @classmethod
    def clean_hex_keys(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def rest_url(self) -> str:
        """Active REST endpoint URL based on configured environment."""
        return (
            self.testnet_rest_url
            if self.environment == "testnet"
            else self.mainnet_rest_url
        )

    @property
    def ws_url(self) -> str:
        """Active WebSocket endpoint URL based on configured environment."""
        return (
            self.testnet_ws_url
            if self.environment == "testnet"
            else self.mainnet_ws_url
        )

    @property
    def has_credentials(self) -> bool:
        """Checks if authenticating credentials (wallet address, API key, private key) are set."""
        zero_addr = "0x0000000000000000000000000000000000000000"
        zero_key = "0" * 64
        return bool(
            self.wallet_address
            and self.wallet_address != zero_addr
            and self.api_key
            and self.api_key != zero_key
            and self.api_private_key
            and self.api_private_key != zero_key
        )


# Global settings instance singleton
settings = ArcusConfig()
