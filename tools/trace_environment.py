"""Repository-local Python setup and native tool discovery."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / '.shrike-traces.json'


def environment_python(root: Path = ROOT) -> Path:
    return root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def load_settings() -> dict:
    data = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
    if not isinstance(data, dict) or any(key != 'toolchain' or not isinstance(value, str)
                                         or not value.strip() for key, value in data.items()):
        raise RuntimeError('Invalid .shrike-traces.json; expected an optional toolchain string.')
    return data


LINUX_DISCOVERY = r'''
import json, os, shutil, sys
from pathlib import Path
requested = sys.argv[1]
candidates = [Path(requested).expanduser()] if requested else [
    Path('/opt/go-configure-sw-hub'),
    Path('/usr/local/go-configure-sw-hub'),
    Path.home() / 'go-configure-sw-hub',
    Path.home() / '.local/opt/go-configure-sw-hub',
]
found = None
for root in candidates:
    external = root / 'bin/external'
    if all(os.access(external / name, os.X_OK) for name in
           ('yosys/v59/yosys', 'eda-placer/v23/eda-placer')):
        found = str(external.resolve())
        break
print(json.dumps(dict(external=found, make=shutil.which('make'),
                      iverilog=shutil.which('iverilog'), checked=list(map(str,candidates)))))
'''


def windows_external(requested: str = '') -> Path | None:
    try:
        from .windows_build import external_dir
    except ImportError:
        from windows_build import external_dir
    try:
        return external_dir(requested or None)
    except RuntimeError:
        return None


def discover(settings: dict) -> dict:
    requested = os.environ.get('SHRIKE_TOOLCHAIN') or settings.get('toolchain', '')
    if os.name == 'nt':
        external = windows_external(requested)
        if external is None:
            raise RuntimeError('Windows Go Configure tools were not found. Install Go Configure Software Hub, then rerun setup.')
        return {'external': str(external), 'make': None, 'iverilog': shutil.which('iverilog'), 'mode': 'Windows'}
    result = subprocess.run([sys.executable, '-c', LINUX_DISCOVERY, requested],
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    if not data['make']:
        raise RuntimeError('GNU Make is missing. Install it with: sudo apt install make')
    if not data['external']:
        raise RuntimeError('Renesas tools not found in: ' + ', '.join(data['checked']) +
                           '. Run setup --toolchain /path/to/go-configure-sw-hub')
    data['mode'] = 'Linux'
    return data


def make_command(work: Path, arguments: list[str], *, needs_fpga: bool = True) -> list[str]:
    if os.name == 'nt' and needs_fpga:
        if not arguments or arguments[0] != 'top':
            raise RuntimeError('The native Windows builder currently supports the top build command.')
        top = next((item for item in arguments[1:] if '=' not in item), None)
        if not top:
            raise RuntimeError('A top module is required for the Windows build.')
        command = [sys.executable, str(ROOT / 'tools' / 'windows_build.py'), str(work), '--top', top]
        toolchain = load_settings().get('toolchain')
        if toolchain:
            command += ['--toolchain', toolchain]
        return command
    return ['make', *arguments]


def ensure_shrike_gen() -> None:
    script = ROOT / 'third_party' / 'shrike-gen' / 'shrike_gen' / 'shrike-gen.py'
    if script.is_file():
        return
    if not (ROOT / '.git').exists():
        raise RuntimeError('shrike-gen is missing. Clone this repository with Git, then run setup again.')
    print('Fetching the pinned shrike-gen dependency...', flush=True)
    subprocess.run(['git', 'submodule', 'update', '--init', '--depth', '1',
                    '--', 'third_party/shrike-gen'], cwd=ROOT, check=True)
    if not script.is_file():
        raise RuntimeError('The shrike-gen dependency could not be initialized.')


def doctor() -> int:
    failures = 0
    print(f'Python: {sys.version.split()[0]} ({sys.executable})')
    for module in ('mpremote', 'serial'):
        present = importlib.util.find_spec(module) is not None
        print(f'{"OK" if present else "MISSING"}: {module}' + ('' if present else ' — run python trace.py setup'))
        failures += not present
    try:
        data = discover(load_settings())
        print(f"OK: {data['mode']} FPGA tools — {data['external']}")
        print('Optional simulation: ' + (data['iverilog'] or 'Icarus Verilog not found'))
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print('MISSING: ' + str(exc))
        failures += 1
    if importlib.util.find_spec('serial'):
        from serial.tools.list_ports import comports
        ports = [port.device for port in comports()]
        print('Serial ports: ' + (', '.join(ports) or 'none — connect the board before capturing'))
    print('Optional waveform viewer: ' + (shutil.which('gtkwave') or shutil.which('gtkwave.exe') or 'not on PATH'))
    print('Setup ready for builds.' if not failures else 'Resolve the missing requirements above, then rerun python trace.py doctor.')
    print('Board firmware is checked when you run a capture; doctor does not program the board.')
    return int(bool(failures))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Set up or check this shrike-traces checkout.')
    parser.add_argument('command', choices=['setup', 'doctor'])
    parser.add_argument('--toolchain', help='Go Configure Software Hub installation directory')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            if args.toolchain:
                parser.error('Save the override with setup, then run doctor.')
            return doctor()
        settings = load_settings()
        ensure_shrike_gen()
        if args.toolchain:
            settings['toolchain'] = args.toolchain
            SETTINGS.write_text(json.dumps(settings, indent=2) + '\n')
        target = ROOT / '.venv'
        if target.exists() and not (target / 'pyvenv.cfg').is_file():
            raise RuntimeError('.venv exists but is not a Python environment.')
        if not environment_python().is_file():
            print('Creating the repository Python environment...', flush=True)
            venv.EnvBuilder(with_pip=True).create(target)
        print('Installing host dependencies into .venv...', flush=True)
        subprocess.run([str(environment_python()), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
        return subprocess.call([str(environment_python()), str(ROOT / 'trace.py'), 'doctor'])
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'error: {exc}\n')
