#!/usr/bin/env python3
"""Capture a shrike-traces trace over the board's MicroPython USB connection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from profile_support import (
    assertion_failures,
    decode_word,
    load_profile,
    vcd_signals,
)


SENTINEL = "SHRIKE_TRACES_DATA:"


def default_mpremote_python() -> Path:
    return Path(sys.executable)


def acquire(port: str, python: Path) -> tuple[int, int, int, int, list[int]]:
    device_code = (
        "import shrike_traces;"
        "s=shrike_traces.ShrikeTraces();"
        "s.reset();"
        "d,v=s.identify();"
        "s.clear();"
        "s.arm();"
        "st=s.wait_done();"
        "t=s.read_trace();"
        "p=s.trigger_pointer();"
        "print('SHRIKE_TRACES_DATA:'+','.join([('%02x'%x) for x in ([d,v,st['raw'],p]+t)]))"
    )
    command = [
        str(python),
        "-m",
        "mpremote",
        "connect",
        port,
        "exec",
        device_code,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())

    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith(SENTINEL):
            payload = line[len(SENTINEL) :]
            break
    if payload is None:
        raise RuntimeError("capture payload not found in mpremote output")

    values = [int(field, 16) for field in payload.split(",")]
    if len(values) != 20:
        raise RuntimeError(f"expected 20 capture fields, received {len(values)}")
    device_id, version, status, trigger_ptr, *trace = values
    if device_id != 0x53 or version != 0x02:
        raise RuntimeError(f"unexpected FPGA identity {device_id:02x}/{version:02x}")
    if (status & 0x07) != 0x07:
        raise RuntimeError(f"capture did not finish cleanly; status=0x{status:02x}")
    return device_id, version, status, trigger_ptr, trace


def write_csv(path: Path, rows: list[dict[str, int]]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["word"] = f"0x{row['word']:04x}"
            writer.writerow(rendered)


def write_vcd(
    path: Path,
    rows: list[dict[str, int]],
    sample_period_ns: int,
    profile: dict,
) -> None:
    signals = [
        (chr(33 + index), name, width)
        for index, (name, width) in enumerate(vcd_signals(profile))
    ]
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"$date {datetime.now(timezone.utc).isoformat()} $end\n")
        handle.write(
            f"$version shrike-traces {profile['id']} host/capture.py $end\n"
        )
        handle.write("$timescale 1ns $end\n$scope module shrike_traces $end\n")
        for identifier, name, width in signals:
            handle.write(f"$var wire {width} {identifier} {name} $end\n")
        handle.write("$upscope $end\n$enddefinitions $end\n")

        for row in rows:
            handle.write(f"#{row['index'] * sample_period_ns}\n")
            for identifier, name, width in signals:
                value = row[name]
                if width == 1:
                    handle.write(f"{value}{identifier}\n")
                else:
                    handle.write(f"b{value:0{width}b} {identifier}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--mpremote-python", type=Path, default=default_mpremote_python())
    parser.add_argument("--output", type=Path, default=Path(__file__).parent.parent / "captures")
    parser.add_argument("--sample-period-ns", type=int)
    parser.add_argument(
        "--profile",
        default="counter",
        help="profile id from profiles/ or path to a profile JSON file",
    )
    args = parser.parse_args()

    profile = load_profile(args.profile)
    sample_period_ns = args.sample_period_ns or profile.get("sample_period_ns", 20)

    device_id, version, status, trigger_ptr, trace = acquire(args.port, args.mpremote_python)
    expected_count = profile.get("sample_count", 16)
    if len(trace) != expected_count:
        raise RuntimeError(f"expected {expected_count} samples, received {len(trace)}")
    rows = [decode_word(profile, index, word) for index, word in enumerate(trace)]

    failures = assertion_failures(profile, rows)
    if failures:
        index, name, actual, expected = failures[0]
        raise RuntimeError(
            f"profile assertion failed at sample {index}: "
            f"{name}={actual}, expected {expected}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    csv_path = args.output / f"capture_{profile['id']}_{stamp}.csv"
    vcd_path = args.output / f"capture_{profile['id']}_{stamp}.vcd"
    write_csv(csv_path, rows)
    write_vcd(vcd_path, rows, sample_period_ns, profile)
    metadata = {
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'port': args.port, 'device_id': device_id, 'version': version,
        'status': status, 'trigger_pointer': trigger_ptr,
        'sample_period_ns': sample_period_ns,
        'profile': {key: value for key, value in profile.items() if key != '_path'},
        'csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    csv_path.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')

    trigger_index = profile.get("trigger_index", 8)
    print(
        f"profile={profile['id']} protocol={version} "
        f"status=0x{status:02x} trigger_ptr={trigger_ptr}"
    )
    print(f"trigger_sample=0x{trace[trigger_index]:04x}")
    print(csv_path.resolve())
    print(vcd_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
