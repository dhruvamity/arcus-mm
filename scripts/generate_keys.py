#!/usr/bin/env python3
"""Helper script to generate a new Ed25519 keypair for Arcus trading.

Outputs private signing key (to place in .env) and public API key.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import ArcusSigner


def main():
    print("=" * 70)
    print(" Arcus Ed25519 Keypair Generator")
    print("=" * 70)

    signer = ArcusSigner.generate()
    priv_hex = signer.private_key_hex
    pub_hex = signer.api_key

    print("\n✅ Fresh Ed25519 Keypair Generated Successfully!\n")
    print(f"API Public Key (ARCUS_API_KEY):\n  {pub_hex}\n")
    print(f"API Private Key (ARCUS_API_PRIVATE_KEY):\n  {priv_hex}\n")

    print("-" * 70)
    print("Next Steps to Register & Authorize this Key:")
    print("1. Option A (Recommended - Arcus Web App):")
    print("   - You can also simply go to: https://testnet.arcus.xyz/api-keys")
    print("   - Connect your wallet, click 'Generate' and copy the keys shown.")
    print("2. If using the keys generated above:")
    print("   - Put both keys in your '.env' file.")
    print("   - Put your connected Ethereum address in 'ARCUS_WALLET_ADDRESS'.")
    print("=" * 70)


if __name__ == "__main__":
    main()
