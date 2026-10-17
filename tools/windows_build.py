#!/usr/bin/env python3
"""Build one Shrike Lite Verilog project with native Windows Renesas tools."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


DEFAULT_TOOLCHAIN = Path(r"C:\Program Files\Renesas Electronics\Go Configure Software Hub")


def external_dir(value: str | None = None) -> Path:
    roots = []
    if value:
        roots.append(Path(value).expanduser())
    if os.environ.get("SHRIKE_TOOLCHAIN"):
        roots.append(Path(os.environ["SHRIKE_TOOLCHAIN"]).expanduser())
    roots.append(DEFAULT_TOOLCHAIN)
    checked = []
    for root in roots:
        for candidate in (root, root / "external", root / "bin" / "external"):
            checked.append(str(candidate))
            if ((candidate / "yosys" / "yosys.exe").is_file()
                    and (candidate / "eda-placer" / "v23" / "eda-placer.exe").is_file()):
                return candidate.resolve()
    raise RuntimeError("Windows Go Configure tools were not found. Checked: " + ", ".join(checked))


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+ " + subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command[0]}")


def project_value(path: Path, name: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":=" in line:
            key, value = line.split(":=", 1)
            if key.strip() == name:
                return value.strip()
    raise RuntimeError(f"{path.name} does not define {name}.")


def write_synthesis_script(path: Path, sources: list[Path], top: str) -> None:
    quoted = " ".join(f'"../src/{source.name}"' for source in sources)
    path.write_text(
        f"read_verilog -sv {quoted}\n"
        "hierarchy -check\n"
        "flatten\n"
        f"synth_xilinx -nobram -noiopad -nodsp -abc9 -top {top}\n"
        "clean\n"
        "autoname\n"
        'write_verilog "post_synth_results.v"\n'
        'write_edif "netlist.edif"\n'
        'tee -q -o post_synth_report.txt stat\n',
        encoding="utf-8",
    )


def wait_for_place_and_route(output: Path, timeout: int = 900) -> Path:
    expected = output / "EFLX_bitstream_AXI.log"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if expected.is_file() and expected.stat().st_size:
            previous = expected.stat().st_size
            time.sleep(2)
            if expected.is_file() and expected.stat().st_size == previous:
                return expected
        time.sleep(2)
    raise RuntimeError(f"Windows place-and-route did not finish within {timeout} seconds. See {output}.")


def collect_outputs(output: Path, build: Path, tools: Path, project: str) -> None:
    for source in output.glob("EFLX_*"):
        if source.is_file():
            shutil.copy2(source, build / source.name.replace("EFLX_", "FPGA_", 1))
    names = (
        "FPGA_bitstream.bin", "FPGA_bitstream.log", "FPGA_bitstream_AXI.log",
        "FPGA_case_analysis_RBB.sdc", "FPGA_case_analysis_top1per.sdc",
        "PNR_PACK_PLACE.log", "PNR_TIMING.log", "PNR_ROUTE.log", "PNR_IO.log",
        "PNR_PLACER_REGION.log", "PNR_PLACER_RESOURCE.log", "PNR_PLACER_TIMING.log",
        "clock_tree.txt", "resource-utilization-report.log", "PNR_RESOURCE.log",
        "PNR_IO.v", "PNR_STDOUT.log", "PNR_OUTPUT.log", "PNR_TRIAL_ROUTE_TIMING.log",
        "PNR_PLACE.log", "RouterInfo.txt", "EFLX_COMPILER_last_saved.prj",
    )
    for name in names:
        source = output / name
        if source.is_file():
            shutil.copy2(source, build / name)
    for directory in ("ta_message",):
        source = output / directory
        if source.is_dir():
            shutil.copytree(source, build / directory, dirs_exist_ok=True)
    axi = build / "FPGA_bitstream_AXI.log"
    if not axi.is_file():
        raise RuntimeError(f"Place-and-route finished without {axi.name}.")
    run(
        [sys.executable, str(tools / "gen_bitstreams.py"), "--axi", str(axi),
         "--outdir", str(build / "bitstream"), "--project", project,
         "--netlist", "netlist.edif"],
        cwd=build,
    )


def build(project_dir: Path, top: str, toolchain: str | None = None) -> Path:
    project_dir = project_dir.resolve()
    source_dir = project_dir / "ffpga" / "src"
    build_dir = project_dir / "ffpga" / "build"
    tools_dir = project_dir / "shrike_gen"
    sources = sorted(source_dir.glob("*.v"))
    if not sources:
        raise RuntimeError(f"No Verilog sources found in {source_dir}.")
    project = project_value(project_dir / "shrike.mk", "PROJECT")
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "bitstream").mkdir(exist_ok=True)
    shutil.copy2(project_dir / "ffpga" / "floorplanspec.fp", build_dir / "floorplanspec.fp")

    print("Generating project files...", flush=True)
    run([sys.executable, str(tools_dir / "gen_io_spec.py"), "--pcf",
         str(project_dir / "io_map.pcf"), "--out-iospec", str(build_dir / "io_spec_in.txt")],
        cwd=project_dir)
    run([sys.executable, str(tools_dir / "gen_ffpga.py"), "--project", project,
         "--sources", *[source.name for source in sources], "--pcf",
         str(project_dir / "io_map.pcf"), "--max-cpu",
         os.environ.get("SHRIKE_PNR_JOBS", "2"),
         "--out", str(project_dir / f"{project}.ffpga")], cwd=project_dir)

    external = external_dir(toolchain)
    yosys = external / "yosys" / "yosys.exe"
    placer_dir = external / "eda-placer" / "v23"
    placer = placer_dir / "eda-placer.exe"
    script = build_dir / "synth_windows.ys"
    write_synthesis_script(script, sources, top)
    print("Synthesizing with Windows Yosys...", flush=True)
    run([str(yosys), "-Q", "-s", str(script)], cwd=build_dir)
    netlist = build_dir / "netlist.edif"
    if not netlist.is_file():
        raise RuntimeError("Yosys completed without creating netlist.edif.")

    run_dir = Path(tempfile.mkdtemp(prefix="native_pnr_", dir=build_dir))
    try:
        config = run_dir / "config"
        output = run_dir / "out"
        config.mkdir()
        output.mkdir()
        shutil.copy2(build_dir / "io_spec_in.txt", config / "io_spec_in.txt")
        shutil.copy2(build_dir / "floorplanspec.fp", config / "floorplanspec.fp")
        blob_result = subprocess.run(
            [sys.executable, str(tools_dir / "gen_fpga_data.py"), "--netlist", str(netlist),
             "--fp", str(config / "floorplanspec.fp"), "--io", str(config / "io_spec_in.txt"),
             "--max-cpu", os.environ.get("SHRIKE_PNR_JOBS", "2")],
            cwd=project_dir, text=True, capture_output=True, check=True,
        )
        environment = os.environ.copy()
        environment["EFLX_COMPILER_INSTALL"] = str(placer_dir)
        print("Running Windows place-and-route...", flush=True)
        run([str(placer), "FPGA_DATA", blob_result.stdout, "0"], cwd=output, env=environment)
        wait_for_place_and_route(output)
        collect_outputs(output, build_dir, tools_dir, project)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
    bitstream = build_dir / "bitstream" / "FPGA_bitstream_MCU.bin"
    if not bitstream.is_file():
        raise RuntimeError("Build completed without the MCU bitstream.")
    print(f"Windows build complete: {bitstream}", flush=True)
    return bitstream


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Windows Shrike Lite FPGA build")
    parser.add_argument("project", type=Path)
    parser.add_argument("--top", required=True)
    parser.add_argument("--toolchain")
    args = parser.parse_args()
    try:
        build(args.project, args.top, args.toolchain)
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
