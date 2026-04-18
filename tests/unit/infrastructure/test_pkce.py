"""Tests for PKCE utilities — validates OpenClaw-compatible output."""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from ds_agent.infrastructure.auth.pkce import (
    build_auth_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)


class TestGenerateCodeVerifier:
    def test_length(self):
        verifier = generate_code_verifier()
        assert len(verifier) == 64  # 32 bytes hex-encoded

    def test_hex_charset(self):
        verifier = generate_code_verifier()
        assert all(c in "0123456789abcdef" for c in verifier)

    def test_uniqueness(self):
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2


class TestGenerateCodeChallenge:
    def test_sha256_base64url(self):
        verifier = "test_verifier_12345"
        challenge = generate_code_challenge(verifier)

        # Manually compute expected value
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected

    def test_no_padding(self):
        challenge = generate_code_challenge("any_verifier")
        assert "=" not in challenge

    def test_url_safe_chars(self):
        challenge = generate_code_challenge("another_verifier")
        assert "+" not in challenge
        assert "/" not in challenge


class TestGenerateState:
    def test_length(self):
        state = generate_state()
        assert len(state) == 64  # 32 bytes hex-encoded

    def test_uniqueness(self):
        s1 = generate_state()
        s2 = generate_state()
        assert s1 != s2


class TestBuildAuthUrl:
    def test_contains_all_params(self):
        url = build_auth_url(
            auth_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
            client_id="test-client-id",
            redirect_uri="http://localhost:8085/oauth2callback",
            scopes=["cloud-platform", "userinfo.email"],
            code_challenge="test-challenge",
            state="test-state",
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.hostname == "accounts.google.com"
        assert params["client_id"] == ["test-client-id"]
        assert params["response_type"] == ["code"]
        assert params["redirect_uri"] == ["http://localhost:8085/oauth2callback"]
        assert params["scope"] == ["cloud-platform userinfo.email"]
        assert params["code_challenge"] == ["test-challenge"]
        assert params["code_challenge_method"] == ["S256"]
        assert params["state"] == ["test-state"]
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]

    def test_custom_access_type(self):
        url = build_auth_url(
            auth_endpoint="https://example.com/auth",
            client_id="c",
            redirect_uri="http://localhost/cb",
            scopes=["s1"],
            code_challenge="ch",
            state="st",
            access_type="online",
            prompt="none",
        )
        params = parse_qs(urlparse(url).query)
        assert params["access_type"] == ["online"]
        assert params["prompt"] == ["none"]
