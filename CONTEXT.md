# bluefinctl — Domain Glossary

## Terms

**DX (Developer Experience)**
The curated set of tools, container environments, and workflows that Bluefin provides for developers. Surfaced through the Developer screen in bluefinctl.

**Feature Portal**
The Developer screen's design pattern: each section presents a named Bluefin capability with a one-line pitch, not a generic software catalog.

**WSL Mode**
A zero-configuration Lima Ubuntu VM that replicates the Windows Subsystem for Linux experience on Bluefin. Persistent VM, home directory mounted, VS Code Remote SSH wired automatically. Entry point: `limactl shell ubuntu`.

**Smart Reboot**
A set of strategies that apply staged OS updates at moments when the user is not actively using their computer (logout, scheduled window), so reboots are invisible. Implemented as systemd user services/timers.

**OpsBar**
The bottom status bar in bluefinctl. The single source of operation feedback: install progress, update status, error messages. No in-app toasts; all user-facing notifications go to the system notification daemon via notify-send.

**Staged Update**
An OS image that has been downloaded and is ready to apply on next reboot (bootc staged). Distinct from an available update that has not yet been applied.

**dx-group**
Silent background provisioning of Linux groups (docker, libvirt, incus-admin, dialout) that DX tools require. Runs invisibly when the Developer screen loads. Users never see it.
