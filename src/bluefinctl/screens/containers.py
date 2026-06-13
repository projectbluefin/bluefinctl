"""Containers screen — podman pod and container status.

Read-only in v1. Shows:
- Running pods and their containers
- Resource usage
- Basic health (up/down/restarting)
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static, Tree

from bluefinctl.screens._sidebar import Sidebar


class PodTree(Static):
    """Tree view of podman pods → containers."""

    DEFAULT_CSS = """
    PodTree { height: 1fr; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Tree("Pods & Containers", id="pod-tree")

    def on_mount(self) -> None:
        tree = self.query_one("#pod-tree", Tree)
        tree.root.expand()
        self.run_worker(self._load_pods(tree))

    async def _load_pods(self, tree: Tree) -> None:
        import asyncio
        import json

        try:
            # Get pods
            proc = await asyncio.create_subprocess_exec(
                "podman", "pod", "ls", "--format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0 and stdout:
                pods = json.loads(stdout)
                for pod in pods:
                    name = pod.get("Name", "unknown")
                    status = pod.get("Status", "unknown")
                    num_containers = pod.get("Containers", [])
                    icon = "v" if status == "Running" else ">"
                    state_icon = "+" if status == "Running" else "-"

                    pod_node = tree.root.add(
                        f"{icon} {state_icon} {name}  [{status}]  "
                        f"{len(num_containers) if isinstance(num_containers, list) else num_containers} containers"
                    )

                    # Get containers in this pod
                    cproc = await asyncio.create_subprocess_exec(
                        "podman", "ps", "--filter", f"pod={name}",
                        "--format=json",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    cstdout, _ = await cproc.communicate()
                    if cproc.returncode == 0 and cstdout:
                        containers = json.loads(cstdout)
                        for ct in containers:
                            ct_name = ct.get("Names", ["?"])[0] if isinstance(ct.get("Names"), list) else ct.get("Names", "?")
                            ct_state = ct.get("State", "unknown")
                            ct_image = ct.get("Image", "").split("/")[-1].split(":")[0]
                            ct_icon = "+" if ct_state == "running" else "-"
                            pod_node.add_leaf(f"  {ct_icon} {ct_name}  ({ct_image})  [{ct_state}]")

                    pod_node.expand()

                if not pods:
                    tree.root.add_leaf("  No pods running")
            else:
                tree.root.add_leaf("  No pods running")

        except FileNotFoundError:
            tree.root.add_leaf("  podman not found")
        except (json.JSONDecodeError, OSError) as e:
            tree.root.add_leaf(f"  Error: {e}")


class ContainersScreen(Screen):
    """Container management — podman pod status."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("l", "view_logs", "Logs"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Sidebar("containers")
            with Vertical(id="main-content"):
                yield Label(
                    "  Containers & Pods",
                    classes="card--title",
                )
                yield PodTree()
                yield Label(
                    "  [r]efresh  [l]ogs  |  Read-only view — manage pods with podman CLI",
                    id="containers-footer",
                )

    async def action_refresh(self) -> None:
        pod_tree = self.query_one(PodTree)
        tree = pod_tree.query_one("#pod-tree", Tree)
        tree.root.remove_children()
        tree.root.expand()
        pod_tree.run_worker(pod_tree._load_pods(tree), exclusive=True)
        self.notify("Refreshed", title="Containers")

    async def action_view_logs(self) -> None:
        self.notify("Select a container to view logs", title="Logs")
