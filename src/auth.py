"""Authentication and signing engine for Arcus perpetuals.

Implements Ed25519 key management, Scheme 1 (typed payload) signing,
and Scheme 2 (legacy message) signing according to official Arcus specifications.
"""

from typing import Dict, Any, Optional, Tuple, Union
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from src.utils import canonical_json, now_ns, good_til_time_nanos


class ArcusSigner:
    """Ed25519 signer for Arcus REST and WebSocket requests."""

    def __init__(self, private_key: Union[str, bytes, ed25519.Ed25519PrivateKey]):
        """Initializes signer from hex string (64 chars), raw 32 bytes, or Ed25519PrivateKey object."""
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            self._priv = private_key
        elif isinstance(private_key, str):
            priv_hex = private_key.strip()
            if len(priv_hex) == 64:
                raw_bytes = bytes.fromhex(priv_hex)
                self._priv = ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
            else:
                # Try loading as PEM
                self._priv = serialization.load_pem_private_key(priv_hex.encode(), password=None)
        elif isinstance(private_key, bytes):
            self._priv = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        else:
            raise TypeError("private_key must be hex string, raw bytes, or Ed25519PrivateKey")

        self._pub = self._priv.public_key()
        self.api_key = self._pub.public_bytes_raw().hex()

    @classmethod
    def generate(cls) -> "ArcusSigner":
        """Generates a new random Ed25519 key pair."""
        priv = ed25519.Ed25519PrivateKey.generate()
        return cls(priv)

    @property
    def private_key_hex(self) -> str:
        """Returns 32-byte private key as a 64-character hex string."""
        return self._priv.private_bytes_raw().hex()

    def sign_bytes(self, data: bytes) -> str:
        """Signs arbitrary bytes and returns 128-hex-character signature (64 bytes)."""
        return self._priv.sign(data).hex()

    def build_place_order_payload(
        self,
        address: str,
        account_index: int,
        market_id: int,
        side_int: int,
        price_ticks: int,
        quantity_quantums: int,
        tif_int: int,
        good_til_nanos: Optional[int] = None,
        reduce_only: int = 0,
        client_id: Optional[str] = None,
        timestamp_ns: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        """Constructs Scheme 1 canonical payload for placeOrder and signs it.

        Returns: (canonical_payload_json_str, signature_hex, timestamp_ns)
        """
        ts = timestamp_ns if timestamp_ns is not None else now_ns()
        g_nanos = good_til_nanos if good_til_nanos is not None else good_til_time_nanos()

        payload_dict: Dict[str, Any] = {
            "ad": address.lower(),
            "ai": int(account_index),
            "ct": int(ts),
            "g": int(g_nanos),
            "m": int(market_id),
            "op": 1,
            "p": int(price_ticks),
            "q": int(quantity_quantums),
            "r": int(reduce_only),
            "s": int(side_int),
            "t": int(tif_int),
            "v": 1,
        }
        if client_id:
            payload_dict["c"] = str(client_id)

        canonical_str = canonical_json(payload_dict)
        signature = self.sign_bytes(canonical_str.encode("utf-8"))
        return canonical_str, signature, ts

    def build_cancel_order_payload(
        self,
        address: str,
        account_index: int,
        market_id: int,
        order_id: Optional[str] = None,
        client_id: Optional[str] = None,
        timestamp_ns: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        """Constructs Scheme 1 canonical payload for cancelOrder and signs it.

        Exactly one of order_id or client_id must be provided.
        Returns: (canonical_payload_json_str, signature_hex, timestamp_ns)
        """
        if not order_id and not client_id:
            raise ValueError("Either order_id or client_id must be provided for cancellation")
        if order_id and client_id:
            raise ValueError("Provide exactly one of order_id or client_id, not both")

        ts = timestamp_ns if timestamp_ns is not None else now_ns()

        payload_dict: Dict[str, Any] = {
            "ad": address.lower(),
            "ai": int(account_index),
            "ct": int(ts),
            "m": int(market_id),
            "op": 2,
            "v": 1,
        }
        if order_id:
            payload_dict["id"] = str(order_id)
        if client_id:
            payload_dict["c"] = str(client_id)

        canonical_str = canonical_json(payload_dict)
        signature = self.sign_bytes(canonical_str.encode("utf-8"))
        return canonical_str, signature, ts

    def build_modify_order_payload(
        self,
        address: str,
        account_index: int,
        market_id: int,
        order_id: str,
        side_int: int,
        price_ticks: int,
        quantity_quantums: int,
        tif_int: int,
        good_til_nanos: int,
        reduce_only: int = 0,
        client_id: Optional[str] = None,
        timestamp_ns: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        """Constructs Scheme 1 canonical payload for modifyOrder and signs it.

        Returns: (canonical_payload_json_str, signature_hex, timestamp_ns)
        """
        ts = timestamp_ns if timestamp_ns is not None else now_ns()

        payload_dict: Dict[str, Any] = {
            "ad": address.lower(),
            "ai": int(account_index),
            "ct": int(ts),
            "g": int(good_til_nanos),
            "id": str(order_id),
            "m": int(market_id),
            "op": 3,
            "p": int(price_ticks),
            "q": int(quantity_quantums),
            "r": int(reduce_only),
            "s": int(side_int),
            "t": int(tif_int),
            "v": 1,
        }
        if client_id:
            payload_dict["c"] = str(client_id)

        canonical_str = canonical_json(payload_dict)
        signature = self.sign_bytes(canonical_str.encode("utf-8"))
        return canonical_str, signature, ts

    def sign_scheme_2(
        self,
        action: str,
        body: Dict[str, Any],
        timestamp_ns: Optional[int] = None,
    ) -> Tuple[str, int]:
        """Signs Scheme 2 legacy message: timestamp + action + canonical_json(body).

        Used for cancelAllOrders, setLeverage, scheduleCancel, and WS authenticate.
        Returns: (signature_hex, timestamp_ns)
        """
        ts = timestamp_ns if timestamp_ns is not None else now_ns()
        body_canonical = canonical_json(body)
        message = f"{ts}{action}{body_canonical}".encode("utf-8")
        signature = self.sign_bytes(message)
        return signature, ts

    def get_auth_headers(
        self,
        signature: str,
        timestamp_ns: int,
    ) -> Dict[str, str]:
        """Returns standard Arcus HTTP authentication headers."""
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "X-Timestamp": str(timestamp_ns),
            "X-Signature": signature,
        }
