---
name: ai-stacks
description: >-
  AI stack management for bluefinctl — GPU detection, bundled quadlet catalog,
  variable substitution, auth, deploy flow, and status detection. Use when
  working in screens/ai.py or core/ai.py, adding new stacks, debugging
  deploy failures, or extending the AI Tools registry.
metadata:
  type: reference
---

# AI Stacks — Agent Skill

## When to Use

- Working in `screens/ai.py` or `core/ai.py`
- Adding a new stack to `stacks/nvidia/` or `stacks/amd/`
- Debugging deploy / stop failures
- Extending `AI_TOOL_REGISTRY` with new tools
- Checking GPU detection or CDI/KFD availability

## When NOT to Use

- General Textual patterns → `.agents/skills/bluefinctl-dev/SKILL.md`
- Homebrew kit management → `.agents/skills/bluefinctl-dev/SKILL.md`

## What this covers

`core/ai.py` + `screens/ai.py` + `stacks/` — GPU-accelerated AI stack management.

## Bundled stack catalog

```
stacks/
├── nvidia/
│   ├── nim-llama3/          nim-llama3.container + nim-llama3-network.network + stack.env
│   ├── nim-sdxl/
│   ├── pytorch-lab/
│   ├── nemo-training/
│   ├── triton-serving/
│   ├── tensorflow-lab/
│   └── rapids-ds/
└── amd/
    ├── lemonade/
    ├── ollama/
    ├── llama-strix/
    ├── llama-vulkan/
    ├── pytorch-lab/
    └── vllm/
```

Discovery: `_discover_stacks()` checks system dirs first (`/usr/share/ublue-os/nvidia-stacks/`, `/usr/share/ublue-os/amd-stacks/`), falls back to bundled `stacks/` if not found.

## Variable substitution

Deploy copies quadlet files to `~/.config/containers/systemd/` substituting:

| Variable | Source |
|---|---|
| `${NGC_MONTH}` | `stacks/nvidia/ngc-month` file |
| `${ROCM_VERSION}` | `stacks/amd/rocm-version` file |

`_copy_quadlets()` reads these files and does a string replace before writing.

## Auth

```python
from bluefinctl.core.ai import check_ngc_secret

# Returns True if podman secret "ngc-api-key" exists
has_ngc = await check_ngc_secret()

# Create via: podman secret create ngc-api-key <file>
```

NGC auth required for NIM stacks (`STACK_REQUIRES_NGC_AUTH=true` in stack.env).

## Deploy flow

```
Preflight checks:
  1. GPU vendor detected (NVIDIA CDI / AMD KFD / Intel)
  2. VRAM >= STACK_VRAM_GB (warn if not, allow override)
  3. Ports not in use
  4. Disk space estimate
  5. Auth tokens if required

Deploy (OperationModal steps):
  1. _copy_quadlets() → ~/.config/containers/systemd/
  2. systemctl --user daemon-reload
  3. podman pull <image>  (PodmanPullParser for progress)
  4. systemctl --user start <pod>
  5. Verify pod is running

Failure rollback:
  - Remove copied quadlet files
  - daemon-reload to clean state
```

## Status detection

```python
# Pod running check
proc = await asyncio.create_subprocess_exec(
    "systemctl", "--user", "is-active", f"{stack_name}-pod.service",
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
)
stdout, _ = await proc.communicate()
is_running = proc.returncode == 0 and stdout.decode().strip() == "active"
```

## Image tag format (rollback calendar)

Bluefin daily builds use date-tagged images: `ghcr.io/projectbluefin/dakota:latest.20260113`. The rollback calendar uses `skopeo inspect --raw` to discover available tags from the registry.

## AI Tools registry gap

`AI_TOOL_REGISTRY` in `core/ai.py` currently has 6 entries. The full `ai-tools.Brewfile` has 21+ tools.

To add a tool:
```python
AITool(
    slug="ramalama",
    command="ramalama",
    name="Ramalama",
    description="Run AI models locally — NVIDIA CDI and AMD ROCm",
    category="Local LLM",
    installed=False,
    source=BUNDLE_AI_TOOLS_SOURCE,
),
```
Detection: `shutil.which(tool.command)` for brew tools; flatpak tools need `flatpak list --app` check.

## Common mistakes

| Mistake | Fix |
|---|---|
| Calling deploy from button handler without `@work` | `push_screen_wait` in deploy flow requires `@work(exclusive=True)` |
| Hardcoding `/usr/share/ublue-os/nvidia-stacks/` path | Use `_discover_stacks()` which handles both system and bundled |
| `systemctl start` without `--user` flag | AI stacks are user-level systemd units |
| Forgetting `daemon-reload` after copy | Quadlet files require daemon-reload before start |

## Red Flags

- New stack added to `stacks/` without a `stack.env` file
- Deploy action calls `push_screen_wait` without `@work`
- `AI_TOOL_REGISTRY` and `ai-tools.Brewfile` diverge further (check both when adding tools)

## Verification

After AI stack changes:

- [ ] `pytest tests/test_ai.py` passing
- [ ] `ruff` and `mypy` clean
- [ ] GPU detection returns correct vendor on target hardware
- [ ] Stack appears in catalog with correct VRAM badge
- [ ] Deploy smoke test: stack starts, port opens, stop works
