"""Import an unchanged Verilog project into the shrike-traces easy flow."""
from __future__ import annotations

import json
from pathlib import Path
import re

from .easy_trace import ROOT, SetupError, read_ports

STATE_DIR = ROOT / ".shrike-traces"
ACTIVE = STATE_DIR / "active_project.json"


def _sources(project: Path) -> list[Path]:
    source_dir = project / "ffpga" / "src"
    found = sorted(source_dir.glob("*.v")) if source_dir.is_dir() else sorted(project.glob("*.v"))
    if not found:
        raise SetupError(f"No Verilog files found in {source_dir if source_dir.is_dir() else project}.")
    return found


def _top(source: str) -> str:
    match = re.search(r"\(\*\s*top\s*\*\)\s*module\s+([A-Za-z_][A-Za-z0-9_]*)", source)
    if not match:
        raise SetupError("Could not identify the top module. Mark it with (* top *).")
    return match.group(1)


def add_project(project: Path) -> Path:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise SetupError(f"Project folder does not exist: {project}")
    sources = _sources(project)
    source = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    top = _top(source)
    ports = read_ports(source, top, project_mode=True)
    inputs = {port["name"]: port for port in ports if port["direction"] == "input"}
    clock = next((name for name in ("clk", "clock", "i_osc") if name in inputs), None)
    if clock is None:
        raise SetupError("Could not identify a clock input named clk, clock, or i_osc.")
    reset_name = next((name for name in ("nreset", "rst_n", "reset_n", "reset", "rst") if name in inputs), None)
    if reset_name is None:
        raise SetupError("Could not identify a reset input.")
    ignored = {"clk_en", "osc_en", "o_osc_en"}
    candidates = [port for port in ports if port["direction"] == "output"
                  and port["name"] not in ignored and not port["name"].endswith(("_oe", "_en"))]
    probes, width = [], 0
    for port in candidates:
        if width + port["width"] <= 16:
            probes.append(port["name"])
            width += port["width"]
    if not probes:
        raise SetupError("No top-level output signals fit the 16-bit probe bus.")
    other_inputs = [port for port in ports if port["direction"] == "input"
                    and port["name"] not in {clock, reset_name}]
    stimulus = {port["name"]: 0 for port in other_inputs}
    config = {
        "design": [str(path) for path in sources],
        "top": top,
        "clock": clock,
        "reset": {"signal": reset_name, "active": 0 if reset_name in {"nreset", "rst_n", "reset_n"} else 1},
        "probes": probes,
        "trigger": f"{probes[0]} == 1",
        "stimulus": stimulus,
        "project_mode": True,
        "imported_project": str(project),
    }
    STATE_DIR.mkdir(exist_ok=True)
    ACTIVE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Added {project.name}: top={top}, probes={', '.join(probes)}")
    print(f"Active project: {ACTIVE}")
    return ACTIVE


def active_config() -> Path:
    if not ACTIVE.is_file():
        raise SetupError("No project is active. Run 'python trace.py add-project PATH' first.")
    return ACTIVE
