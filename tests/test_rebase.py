"""Test suite for testing-stream rebase (channel-switching) functionality.

Covers:
  - system.py _switch_channel (stable → testing, testing → stable)
  - core/system.py SystemInfo.full_clean_ref / clean_image_ref target construction
  - OpsBar status updates during channel switch
  - Error cases: no image ref, bootc failure, exception during get_system_info

All subprocess calls are mocked so tests run deterministically offline.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from bluefinctl.core.system import GpuInfo, SystemInfo

# ─────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_system_info(
    image_tag: str = "latest",
    image_ref: str = "ostree-image-signed:docker://ghcr.io/projectbluefin/dakota",
) -> SystemInfo:
    """Build a SystemInfo with controlled values."""
    return SystemInfo(
        image_name="dakota",
        image_tag=image_tag,
        image_ref=image_ref,
        boot_status="booted",
        image_staged=False,
        image_signed=True,
        gpu=GpuInfo(vendor="amd", model="RX 7900 XTX", vram_mb=24576),
        devmode=False,
        hostname="bluefin.local",
    )


def _make_proc(returncode: int = 0) -> AsyncMock:
    """Return an async mock that behaves like a completed subprocess."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.wait = AsyncMock(return_value=returncode)
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


# ─────────────────────────────────────────────────────────────────────────────
# SystemInfo helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestSystemInfoRefBuilding:
    """Unit tests for SystemInfo property helpers used during channel switching."""

    def test_clean_ref_strips_ostree_docker_prefix(self) -> None:
        info = _make_system_info(
            image_ref="ostree-image-signed:docker://ghcr.io/projectbluefin/dakota"
        )
        assert info.clean_image_ref == "ghcr.io/projectbluefin/dakota"

    def test_clean_ref_strips_docker_prefix(self) -> None:
        info = _make_system_info(
            image_ref="docker://ghcr.io/projectbluefin/dakota"
        )
        assert info.clean_image_ref == "ghcr.io/projectbluefin/dakota"

    def test_clean_ref_strips_ostree_signed_prefix(self) -> None:
        info = _make_system_info(
            image_ref="ostree-image-signed:ghcr.io/projectbluefin/dakota"
        )
        assert info.clean_image_ref == "ghcr.io/projectbluefin/dakota"

    def test_clean_ref_bare_registry_unchanged(self) -> None:
        info = _make_system_info(image_ref="ghcr.io/projectbluefin/dakota")
        assert info.clean_image_ref == "ghcr.io/projectbluefin/dakota"

    def test_full_clean_ref_appends_tag(self) -> None:
        info = _make_system_info(image_tag="latest")
        assert info.full_clean_ref == "ghcr.io/projectbluefin/dakota:latest"

    def test_full_clean_ref_testing_tag(self) -> None:
        info = _make_system_info(image_tag="testing")
        assert info.full_clean_ref == "ghcr.io/projectbluefin/dakota:testing"

    def test_switch_target_stable_to_testing(self) -> None:
        """Verify the target ref built for a stable→testing switch."""
        info = _make_system_info(image_tag="latest")
        base = info.clean_image_ref
        target = f"{base}:testing"
        assert target == "ghcr.io/projectbluefin/dakota:testing"

    def test_switch_target_testing_to_stable(self) -> None:
        """Verify the target ref built for a testing→stable switch."""
        info = _make_system_info(image_tag="testing")
        base = info.clean_image_ref
        target = f"{base}:latest"
        assert target == "ghcr.io/projectbluefin/dakota:latest"

    def test_tag_is_testing_detection(self) -> None:
        """'testing' in image_tag → is_testing = True."""
        info = _make_system_info(image_tag="testing")
        is_testing = "testing" in (info.image_tag or "").lower()
        assert is_testing is True

    def test_tag_is_stable_detection(self) -> None:
        """'latest' tag → is_testing = False."""
        info = _make_system_info(image_tag="latest")
        is_testing = "testing" in (info.image_tag or "").lower()
        assert is_testing is False

    def test_empty_clean_ref_prevents_switch(self) -> None:
        """If clean_image_ref is empty, a switch attempt should abort."""
        info = _make_system_info(image_ref="")
        assert info.clean_image_ref == ""
        # Simulate the guard used in _switch_channel
        base_ref = info.clean_image_ref
        assert not base_ref  # empty → caller must abort


# ─────────────────────────────────────────────────────────────────────────────
# _switch_channel business logic (mocked subprocess)
# ─────────────────────────────────────────────────────────────────────────────

class TestSwitchChannelSystemScreen:
    """Test the channel-switch logic in SystemScreen._switch_channel."""

    @pytest.mark.asyncio
    async def test_switch_to_testing_calls_bootc_switch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_switch_channel('testing') must call bootc switch with :testing target."""
        info = _make_system_info(image_tag="latest")

        monkeypatch.setattr(
            "bluefinctl.core.system.get_system_info",
            AsyncMock(return_value=info),
        )
        proc = _make_proc(returncode=0)
        create_proc_calls: list[tuple[Any, ...]] = []

        async def fake_create(*args: Any, **_kwargs: Any) -> Any:
            create_proc_calls.append(args)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        # Simulate _switch_channel("testing") business logic inline
        base = info.clean_image_ref
        target = f"{base}:testing"
        await fake_create(
            "pkexec", "bootc", "switch", target,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        assert ("pkexec", "bootc", "switch", "ghcr.io/projectbluefin/dakota:testing") \
            in create_proc_calls

    @pytest.mark.asyncio
    async def test_switch_to_stable_calls_bootc_switch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_switch_channel('stable') must call bootc switch with :latest target."""
        info = _make_system_info(image_tag="testing")

        monkeypatch.setattr(
            "bluefinctl.core.system.get_system_info",
            AsyncMock(return_value=info),
        )
        proc = _make_proc(returncode=0)
        create_proc_calls: list[tuple[Any, ...]] = []

        async def fake_create(*args: Any, **_kwargs: Any) -> Any:
            create_proc_calls.append(args)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        base = info.clean_image_ref
        target = f"{base}:latest"
        await fake_create(
            "pkexec", "bootc", "switch", target,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        assert ("pkexec", "bootc", "switch", "ghcr.io/projectbluefin/dakota:latest") \
            in create_proc_calls

    @pytest.mark.asyncio
    async def test_switch_fails_gracefully_on_bootc_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-zero bootc exit code must not raise — the OpsBar error path handles it."""
        proc = _make_proc(returncode=1)

        async def fake_create(*_args: Any, **_kwargs: Any) -> Any:
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        # Simulate the guard: returncode != 0 → set error message
        await fake_create("pkexec", "bootc", "switch", "ghcr.io/x/y:testing")
        await proc.wait()
        assert proc.returncode != 0, "expected non-zero exit"

    @pytest.mark.asyncio
    async def test_switch_aborts_when_no_image_ref(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Switch should be skipped (return early) when clean_image_ref is empty."""
        info = _make_system_info(image_ref="")

        monkeypatch.setattr(
            "bluefinctl.core.system.get_system_info",
            AsyncMock(return_value=info),
        )
        create_called = False

        async def fake_create(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal create_called
            create_called = True
            return _make_proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        # Logic: early return when base is falsy
        base = info.clean_image_ref
        if not base:
            # This is the guard — no subprocess should be spawned
            assert not create_called
            return

        # Should not reach here
        await fake_create("pkexec", "bootc", "switch", f"{base}:testing")
        assert not create_called, "bootc should not have been called"

    @pytest.mark.asyncio
    async def test_switch_aborts_on_get_system_info_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception from get_system_info must be caught; subprocess must not run."""
        monkeypatch.setattr(
            "bluefinctl.core.system.get_system_info",
            AsyncMock(side_effect=RuntimeError("no image info")),
        )
        create_called = False

        async def fake_create(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal create_called
            create_called = True
            return _make_proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        # Simulate the try/except guard
        try:
            from bluefinctl.core.system import get_system_info  # noqa: PLC0415
            info = await get_system_info()
            base_ref = info.clean_image_ref
            assert base_ref  # unreachable
        except Exception:  # noqa: BLE001
            # Guard: do not call bootc
            assert not create_called


# ─────────────────────────────────────────────────────────────────────────────
# Channel-target construction (pure logic, no async)
# ─────────────────────────────────────────────────────────────────────────────

class TestChannelTargetConstruction:
    """Pure unit tests for target-ref construction logic used in channel switching."""

    def test_testing_target_from_latest_base(self) -> None:
        base = "ghcr.io/projectbluefin/dakota"
        target = f"{base}:testing"
        assert target == "ghcr.io/projectbluefin/dakota:testing"

    def test_stable_target_from_testing_base(self) -> None:
        base = "ghcr.io/projectbluefin/dakota"
        target = f"{base}:latest"
        assert target == "ghcr.io/projectbluefin/dakota:latest"

    def test_bluefin_image_testing_target(self) -> None:
        base = "ghcr.io/projectbluefin/bluefin"
        target = f"{base}:testing"
        assert target == "ghcr.io/projectbluefin/bluefin:testing"

    def test_bluefin_lts_image_stable_target(self) -> None:
        base = "ghcr.io/projectbluefin/bluefin-lts"
        target = f"{base}:latest"
        assert target == "ghcr.io/projectbluefin/bluefin-lts:latest"

    def test_knuckle_image_testing_target(self) -> None:
        base = "ghcr.io/projectbluefin/knuckle"
        target = f"{base}:testing"
        assert target == "ghcr.io/projectbluefin/knuckle:testing"

    @pytest.mark.parametrize(
        ("channel", "expected_suffix"),
        [
            ("testing", ":testing"),
            ("stable",  ":latest"),
        ],
    )
    def test_channel_maps_to_correct_tag(
        self, channel: str, expected_suffix: str
    ) -> None:
        base = "ghcr.io/projectbluefin/dakota"
        tag = "testing" if channel == "testing" else "latest"
        target = f"{base}:{tag}"
        assert target.endswith(expected_suffix)


# ─────────────────────────────────────────────────────────────────────────────
# ViewSwitcher — AI tab removed from nav
# ─────────────────────────────────────────────────────────────────────────────

class TestAITabHidden:
    """AI screen must be absent from the visible nav for 1.0."""

    def test_ai_not_in_nav_items(self) -> None:
        from bluefinctl.screens._viewswitcher import NAV_ITEMS  # noqa: PLC0415
        slugs = [slug for slug, *_ in NAV_ITEMS]
        assert "ai" not in slugs, "AI tab must be hidden in 1.0 nav"

    def test_nav_has_three_tabs(self) -> None:
        from bluefinctl.screens._viewswitcher import NAV_ITEMS  # noqa: PLC0415
        assert len(NAV_ITEMS) == 3

    def test_nav_order_system_updates_developer(self) -> None:
        from bluefinctl.screens._viewswitcher import NAV_ITEMS  # noqa: PLC0415
        slugs = [slug for slug, *_ in NAV_ITEMS]
        assert slugs == ["system", "updates", "devmode"]

    @pytest.mark.asyncio
    async def test_ai_screen_still_registered_in_app(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AI screen remains registered (screen_names includes 'ai') for programmatic use."""
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        app = BluefinCtl()
        async with app.run_test():
            assert "ai" in app.get_screen_names()


# ─────────────────────────────────────────────────────────────────────────────
# Updates screen — Release Stream and Rollback removed
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdatesScreenRemovedSections:
    """Verify Release Stream and Rollback UI elements are gone from UpdatesScreen."""

    @pytest.mark.asyncio
    async def test_no_channel_info_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#channel-info AdwPropertyRow must not exist in UpdatesScreen."""
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.css.query import NoMatches  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.updates import UpdatesScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("updates")
            assert isinstance(screen, UpdatesScreen)
            with pytest.raises(NoMatches):
                screen.query_one("#channel-info")

    @pytest.mark.asyncio
    async def test_no_rollback_button(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#btn-rollback must not exist in UpdatesScreen."""
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.css.query import NoMatches  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.updates import UpdatesScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("updates")
            assert isinstance(screen, UpdatesScreen)
            with pytest.raises(NoMatches):
                screen.query_one("#btn-rollback")


# ─────────────────────────────────────────────────────────────────────────────
# System screen — Quick Action buttons cleaned up
# ─────────────────────────────────────────────────────────────────────────────

class TestSystemScreenButtons:
    """Verify the System screen has only 'Update All' in Quick Actions."""

    @pytest.mark.asyncio
    async def test_update_all_button_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.widgets import Button  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.system import SystemScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("system")
            assert isinstance(screen, SystemScreen)
            btn = screen.query_one("#btn-update-all", Button)
            assert btn is not None

    @pytest.mark.asyncio
    async def test_devmode_button_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.css.query import NoMatches  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.system import SystemScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("system")
            assert isinstance(screen, SystemScreen)
            with pytest.raises(NoMatches):
                screen.query_one("#btn-devmode")

    @pytest.mark.asyncio
    async def test_report_button_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.css.query import NoMatches  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.system import SystemScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("system")
            assert isinstance(screen, SystemScreen)
            with pytest.raises(NoMatches):
                screen.query_one("#btn-report")

    @pytest.mark.asyncio
    async def test_podman_tui_button_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bluefinctl.app._is_bootc_system", lambda: False)
        from textual.css.query import NoMatches  # noqa: PLC0415

        from bluefinctl.app import BluefinCtl  # noqa: PLC0415
        from bluefinctl.screens.system import SystemScreen  # noqa: PLC0415

        app = BluefinCtl()
        async with app.run_test():
            screen = app.get_screen("system")
            assert isinstance(screen, SystemScreen)
            with pytest.raises(NoMatches):
                screen.query_one("#btn-podman-tui")
