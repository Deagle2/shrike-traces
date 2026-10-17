#!/usr/bin/env python3
"""Set up shrike-traces, check prerequisites, or run an RTL experiment."""
import subprocess
import sys
from pathlib import Path


def main():
    if sys.version_info < (3, 10):
        print('shrike-traces requires Python 3.10 or later.', file=sys.stderr)
        return 1
    from tools.trace_environment import ROOT, environment_python
    python = environment_python()
    # Use only this checkout's environment; never another project's Python.
    if python.is_file() and Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        return subprocess.call([str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
    if len(sys.argv) > 1 and sys.argv[1] in ('setup', 'doctor'):
        from tools.trace_environment import main as environment_main
        return environment_main(sys.argv[1:])
    if len(sys.argv) > 1 and sys.argv[1] == 'add-project':
        if len(sys.argv) != 3:
            print('Usage: python trace.py add-project PATH', file=sys.stderr)
            return 2
        from tools.project_trace import add_project
        try:
            add_project(Path(sys.argv[2]))
            return 0
        except (OSError, ValueError) as exc:
            print(f'error: {exc}', file=sys.stderr)
            return 1
    if len(sys.argv) > 1 and sys.argv[1] in ('build', 'capture'):
        from tools.project_trace import active_config
        try:
            config = active_config()
        except (OSError, ValueError) as exc:
            print(f'error: {exc}', file=sys.stderr)
            return 1
        command = [str(config), '--build-only' if sys.argv[1] == 'build' else '--capture-only', *sys.argv[2:]]
        from tools.easy_trace import main as capture_main
        return capture_main(command)
    if len(sys.argv) == 1 or sys.argv[1] in ('-h', '--help'):
        print('Setup:       python trace.py setup\nCheck:       python trace.py doctor\nAdd project: python trace.py add-project PATH\nBuild:       python trace.py build\nCapture:     python trace.py capture\n')
    from tools.easy_trace import main as capture_main
    return capture_main()

if __name__ == "__main__":
    raise SystemExit(main())
