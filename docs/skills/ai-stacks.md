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
- Debugging deploy / remove failures
- Extending `AI_TOOL_REGISTRY` with new tools
- Checking GPU detection or CDI/KFD availability

## When NOT to Use

- General Textual patterns → `.agents/skills/bluefinctl-dev/SKILL.md`
- Homebrew kit management → `.agents/skills/bluefinctl-dev/SKILL.md`

## What this covers

`core/ai.py` + `screens/ai.py` + `stacks/` — GPU-accelerated AI stack management.

## AMD deployment model

AMD is identical to NVIDIA: kernel driver on host, full ROCm userspace in containers.

- **Host**: `amdgpu` kernel module (in-tree, no DKMS), `/dev/kfd`, `/dev/dri/renderD128`
- **Containers**: Full ROCm userspace (HIP, pytorch-rocm, etc.)
- `rocm-smi` is NOT on the host — do not try to call it for version detection
- ROCm version is read from `stacks/amd/rocm-version` (bundled file, updated with stack bumps)

**render group**: `/dev/dri/renderD128` is owned by `root:render`. The deploy preflight
checks group membership via `grp.getgrnam("render")` and runs `pkexec usermod -aG render`
automatically if needed. The change is effective on next login — the current session does
not gain the group membership immediately, so the deploy may still fail for the current session.

## Bundled stack catalog

```
stacks/
├── nvidia/
│   ├── ngc-month              # e.g. "25.06" — substituted as ${NGC_MONTH}
│   ├── nim-llama3/
│   ├── nim-sdxl/
│   ├── pytorch-lab/
│   ├── nemo-training/
│   ├── triton-serving/
│   ├── tensorflow-lab/
│   └── rapids-ds/
└── amd/
    ├── rocm-version           # e.g. "7.2.4" — substituted as ${ROCM_VERSION}
    ├── lemonade/              # ROCm + Vulkan + NPU, OpenAI/Anthropic/Ollama APIs
    ├── ramalama/              # OCI-native, auto-detect ROCm (replaces Ollama)
    ├── llama-strix/           # STACK_ARCH=strix-halo, gfx1151 unified memory
    ├── llama-vulkan/          # STACK_ARCH=strix-halo, Vulkan/RADV, no KFD needed
    ├── pytorch-lab/           # docker.io/rocm/pytorch official image
    └── vllm/                  # PagedAttention, RX 7900 / MI series
```

**Discovery**: `_discover_stacks()` checks system dirs first (`/usr/share/ublue-os/nvidia-stacks/`,
`/usr/share/ublue-os/amd-stacks/`), falls back to bundled `stacks/<vendor>/` via
`importlib.resources` if the system dir is absent (dev machines, pre-install).

## stack.env fields

| Field | Required | Description |
|---|---|---|
| `STACK_NAME` | yes | Display name |
| `STACK_DESC` | yes | One-line description (shown in list, truncated to ~45 chars) |
| `STACK_LONG_DESC` | recommended | Multi-sentence description for the detail pane |
| `STACK_ARCH` | optional | Target architecture label, e.g. `strix-halo` — shown as badge |
| `STACK_CATEGORY` | yes | `serve` / `dev` / `train` / `nim` |
| `STACK_VRAM_GB` | yes | Minimum VRAM in GB |
| `STACK_DISK_GB` | yes | Approximate disk usage in GB |
| `STACK_PORTS` | yes | `name:port` comma-separated |
| `STACK_ORDER` | yes | Sort order (lower = first) |
| `STACK_REQUIRES_NGC_AUTH` | optional | `true` if NGC API key required |
| `STACK_REQUIRES_HF_AUTH` | optional | `true` if HuggingFace token required |

Stack-specific vars (e.g. `LLAMA_MODEL`, `VLLM_MODEL`) are also substituted into
the container file at deploy time — any `${VAR}` present in the `.container` file
is replaced from stack.env values.

## AIStack dataclass fields

```python
@dataclass
class AIStack:
    slug: str
    name: str
    description: str          # short, list view
    long_description: str     # full, detail pane
    arch: str                 # e.g. "strix-halo" — empty = any GPU
    category: StackCategory
    vram_gb: int
    disk_gb: int
    ports: dict[str, int]
    requires_ngc_auth: bool
    requires_hf_auth: bool
    requires_kfd: bool        # auto-detected: True if AddDevice=/dev/kfd in .container
    order: int
    container_file: str
    network_file: str
    status: StackStatus
```

`requires_kfd` is derived automatically from the container file — no stack.env field needed.

## Variable substitution

`_copy_quadlets()` performs three layers of substitution before writing to
`~/.config/containers/systemd/`:

| Variable | Source |
|---|---|
| `${NGC_MONTH}` | `stacks/nvidia/ngc-month` file |
| `${ROCM_VERSION}` | `stacks/amd/rocm-version` file |
| `${LLAMA_MODEL}`, `${VLLM_MODEL}`, etc. | stack's own `stack.env` values |

## GPU status bar (screens/ai.py)

`GpuStatusBar` is a **single-line** `Static` at the top of the Stacks tab — not an
`AdwPreferencesGroup`. Height is 1 row. AMD line example:

```
AMD Radeon RX 7900 XTX  24 GB  kfd: ok  render: ok  ROCm 7.2.4
```

If render group is missing: `render: [!] not in group` — preflight adds the user at deploy time, effective on next login.

## Stack lifecycle (toggle model)

Stacks are either **deployed** or **not deployed** — no persistent-but-stopped state.

| Action | Key | What it does |
|---|---|---|
| Deploy | Enter | Copy quadlets + daemon-reload + systemctl start |
| Remove | s | systemctl stop + disable + delete quadlet files + daemon-reload |
| Logs | l | journalctl --user for the stack's service |

`remove_stack_steps()` is the canonical function. `stop_stack_steps()` is an alias for
CLI backward compat.

## Deploy preflight — render group

When `stack.requires_kfd` is True and the user is not in the `render` group,
`deploy_stack_steps()` inserts a preflight step that runs:

```bash
pkexec usermod -aG render $USER
```

This is step 1 of 6 (vs 5 for stacks that don't need KFD). Failure is non-fatal —
deploy continues because `/dev/dri/renderD128` may still be world-accessible.

## Auth

```python
from bluefinctl.core.ai import check_ngc_secret

# Returns True if podman secret "ngc-api-key" exists
has_ngc = await check_ngc_secret()

# Create via: podman secret create ngc-api-key <file>
```

NGC auth required for NIM stacks (`STACK_REQUIRES_NGC_AUTH=true` in stack.env).

## AI Tools registry

`AI_TOOL_REGISTRY` in `core/ai.py`. Ollama is intentionally absent — use RamaLama stack.

To add a tool:
```python
AITool(
    slug="my-tool",
    command="my-tool",
    name="My Tool",
    description="What it does",
    category="Local AI",
    installed=False,
    source=BUNDLE_AI_TOOLS_SOURCE,
),
```
Detection: `shutil.which(tool.command)` for brew tools.

## Common mistakes

| Mistake | Fix |
|---|---|
| Calling deploy from button handler without `@work` | `push_screen_wait` requires `@work(exclusive=True)` |
| Using `_discover_stacks()` with hardcoded system path | Function handles system → bundled fallback automatically |
| `systemctl start` without `--user` flag | AI stacks are user-level systemd units |
| Forgetting `daemon-reload` after copy | Quadlet files require daemon-reload before start |
| Adding Ollama back to registry | Ollama is intentionally removed — use RamaLama |
| Using AdwPreferencesGroup for GPU info | Use GpuStatusBar (single-line Static, height: 1) |
| Adding buttons to AI screen | No buttons — all actions are keyboard/footer only |

## Verification

After AI stack changes:

- [ ] `pytest tests/test_ai.py` passing
- [ ] `ruff check` and `mypy` clean
- [ ] AMD stacks load from bundled fallback when system dir absent
- [ ] Stack appears in catalog with correct VRAM badge and arch label if applicable
- [ ] `long_description` shows in detail pane
- [ ] Deploy smoke test: quadlet files written with correct substitutions, service starts
- [ ] Remove smoke test: service stopped, quadlet files deleted, daemon-reloaded
