"""Tests for bluefinctl.core.system image-tag resolution.

Covers:
  - _tag_from_image_ref helper parses OCI refs correctly
  - get_system_info prefers the runtime bootc tag over build-time image-info.json
  - get_system_info falls back to image-info.json when bootc status lacks a tag
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from bluefinctl.core.system import SystemInfo, _tag_from_image_ref, get_system_info


def _make_image_info(tag: str = "latest") -> dict[str, Any]:
    return {
        "image-name": "bluefin",
        "image-tag": tag,
        "image-ref": "ostree-image-signed:docker://ghcr.io/projectbluefin/bluefin",
    }


def _bootc_status_json(image: str) -> bytes:
    return json.dumps(
        {
            "status": {
                "booted": {
                    "image": {
                        "image": {"image": image, "digest": "sha256:c0ffee"},
                    },
                },
            },
        }
    ).encode()


class TestTagFromImageRef:
    def test_extracts_standard_tag(self) -> None:
        assert _tag_from_image_ref("ghcr.io/projectbluefin/bluefin:testing") == "testing"

    def test_extracts_registry_port_tag(self) -> None:
        assert _tag_from_image_ref("registry:5000/bluefin:testing") == "testing"

    def test_returns_none_for_digest_ref(self) -> None:
        assert _tag_from_image_ref("ghcr.io/projectbluefin/bluefin@sha256:c0ffee") is None

    def test_returns_none_for_bare_ref(self) -> None:
        assert _tag_from_image_ref("ghcr.io/projectbluefin/bluefin") is None


class TestGetSystemInfoImageTag:
    @pytest.mark.asyncio
    async def test_prefers_bootc_status_tag(self) -> None:
        """Runtime tag from bootc status should override build-time image-info."""
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(
            return_value=(_bootc_status_json("ghcr.io/projectbluefin/bluefin:testing"), b"")
        )

        with (
            patch(
                "bluefinctl.core.system._read_image_info", return_value=_make_image_info("latest")
            ),
            patch("bluefinctl.core.system._detect_gpu", return_value=AsyncMock()),
            patch("bluefinctl.core.system._check_devmode", return_value=False),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)),
            patch("socket.gethostname", return_value="test-host"),
        ):
            info = await get_system_info()

        assert isinstance(info, SystemInfo)
        assert info.image_tag == "testing"

    @pytest.mark.asyncio
    async def test_falls_back_to_image_info_when_no_bootc_tag(self) -> None:
        """When bootc status has no tag, keep build-time image-info tag."""
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(
            return_value=(_bootc_status_json("ghcr.io/projectbluefin/bluefin"), b"")
        )

        with (
            patch(
                "bluefinctl.core.system._read_image_info", return_value=_make_image_info("latest")
            ),
            patch("bluefinctl.core.system._detect_gpu", return_value=AsyncMock()),
            patch("bluefinctl.core.system._check_devmode", return_value=False),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)),
            patch("socket.gethostname", return_value="test-host"),
        ):
            info = await get_system_info()

        assert isinstance(info, SystemInfo)
        assert info.image_tag == "latest"

    @pytest.mark.asyncio
    async def test_falls_back_to_image_info_when_bootc_missing(self) -> None:
        """If bootc CLI is unavailable, use build-time image-info tag."""
        proc = AsyncMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"no bootc"))

        with (
            patch(
                "bluefinctl.core.system._read_image_info",
                return_value={"image-name": "bluefin", "image-tag": "stable"},
            ),
            patch("bluefinctl.core.system._detect_gpu", return_value=AsyncMock()),
            patch("bluefinctl.core.system._check_devmode", return_value=False),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)),
            patch("socket.gethostname", return_value="test-host"),
        ):
            info = await get_system_info()

        assert isinstance(info, SystemInfo)
        assert info.image_tag == "stable"
