"""Utilities to generate HTML from events."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import ujson
from typing_extensions import Annotated as An
from typing_extensions import Doc


@dataclass
class _Cluster:
    id: str
    name: str
    nodes: set[str] = field(default_factory=set)
    clusters: set[_Cluster] = field(default_factory=set)

    def __hash__(self):
        return id(self)

    def __iter__(self):
        yield from self.nodes
        yield from self.clusters

    def _to_dot(self, indent: str = "") -> Iterator[str]:
        yield "\n"
        yield f'{indent}subgraph "cluster_{self.id}" {{\n'
        if self.nodes:
            yield f"{indent} "
            for node in self.nodes:
                yield f' "{node}"'
            yield ";\n"
        yield f'{indent}  label = "{self.name}";\n'
        yield f'{indent}  name = "{self.name}";\n'
        yield f'{indent}  style = "filled";\n'
        yield f"{indent}  graph[style=dotted];\n"

        if self.clusters:
            for cluster in sorted(self.clusters, key=lambda c: c.id):
                yield from cluster._to_dot(indent=indent + "  ")
        yield f"{indent}}};\n"


def _dot(events_file: str = "events.jsonl") -> Iterator[str]:
    nodes = set()
    edges = set()

    with open(events_file) as file:
        for line in file:
            data = ujson.loads(line)
            caller = data["caller"]["name"]
            callee = data["callee"]["name"]
            nodes.add(caller)
            nodes.add(callee)
            if data["event"] == "call":
                edges.add((caller, callee))

    clusters = {}
    top_level_clusters = set()
    for node in nodes:
        parts = node.split(".")
        parent_cluster = None
        for i in range(1, len(parts)):
            cluster_id = ".".join(parts[:i])
            if cluster_id not in clusters:
                cluster = _Cluster(cluster_id, parts[i - 1])
                clusters[cluster_id] = cluster
            else:
                cluster = clusters[cluster_id]
            if parent_cluster:
                parent_cluster.clusters.add(cluster)
            else:
                top_level_clusters.add(cluster)
            parent_cluster = cluster
        cluster.nodes.add(node)

    yield "digraph G {\n"
    yield "  concentrate = false;\n"
    yield '  splines = "ortho";\n'
    yield '  rankdir = "LR";\n'
    yield "\n"

    color = "#708FCC"
    for node in sorted(nodes):
        node_id = node  # .replace("<", "|").replace(">", "|")
        label = f"{node.rsplit('.', 1)[-1]}()"
        name = node.replace(".", "::")
        yield f'  "{node}" [id="{node_id}" label="{label}" name="{name}" shape="rect" style="filled" fillcolor="{color}"];\n'

    yield "\n"

    color = "#000000"
    for edge in edges:
        edge_id = f"{edge[0]}--{edge[1]}"  # .replace("<", "|").replace(">", "|")
        yield f'  "{edge[0]}" -> "{edge[1]}" [id="{edge_id}" color="{color}" penwidth="2"];\n'

    for cluster in top_level_clusters:
        yield from cluster._to_dot(indent="  ")

    yield "}\n"


def _dot_to_svg(events_file: str = "events.jsonl") -> str:
    process = subprocess.Popen(
        ["dot", "-Tsvg"],  # noqa: S603, S607
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    for line in _dot(events_file):
        process.stdin.write(line)  # type: ignore[union-attr]
    return process.communicate()[0]


_HTML = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>happy-path for Griffe</title>
        <style>
            {css}
        </style>
    </head>
    <body>
        <div class="sidenav">
            <button id="pressPlay" type="button">⧐ Play</button>
            <button id="pressPause" type="button">⏸ Pause</button>
            <button id="pressStepForward" type="button">▶ Step forward</button>
            <button id="pressStepBackward" type="button">◀ Step backward</button>
            <button id="pressStepOut" type="button">⏏ Step out</button>
        </div>
        <div class="main">
            {svg}
            <script>
            document.addEventListener("DOMContentLoaded", function() {{
                {js}
                happyPath();
            }});
            </script>
        </div>
    </body>
</html>
"""


def render(
    events_file: An[str, Doc("Path to an events file.")] = "events.jsonl",
) -> An[str, Doc("HTML content.")]:
    """Generate an HTML file from a JSONL file containing events."""
    parent = Path(__file__).parent
    return _HTML.format(
        css=parent.joinpath("happy_path.css").read_text(),
        svg=_dot_to_svg(events_file),
        js=parent.joinpath("happy_path.js").read_text(),
    )
