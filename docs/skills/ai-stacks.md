# AI Stacks — Agent Skill

Load when working on `core/ai.py`, `screens/ai.py`, or `src/bluefinctl/stacks/`.

## What this covers

GPU-accelerated AI workload management via Podman Quadlet user services.

- Stack discovery from system dirs or bundled catalog
- GPU detection (NVIDIA CDI / AMD KFD)
- NGC and HuggingFace auth
- Deploy / stop / remove lifecycle
- AI tool inventory (`ai-tools.Brewfile`)

## Bundled stack catalog

`src/bluefinctl/stacks/` ships quadlet files from closed PRs projectbluefin/common #676 (NVIDIA) and #684 (AMD).

| Vendor | Stack | VRAM | Category | Auth needed |
|--------|-------|------|----------|-------------|
| NVIDIA | NIM Llama 3.1 8B | 16 GB | nim | NGC key |
| NVIDIA | NIM SDXL | 8 GB | nim | NGC key |
| NVIDIA | PyTorch Lab | 8 GB | dev | — |
| NVIDIA | TensorFlow Lab | 8 GB | dev | — |
| NVIDIA | RAPIDS Data Science | 8 GB | dev | — |
| NVIDIA | Triton Inference Server | 12 GB | serve | — |
| NVIDIA | NeMo Training | 24 GB | train | — |
| AMD | Llama Strix (gfx1151) | 8 GB | serve | — |
| AMD | Ollama (ROCm) | 4 GB | serve | — |
| AMD | Lemonade | 4 GB | serve | — |
| AMD | Llama Vulkan (RDNA2+) | 4 GB | serve | — |
| AMD | vLLM (ROCm) | 16 GB | serve | HF token |
| AMD | PyTorch Lab (ROCm) | 8 GB | dev | — |

Stack discovery priority:
1. System: `/usr/share/ublue-os/{nvidia,amd}-stacks/`
2. Bundled: `src/bluefinctl/stacks/{nvidia,amd}/`

## Variable substitution

Container files use `${NGC_MONTH}` (NVIDIA) or `${ROCM_VERSION}` (AMD).
Values are read from system files first, then bundled defaults:

```python
_get_ngc_month()   # → "25.06" (reads /usr/share/ublue-os/nvidia-stacks/ngc-month)
_get_rocm_version() # → "7.2.4" (reads /usr/share/ublue-os/amd-stacks/rocm-version)
```

`_copy_quadlets(stack)` substitutes these when writing to `~/.config/containers/systemd/`.

## Auth

**NGC (NVIDIA NIM stacks):**
```python
check_ngc_secret()  # → True if podman secret "ngc-api-key" exists
# Create: podman secret create ngc-api-key -  <<< "your-key"
# CLI:    bluefinctl ai ngc-auth <key>  (NOT YET IMPLEMENTED — see gap-tracker)
```

**HuggingFace (vLLM, some llama stacks):**
```python
check_hf_token()  # → True if HF_TOKEN env var or ~/.cache/huggingface/token exists
```

## Deploy flow

```
_copy_quadlets(stack)            # substitute vars, write .container + .network to ~/.config/containers/systemd/
systemctl --user daemon-reload   # let systemd pick up new quadlet files
systemctl --user start <slug>    # start the container service
```

`deploy_stack_steps()` returns an async generator of `ProgressUpdate` for `OperationModal`.

## Status detection

```python
_get_deployed_slugs()         # quadlet .container files present in ~/.config/containers/systemd/
_get_running_user_services()  # active services from systemctl --user list-units
```

`StackStatus.STOPPED` = deployed but not running. `StackStatus.RUNNING` = service active.

## Image tag format (rollback calendar)

Date-tagged builds use `<base>:<tag_prefix>-<YYYYMMDD>`:
- NVIDIA: `ghcr.io/projectbluefin/bluefin:43-20260610`
- AMD (if applicable): same format

Verification via `skopeo inspect --raw docker://<ref>` (falls back to `podman manifest inspect`).

**⚠ Unverified on real hardware** — the exact tag format may differ between variants (bluefin vs dakota vs bluefin-lts). Test on real Bluefin hardware before declaring this working.

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

- **Don't call `systemctl start` without `daemon-reload` first** — new quadlet files are invisible until reload.
- **Don't use `podman pod ls` for status** — stacks use systemd services, not pods. Use `systemctl --user list-units`.
- **NIM stacks need `TimeoutStartSec=600`** — first pull is 8-16 GB; default timeout kills it.
- **AMD `/dev/kfd` check** — `kfd_ok` in `GpuDetection` requires `/dev/kfd` AND `/sys/class/kfd/kfd`. Absence means ROCm can't see the GPU but Vulkan may still work (llama-vulkan doesn't need kfd).
