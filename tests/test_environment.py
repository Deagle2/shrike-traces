"""Portability checks for native Windows and direct Linux command routing."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import trace_environment as environment


class EnvironmentTests(unittest.TestCase):
    def test_windows_build_uses_python_builder(self):
        work = Path(__file__).parent
        with patch.object(environment.os, 'name', 'nt'), \
             patch.object(environment, 'load_settings', return_value={}):
            command = environment.make_command(work, ['top', 'DUT', 'VERILATOR='])
        self.assertEqual(command[0], sys.executable)
        self.assertTrue(command[1].endswith('windows_build.py'))
        self.assertEqual(command[-2:], ['--top', 'DUT'])

    def test_windows_build_passes_custom_toolchain(self):
        work = Path(__file__).parent
        with patch.object(environment.os, 'name', 'nt'), \
             patch.object(environment, 'load_settings', return_value={'toolchain': r'C:\\Renesas'}):
            command = environment.make_command(work, ['top', 'DUT'])
        self.assertEqual(command[-2:], ['--toolchain', r'C:\\Renesas'])

    def test_linux_build_uses_make(self):
        work = Path(__file__).parent
        with patch.object(environment.os, 'name', 'posix'):
            command = environment.make_command(work, ['top', 'DUT', 'VERILATOR='])
        self.assertEqual(command, ['make', 'top', 'DUT', 'VERILATOR='])

    def test_simulation_does_not_discover_vendor_tools(self):
        work = Path(__file__).parent
        with patch.object(environment, 'discover', side_effect=AssertionError('unnecessary discovery')):
            self.assertEqual(environment.make_command(work, ['-C', 'sim', 'test'], needs_fpga=False),
                             ['make', '-C', 'sim', 'test'])


if __name__ == '__main__':
    unittest.main()
