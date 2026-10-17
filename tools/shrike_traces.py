#!/usr/bin/env python3
"""One command-line entry point for shrike-traces profiles and board captures."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from trace_environment import make_command


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOST_DIR = PROJECT_ROOT / "host"
sys.path.insert(0, str(HOST_DIR))

from profile_support import ProfileError, list_profiles, load_profile  # noqa: E402


def _run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print("+ " + " ".join(shlex.quote(part) for part in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _make(arguments: list[str]) -> None:
    _run(make_command(PROJECT_ROOT, arguments, needs_fpga=arguments[0] != '-C'))


def _mpremote_python(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path(sys.executable)


def _profile(value: str) -> dict:
    return load_profile(value)


def command_list(_: argparse.Namespace) -> None:
    print("profile   top module             description")
    for profile in list_profiles():
        print(
            f"{profile['id']:<9} "
            f"{profile['top_module']:<22} "
            f"{profile['description']}"
        )


def command_check(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    bitstream = (PROJECT_ROOT / profile["bitstream"]).resolve()
    print(f"profile:       {profile['id']}")
    print(f"top module:    {profile['top_module']}")
    print(f"test target:   {profile.get('test_target', 'not defined')}")
    print(f"bitstream:     {bitstream}")
    print(f"present:       {bitstream.is_file()}")
    print(f"trigger index: {profile.get('trigger_index', 8)}")
    print("signals:")
    for signal in profile["signals"]:
        msb = signal["lsb"] + signal["width"] - 1
        location = str(signal["lsb"]) if msb == signal["lsb"] else f"{msb}:{signal['lsb']}"
        print(f"  probe[{location:<5}] {signal['name']}")
    for assertion in profile.get("assertions", []):
        print(f"assertion:     {assertion['name']} = {assertion['expression']}")


def command_simulate(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    target = profile.get("test_target")
    if not target:
        raise ProfileError(f"profile {profile['id']} has no test_target")
    _make(["-C", "sim", target])


def command_build(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    _make(["top", profile["top_module"], "VERILATOR="])
    generated = PROJECT_ROOT / "ffpga" / "build" / "bitstream" / "FPGA_bitstream_MCU.bin"
    if not generated.is_file():
        raise RuntimeError(f"build completed without expected bitstream: {generated}")
    print(f"built: {generated}")


def command_flash(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    if args.built:
        bitstream = PROJECT_ROOT / "ffpga" / "build" / "bitstream" / "FPGA_bitstream_MCU.bin"
    else:
        bitstream = (PROJECT_ROOT / profile["bitstream"]).resolve()
    if not bitstream.is_file():
        raise FileNotFoundError(f"bitstream not found: {bitstream}")

    python = _mpremote_python(args.mpremote_python)
    base = [str(python), "-m", "mpremote", "connect", args.port]
    _run([*base, "cp", str(bitstream), ":"])
    if not args.skip_driver:
        _run(
            [
                *base,
                "cp",
                str(PROJECT_ROOT / "firmware" / "micropython" / "shrike_traces.py"),
                ":",
            ]
        )
    _run([*base, "exec", f"import shrike; shrike.flash('{bitstream.name}')"])
    print(f"active image: {profile['id']} ({bitstream.name})")


def command_capture(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    command = [
        sys.executable,
        str(HOST_DIR / "capture.py"),
        "--profile",
        profile["id"],
        "--port",
        args.port,
    ]
    if args.mpremote_python:
        command.extend(["--mpremote-python", args.mpremote_python])
    _run(command)


def _find_gtkwave() -> str:
    found = shutil.which("gtkwave") or shutil.which("gtkwave.exe")
    if found:
        return found
    raise FileNotFoundError("GTKWave was not found on PATH")


def _latest_vcd(profile_id: str) -> Path:
    captures = PROJECT_ROOT / "captures"
    generated = sorted(captures.glob(f"capture_{profile_id}_*.vcd"), key=lambda p: p.stat().st_mtime)
    if generated:
        return generated[-1]
    curated = captures / f"{profile_id}_example.vcd"
    if curated.is_file():
        return curated
    if profile_id == "counter" and (captures / "counter_example.vcd").is_file():
        return captures / "counter_example.vcd"
    raise FileNotFoundError(f"no VCD capture found for profile {profile_id}")


def command_view(args: argparse.Namespace) -> None:
    profile = _profile(args.profile)
    vcd = Path(args.file).resolve() if args.file else _latest_vcd(profile["id"])
    if not vcd.is_file():
        raise FileNotFoundError(vcd)
    executable = _find_gtkwave()
    print(f"opening: {vcd}")
    subprocess.Popen([executable, str(vcd)], cwd=PROJECT_ROOT)


def command_run(args: argparse.Namespace) -> None:
    command_flash(args)
    command_capture(args)
    if not args.no_view:
        command_view(args)


def add_board_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("profile")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--mpremote-python")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate, build, flash, capture, and view shrike-traces DUT profiles."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_command = commands.add_parser("list", help="list available DUT profiles")
    list_command.set_defaults(function=command_list)

    for name, function, help_text in (
        ("check", command_check, "validate and explain a profile"),
        ("simulate", command_simulate, "run the profile's RTL testbench"),
        ("build", command_build, "build the profile's FPGA image"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("profile")
        command.set_defaults(function=function)

    flash = commands.add_parser("flash", help="load a profile bitstream onto Shrike Lite")
    add_board_options(flash)
    flash.add_argument("--built", action="store_true", help="flash the latest local build")
    flash.add_argument("--skip-driver", action="store_true")
    flash.set_defaults(function=command_flash)

    capture = commands.add_parser("capture", help="capture CSV and VCD from the board")
    add_board_options(capture)
    capture.set_defaults(function=command_capture)

    view = commands.add_parser("view", help="open the latest profile VCD in GTKWave")
    view.add_argument("profile")
    view.add_argument("--file")
    view.set_defaults(function=command_view)

    run = commands.add_parser("run", help="flash, capture, and open GTKWave")
    add_board_options(run)
    run.add_argument("--built", action="store_true", help="flash the latest local build")
    run.add_argument("--skip-driver", action="store_true")
    run.add_argument("--no-view", action="store_true")
    run.add_argument("--file")
    run.set_defaults(function=command_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.function(args)
    except (ProfileError, FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
