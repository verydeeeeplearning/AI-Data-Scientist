"""Tests for SSRF guard on skill.importUrl RPC handler."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from ds_agent.api.ws_handler import _validate_skill_import_url


# ---------------------------------------------------------------------------
# Helper: build a fake socket.getaddrinfo return value for a given IP string
# ---------------------------------------------------------------------------
def _fake_addrinfo(ip: str):
    """Return a minimal getaddrinfo-shaped list for the given IP."""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 0, "", (ip, 0))]


# ---------------------------------------------------------------------------
# Tests: valid public URL
# ---------------------------------------------------------------------------
class TestValidPublicUrl:
    def test_public_ipv4_passes(self):
        """A well-known public IP should pass validation without error."""
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("93.184.216.34")):
            _validate_skill_import_url("https://example.com/skill.md")  # must not raise

    def test_http_scheme_accepted(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("93.184.216.34")):
            _validate_skill_import_url("http://example.com/skill.md")  # must not raise


# ---------------------------------------------------------------------------
# Tests: scheme rejection
# ---------------------------------------------------------------------------
class TestSchemeRejection:
    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="scheme.*file.*not allowed|only http"):
            _validate_skill_import_url("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValueError, match="scheme.*ftp.*not allowed|only http"):
            _validate_skill_import_url("ftp://example.com/skill.md")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(ValueError, match="scheme.*javascript.*not allowed|only http"):
            _validate_skill_import_url("javascript:alert(1)")


# ---------------------------------------------------------------------------
# Tests: loopback rejection
# ---------------------------------------------------------------------------
class TestLoopbackRejection:
    def test_localhost_ipv4_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("127.0.0.1")):
            with pytest.raises(ValueError, match="loopback"):
                _validate_skill_import_url("http://localhost/skill.md")

    def test_loopback_127_0_0_2_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("127.0.0.2")):
            with pytest.raises(ValueError, match="loopback"):
                _validate_skill_import_url("http://internal.local/skill.md")

    def test_ipv6_loopback_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("::1")):
            with pytest.raises(ValueError, match="loopback"):
                _validate_skill_import_url("http://[::1]/skill.md")


# ---------------------------------------------------------------------------
# Tests: RFC 1918 private ranges
# ---------------------------------------------------------------------------
class TestPrivateIpRejection:
    def test_10_x_x_x_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("10.0.0.1")):
            with pytest.raises(ValueError, match="private"):
                _validate_skill_import_url("http://internal.corp/skill.md")

    def test_172_16_x_x_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("172.16.0.1")):
            with pytest.raises(ValueError, match="private"):
                _validate_skill_import_url("http://dev.corp/skill.md")

    def test_192_168_x_x_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("192.168.1.1")):
            with pytest.raises(ValueError, match="private"):
                _validate_skill_import_url("http://router.local/skill.md")

    def test_rfc1918_upper_172_31_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("172.31.255.255")):
            with pytest.raises(ValueError, match="private"):
                _validate_skill_import_url("http://edge.corp/skill.md")


# ---------------------------------------------------------------------------
# Tests: link-local (includes cloud metadata 169.254.169.254)
# ---------------------------------------------------------------------------
class TestLinkLocalRejection:
    def test_aws_metadata_endpoint_rejected(self):
        """169.254.169.254 is link-local and must be blocked."""
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("169.254.169.254")):
            with pytest.raises(ValueError, match="link-local"):
                _validate_skill_import_url("http://169.254.169.254/latest/meta-data/")

    def test_link_local_range_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("169.254.1.1")):
            with pytest.raises(ValueError, match="link-local"):
                _validate_skill_import_url("http://apipa.local/skill.md")

    def test_ipv6_link_local_rejected(self):
        with patch("socket.getaddrinfo", return_value=_fake_addrinfo("fe80::1")):
            with pytest.raises(ValueError, match="link-local"):
                _validate_skill_import_url("http://[fe80::1]/skill.md")
