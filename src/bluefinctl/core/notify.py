"""System notification helper.

Sends desktop notifications via notify-send. This is the ONLY mechanism
for user-facing notifications in bluefinctl. No in-app Textual toasts
should be used anywhere in the app.

Usage::

    from bluefinctl.core.notify import system_notify
    system_notify("Docker installed", "Ready to use")
    system_notify("Install failed", "brew exited 1", urgency="critical")
"""

from __future__ import annotations

import subprocess


def system_notify(title: str, body: str, urgency: str = "normal") -> None:
    """Send a desktop notification via notify-send.

    Args:
        title:   Notification title (app name prepended automatically).
        body:    Notification body text.
        urgency: low | normal | critical.  Defaults to "normal".
    """
    subprocess.run(
        [
            "notify-send",
            "--app-name=bluefinctl",
            f"--urgency={urgency}",
            title,
            body,
        ],
        check=False,
    )
