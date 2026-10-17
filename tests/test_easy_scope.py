import sys
import json
import tempfile
from unittest.mock import patch
from subprocess import CompletedProcess
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from easy_trace import SetupError, check_board, compile_trigger, dut_wiring, prepare, read_ports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from profile_support import _evaluate_expression
import ast


class EasyScopeTests(unittest.TestCase):
    def setUp(self):
        self.signals = [dict(name="b", width=4, lsb=0), dict(name="a", width=4, lsb=4),
                        dict(name="product", width=8, lsb=8)]

    def test_exact_input_trigger_for_all_input_pairs(self):
        rtl, condition = compile_trigger("a == 6 and b == 7", self.signals)
        self.assertIn("&&", rtl)
        for a in range(16):
            for b in range(16):
                # Deliberately wrong product must not suppress an input trigger.
                actual = _evaluate_expression(ast.parse(condition, mode='eval'), dict(a=a,b=b,product=255))
                self.assertEqual(actual, a == 6 and b == 7)

    def test_or_and_parentheses_and_ranges(self):
        cases = [
            ('a == 6 || b == 7', lambda a,b: a == 6 or b == 7),
            ('(a == 6 || a == 9) && b == 7', lambda a,b: a in (6,9) and b == 7),
            ('a >= 6 && a <= 9 && b != 0', lambda a,b: 6 <= a <= 9 and b != 0),
            ('a < 6 || b > 7', lambda a,b: a < 6 or b > 7),
        ]
        for expression, reference in cases:
            _, condition = compile_trigger(expression, self.signals)
            for a in range(16):
                for b in range(16):
                    self.assertEqual(_evaluate_expression(ast.parse(condition, mode='eval'), dict(a=a,b=b)), reference(a,b))

    def test_rejects_invalid_or_unsupported_triggers(self):
        for expression in ("a == 16", "a == -1", "a == True", "missing == 1", "a = 6",
                           "a + 1 == 2", "0 < a < 2", "__import__('os')"):
            with self.subTest(expression=expression), self.assertRaises(SetupError):
                compile_trigger(expression, self.signals)

    def test_grouped_ports_and_comments(self):
        ports = read_ports("// comment\nmodule dut(input logic [3:0] a,b, input wire cin, output logic [7:0] p); assign p=a*b; endmodule", "dut")
        self.assertEqual([(p['name'], p['width'], p['direction']) for p in ports],
                         [('a',4,'input'),('b',4,'input'),('cin',1,'input'),('p',8,'output')])

    def test_imported_parameterized_multimodule_top(self):
        source = '''
        (* top *) module demo #(parameter DEPTH=8) (
          (* iopad_external_pin *) input clk,
          input nreset,
          output reg led_0,
          output led0_oe
        ); helper child(); endmodule
        module helper(); endmodule
        '''
        ports = read_ports(source, "demo", project_mode=True)
        self.assertEqual([(p['name'], p['direction']) for p in ports],
                         [('clk', 'input'), ('nreset', 'input'),
                          ('led_0', 'output'), ('led0_oe', 'output')])

    def test_rejects_ports_that_cannot_be_driven_safely(self):
        for header in ("input signed [3:0] a, output y", "input [W-1:0] a, output y",
                       "inout a, output y", "input [32:0] a, output y"):
            with self.subTest(header=header), self.assertRaises(SetupError):
                read_ports(f"module dut({header}); endmodule", "dut")

    def test_sequential_design_needs_clock_and_reset_mapping(self):
        source = 'module dut(input clk, reset, up, output reg [7:0] y); always @(posedge clk) if(reset) y<=0; else y<=y+up; endmodule'
        ports = read_ports(source, 'dut')
        with self.assertRaises(SetupError):
            dut_wiring({'stimulus':'counter'}, ports, source)
        for bad in ({'clock':'up'}, {'clock':'clk', 'reset':{'signal':'clk','active':1}},
                    {'clock':'clk', 'reset':{'signal':'reset','active':2}}):
            with self.subTest(bad=bad), self.assertRaises(SetupError):
                dut_wiring(bad | {'stimulus':{'up':1}}, ports, source)
        wiring, _ = dut_wiring({'clock':'clk', 'reset':{'signal':'reset','active':1}, 'stimulus':{'up':1}}, ports, source)
        self.assertIn('!rst_n || clear_pulse || !capturing', wiring)

    def test_rejects_second_clock(self):
        source = 'module dut(input clk, reset, clk2, output reg y); always @(posedge clk) y<=0; always @(posedge clk2) y<=1; endmodule'
        with self.assertRaises(SetupError):
            dut_wiring({'clock':'clk', 'reset':{'signal':'reset','active':1}, 'stimulus':{'clk2':0}}, read_ports(source,'dut'), source)

    def test_checks_board_identity_before_flashing(self):
        with patch('easy_trace.subprocess.run', return_value=CompletedProcess([], 0, 'Raspberry Pi Pico with RP2040', '')):
            with self.assertRaises(SetupError):
                check_board('COM3')
        with patch('easy_trace.subprocess.run', return_value=CompletedProcess([], 0, 'Vicharak Shrike FPGA with RP2040', '')):
            check_board('COM3')

    def test_invalid_configuration_does_not_generate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dut.v').write_text('module dut(input [7:0] a,b, output [15:0] p); assign p=a*b; endmodule')
            base = dict(design='dut.v', top='dut', probes=['p','a','b'], trigger='a == 6', stimulus='counter')
            for change in ({}, {'probes':['unknown']}, {'probes':['a','a']}, {'stimulus':'random'}):
                config = base | change
                (root / 'trace.json').write_text(json.dumps(config))
                with self.subTest(change=change), self.assertRaises(SetupError):
                    prepare(root / 'trace.json', root=root)
                self.assertFalse((root / 'generated').exists())


if __name__ == '__main__':
    unittest.main()
