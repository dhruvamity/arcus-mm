from __future__ import annotations

import unittest
from scripts.secret_scan import scan_content, is_dummy
from scripts.generate_repo_bundle import is_excluded


class TestSecurityScanner(unittest.TestCase):
    """Verifies security scanner rules, secret detection, and bundle exclusion policies."""

    def test_arcus_env_var_detection(self):
        code = 'ARCUS_API_KEY = "my_super_secret_arcus_key_12345"\n'
        findings = scan_content("src/test_module.py", code)
        self.assertEqual(len(findings), 1)
        filename, lineno, rule, length = findings[0]
        self.assertEqual(rule, "ARCUS_CREDENTIAL_VAR")
        self.assertEqual(lineno, 1)
        self.assertEqual(length, len("my_super_secret_arcus_key_12345"))

    def test_hex64_key_assignment(self):
        code = 'VENUE_SECRET_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"\n'
        findings = scan_content("src/test_module.py", code)
        self.assertEqual(len(findings), 1)
        _, _, rule, length = findings[0]
        self.assertEqual(rule, "HEX64_KEY_ASSIGNMENT")
        self.assertEqual(length, 64)

    def test_eth_address_outside_fixtures(self):
        code = 'target_wallet = "0x1234567890abcdef1234567890abcdef12345678"\n'
        # Outside fixtures -> flagged
        findings = scan_content("src/active_trading.py", code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][2], "ETH_ADDRESS_OUTSIDE_FIXTURES")

        # Inside tests/ -> allowed if dummy or fixture
        findings_fixture = scan_content("tests/test_something.py", code)
        # Should not flag as ETH_ADDRESS_OUTSIDE_FIXTURES in tests
        self.assertEqual(len(findings_fixture), 0)

    def test_dummy_values_whitelisted(self):
        dummy_hex = "0" * 64
        dummy_addr = "0x" + "0" * 40
        self.assertTrue(is_dummy(dummy_hex))
        self.assertTrue(is_dummy(dummy_addr))

        code = f'DUMMY_KEY = "{dummy_hex}"\n'
        findings = scan_content("src/config.py", code)
        self.assertEqual(len(findings), 0)

    def test_ghp_token_detection(self):
        code = 'GITHUB_AUTH = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"\n'
        findings = scan_content("src/helper.py", code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][2], "GITHUB_TOKEN")

    def test_pem_block_detection(self):
        code = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n"
        findings = scan_content("src/crypto.py", code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][2], "PEM_PRIVATE_KEY")

    def test_bundle_exclusions(self):
        self.assertTrue(is_excluded(".env")[0])
        self.assertTrue(is_excluded(".env.local")[0])
        self.assertTrue(is_excluded(".env.production")[0])
        self.assertFalse(is_excluded(".env.example")[0])
        self.assertTrue(is_excluded("certs/server.pem")[0])
        self.assertTrue(is_excluded("config/jwt.key")[0])
        self.assertTrue(is_excluded("data/market_data.parquet")[0])
        self.assertTrue(is_excluded("data/raw/trades.jsonl")[0])
        self.assertTrue(is_excluded(".DS_Store")[0])
        self.assertFalse(is_excluded("src/auth.py")[0])
        self.assertFalse(is_excluded("configs/venue_verified.yaml")[0])


if __name__ == "__main__":
    unittest.main()
