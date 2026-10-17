"""Run with Python in Linux/WSL; requires iverilog and vvp on PATH."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from easy_trace import prepare

cases = [
    ('count == 17', 17),
    ('count == 17 && up_down == 1', 17),
    ('count == 17 && up_down == 0', 47),
    ('count == 17 || up_down == 1', 8),
    ('count == 200 || up_down == 0', 32),
    ('(count == 17 && up_down == 0) || (count == 12 && up_down == 1)', 12),
    ('count >= 20 && count <= 23', 20),
    ('count != 0 && up_down == 0', 32),
]

def simulate(work, name, parameters=()):
    output = work / (name + '.vvp')
    subprocess.run(['iverilog', '-g2012', '-s', name, *parameters, '-o', str(output),
                    *map(str, sorted((work / 'ffpga/src').glob('*.v'))), str(ROOT / 'tests' / (name+'.sv'))], check=True)
    subprocess.run(['vvp', str(output)], check=True)

work, _ = prepare(ROOT / 'examples/multiplier/trace.json')
simulate(work, 'tb_easy_multiplier')
for expression, step in cases:
    print('Testing:', expression, flush=True)
    work, _ = prepare(ROOT / 'examples/up_down_counter/trace.json', trigger_override=expression)
    simulate(work, 'tb_easy_counter', [f'-Ptb_easy_counter.TRIGGER_STEP={step}'])
