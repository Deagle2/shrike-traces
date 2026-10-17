"""Configuration frontend for combinational and single-clock DUTs."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

try:
    from .trace_environment import make_command
except ImportError:
    from trace_environment import make_command

ROOT = Path(__file__).resolve().parent.parent
IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
CORE_FILES = ("trigger_unit.v", "trace_mem_regs.v", "scope_controller.v",
              "shrike_traces_core.v", "spi_target.v", "scope_spi_regs.v",
              "shrike_traces_shell.v")


class SetupError(ValueError):
    pass


def read_ports(source: str, top: str, project_mode: bool = False) -> list[dict]:
    """Read literal-width ANSI ports from a small DUT or imported project top."""
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    clean = re.sub(r"\(\*.*?\*\)", "", clean, flags=re.S)
    if not project_mode and len(re.findall(r"\bmodule\b", clean)) != 1:
        raise SetupError("Use one self-contained module per design file.")
    if not project_mode and re.search(r"\b(always_latch|initial|parameter|localparam)\b", clean):
        raise SetupError("Initial blocks, explicit latches, and parameters need the advanced workflow.")
    if re.search(r"`(?!timescale\b)", clean):
        raise SetupError("Preprocessor directives other than `timescale are not supported.")
    parameter_block = r"(?:#\s*\(.*?\)\s*)?" if project_mode else ""
    header = re.search(r"\bmodule\s+" + re.escape(top) + r"\s*" + parameter_block + r"\((.*?)\)\s*;", clean, re.S)
    if not header:
        raise SetupError("Cannot read top module: use ANSI input/output declarations and literal widths.")
    ports = []
    direction, width = None, 1
    for part in header.group(1).split(","):
        part = part.strip()
        declaration = re.fullmatch(r"(input|output)\s+(?:(?:wire|logic|reg)\s+)?(?:\[\s*(\d+)\s*:\s*0\s*\]\s*)?(" + IDENT + r")", part)
        if declaration:
            direction, msb, name = declaration.groups()
            width = int(msb) + 1 if msb is not None else 1
        elif direction and re.fullmatch(IDENT, part):
            name = part
        else:
            raise SetupError(f"Unsupported port declaration: {part!r}. Use unsigned input/output [N:0] ports.")
        if width > 16 or name in {p["name"] for p in ports}:
            raise SetupError(f"Invalid or duplicate port: {name}")
        if name in {"index", "word", "trigger", "expected_word_ok", "trigger_inputs_ok"}:
            raise SetupError(f"Port name {name!r} is reserved by the capture decoder.")
        ports.append({"name": name, "width": width, "direction": direction})
    if not any(p["direction"] == "input" for p in ports) or not any(p["direction"] == "output" for p in ports):
        raise SetupError("The design must have at least one input and one output.")
    return ports


def compile_trigger(expression: str, signals: list[dict]) -> tuple[str, str]:
    """Compile a bounded expression AST independently to Verilog and host syntax."""
    expression = expression.replace("&&", " and ").replace("||", " or ")
    try:
        tree = ast.parse(expression.strip(), mode="eval").body
    except SyntaxError as exc:
        raise SetupError("Use == for comparisons, e.g. count == 17 && up_down == 1.") from exc
    if len(list(ast.walk(tree))) > 200:
        raise SetupError("Trigger expression is too large; use at most a few dozen comparisons.")
    mapping = {s["name"]: s for s in signals}
    operators = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}

    def visit(term):
        if isinstance(term, ast.BoolOp) and isinstance(term.op, (ast.And, ast.Or)):
            pairs = [visit(value) for value in term.values]
            vjoin, pjoin = (" && ", " and ") if isinstance(term.op, ast.And) else (" || ", " or ")
            return "(" + vjoin.join(p[0] for p in pairs) + ")", "(" + pjoin.join(p[1] for p in pairs) + ")"
        if not (isinstance(term, ast.Compare) and isinstance(term.left, ast.Name)
                and len(term.ops) == 1 and type(term.ops[0]) in operators
                and isinstance(term.comparators[0], ast.Constant)
                and type(term.comparators[0].value) is int):
            raise SetupError("Use unsigned signal-to-integer comparisons joined with AND/OR; arithmetic and assignments are not supported.")
        name, number = term.left.id, term.comparators[0].value
        if name not in mapping:
            raise SetupError(f"Trigger signal {name!r} must be in probes (names are case-sensitive).")
        signal = mapping[name]
        if not 0 <= number < (1 << signal["width"]):
            raise SetupError(f"Trigger value {number} does not fit {name} ({signal['width']} bits).")
        operator = operators[type(term.ops[0])]
        return (f"(probe[{signal['lsb']} +: {signal['width']}] {operator} {signal['width']}'d{number})",
                f"({name} {operator} {number})")

    return visit(tree)


def dut_wiring(config: dict, ports: list[dict], source: str) -> tuple[str, list[str]]:
    """Drive one board clock, reset while idle, and explicit input stimuli."""
    mapping = {p['name']: p for p in ports}
    clock = config.get('clock')
    reset = config.get('reset')
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    edges = re.findall(r"\b(posedge|negedge)\s+(" + IDENT + r")", clean)
    if clock is not None:
        if not isinstance(clock, str) or clock not in mapping or mapping[clock]['direction'] != 'input' or mapping[clock]['width'] != 1:
            raise SetupError('clock must name a one-bit input port.')
        if not isinstance(reset, dict) or set(reset) != {'signal', 'active'} or type(reset['active']) is not int or reset['active'] not in (0, 1):
            raise SetupError('Sequential designs need reset: {"signal": "reset", "active": 1} (or active: 0).')
        name = reset['signal']
        if not isinstance(name, str) or name == clock or name not in mapping or mapping[name]['direction'] != 'input' or mapping[name]['width'] != 1:
            raise SetupError('reset.signal must name a distinct one-bit input port.')
        allowed = {('posedge', clock), ('posedge' if reset['active'] else 'negedge', name)}
        if ('posedge', clock) not in edges or any(edge not in allowed for edge in edges):
            raise SetupError('Only the configured positive-edge clock and optional reset edge are supported.')
    elif edges or reset is not None:
        raise SetupError('Sequential RTL requires explicit clock and reset configuration.')
    control_names = {clock, reset['signal'] if reset else None}
    inputs = [p for p in ports if p['direction'] == 'input' and p['name'] not in control_names]
    if clock is None and any(p['name'].lower() in {'clk', 'clock', 'reset', 'reset_n', 'rst', 'rst_n'} for p in inputs):
        raise SetupError('Clock/reset inputs must be configured explicitly; they are not counter stimulus bits.')
    width = sum(p['width'] for p in inputs)
    if width > 16:
        raise SetupError('Automatic input stimulus supports at most 16 data input bits.')
    stimulus = config.get('stimulus')
    if stimulus != 'counter' and (not isinstance(stimulus, dict) or set(stimulus) != {p['name'] for p in inputs}):
        raise SetupError('stimulus must be "counter" or specify every non-clock/reset input by name.')
    text, connections = [], []
    for i, p in enumerate(ports):
        p['net'] = f'dut_signal_{i}'
        text.append(f"wire [{p['width']-1}:0] {p['net']};")
        connections.append(f".{p['name']}({p['net']})")
    if clock:
        text.append(f"assign {mapping[clock]['net']} = clk;")
        expression = '(!rst_n || clear_pulse || !capturing)'
        if reset['active'] == 0:
            expression = '!' + expression
        text.append(f"assign {mapping[reset['signal']]['net']} = {expression};")
    if stimulus == 'counter' and width:
        text.extend([f'reg [{width-1}:0] stimulus;',
                     "always @(posedge clk or negedge rst_n)\n  if (!rst_n) stimulus <= 0;\n  else if (clear_pulse) stimulus <= 0;\n  else if (capturing) stimulus <= stimulus + 1'b1;"])
        offset = width
        for p in inputs:
            offset -= p['width']
            text.append(f"assign {p['net']} = stimulus[{offset} +: {p['width']}];")
    elif isinstance(stimulus, dict):
        for i, p in enumerate(inputs):
            value = stimulus[p['name']]
            if type(value) is int:
                if not 0 <= value < 1 << p['width']:
                    raise SetupError(f"Stimulus value does not fit {p['name']}.")
                text.append(f"assign {p['net']} = {p['width']}'d{value};")
                continue
            if not isinstance(value, dict) or set(value) != {'sequence', 'cycles_per_value'}:
                raise SetupError('Each stimulus is an integer or {"sequence": [1, 0], "cycles_per_value": 32}.')
            sequence, cycles = value['sequence'], value['cycles_per_value']
            if (not isinstance(sequence, list) or not sequence or len(sequence) > 256
                    or any(type(v) is not int or not 0 <= v < 1 << p['width'] for v in sequence)
                    or type(cycles) is not int or cycles < 1 or len(sequence)*cycles > 65536):
                raise SetupError('Invalid stimulus sequence; use fitting values and a period of 1..65536 cycles.')
            period = len(sequence)*cycles
            step = f'stimulus_step_{i}'
            text.append(f"reg [{max(1,(period-1).bit_length())-1}:0] {step};")
            text.append(f"always @(posedge clk or negedge rst_n)\n  if (!rst_n) {step} <= 0;\n  else if (clear_pulse) {step} <= 0;\n  else if (capturing) {step} <= ({step} == {period-1}) ? 0 : {step} + 1'b1;")
            expr = ''.join(f"({step} < {(j+1)*cycles}) ? {p['width']}'d{v} : " for j,v in enumerate(sequence[:-1]))
            text.append(f"assign {p['net']} = {expr}{p['width']}'d{sequence[-1]};")
    return '\n'.join(text), connections


def prepare(config_path: Path, root: Path = ROOT, trigger_override: str | None = None) -> tuple[Path, dict]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise SetupError("Configuration must be a JSON object.")
    if trigger_override is not None:
        config['trigger'] = trigger_override
    for key in ("top", "trigger"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise SetupError(f"Configuration needs a non-empty {key!r} string.")
    designs = config.get("design")
    if isinstance(designs, str):
        designs = [designs]
    if (not isinstance(designs, list) or not designs
            or any(not isinstance(item, str) or not item for item in designs)):
        raise SetupError("Configuration needs design as a file name or non-empty list of file names.")
    top = config["top"]
    if not re.fullmatch(IDENT, top) or top == "ShrikeTracesEasy" or top in {Path(f).stem for f in CORE_FILES}:
        raise SetupError("Choose a valid DUT module name distinct from the analyzer modules.")
    source_paths = [(config_path.parent / item).resolve() for item in designs]
    source = "\n\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    project_mode = bool(config.get("project_mode"))
    ports = read_ports(source, top, project_mode=project_mode)
    wiring, connections = dut_wiring(config, ports, source)
    names = config.get("probes")
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        raise SetupError("probes must be a non-empty list of unique port names.")
    port_map = {p["name"]: p for p in ports}
    if any(n not in port_map for n in names):
        raise SetupError("Every probe must name a DUT input or output port.")
    if config.get('clock') in names:
        raise SetupError('Do not probe the sampling clock itself; select the state and data signals.')
    width = sum(port_map[n]["width"] for n in names)
    if width > 16:
        raise SetupError(f"Selected probes need {width} bits; this analyzer supports 16.")
    signals, offset = [], 0
    for name in reversed(names):
        signals.append({"name": name, "lsb": offset, "width": port_map[name]["width"]})
        offset += port_map[name]["width"]
    trigger_rtl, condition = compile_trigger(config["trigger"], signals)
    identity = hashlib.sha256(str(config_path).encode()).hexdigest()[:8]
    profile_id = f"easy_{top}_{identity}"
    work = root / "generated" / profile_id
    # Only overwrite directories owned by this frontend.
    marker = work / ".shrike-traces-generated"
    if work.exists() and not marker.is_file():
        raise SetupError(f"Refusing to overwrite an unowned directory: {work}")
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(config_path), encoding="utf-8")
    src = work / "ffpga" / "src"
    src.mkdir(parents=True, exist_ok=True)
    for file in CORE_FILES:
        shutil.copy2(root / "ffpga" / "src" / file, src / file)
    for file in ("Makefile", "io_map.pcf"):
        shutil.copy2(root / file, work / file)
    # The vendor Makefile selects project mode only when an .ffpga exists.
    # Its update target replaces this seed with the generated source list.
    if not (work / "ShrikeTracesEasy.ffpga").exists():
        shutil.copy2(root / "ShrikeTraces.ffpga", work / "ShrikeTracesEasy.ffpga")
    shutil.copy2(root / "ffpga" / "floorplanspec.fp", work / "ffpga" / "floorplanspec.fp")
    generator = ROOT / "third_party" / "shrike-gen" / "shrike_gen"
    if not (generator / "shrike-gen.py").is_file():
        raise SetupError("shrike-gen is missing. Run 'python trace.py setup' first.")
    shutil.copytree(generator, work / "shrike_gen", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    # Upstream uses a POSIX-only strftime flag. Patch only the disposable
    # generated copy so the pinned dependency stays unmodified.
    if os.name == "nt":
        gen_ffpga = work / "shrike_gen" / "gen_ffpga.py"
        text = gen_ffpga.read_text(encoding="utf-8")
        text = text.replace("return dt.strftime('%-d %b %Y 00:00:00')",
                            "return f'{dt.day} {dt:%b %Y 00:00:00}'")
        text = text.replace("out_path.write_text(xml)",
                            "out_path.write_text(xml, encoding='utf-8')")
        gen_ffpga.write_text(text, encoding="utf-8")
        gen_io = work / "shrike_gen" / "gen_io_spec.py"
        text = gen_io.read_text(encoding="utf-8")
        text = text.replace("path.read_text()", "path.read_text(encoding='utf-8')")
        text = text.replace("args.ffpga.read_text()", "args.ffpga.read_text(encoding='utf-8')")
        text = text.replace("args.out_iospec.write_text(txt)",
                            "args.out_iospec.write_text(txt, encoding='utf-8')")
        text = text.replace("args.out_xml.write_text(xml + '\\n')",
                            "args.out_xml.write_text(xml + '\\n', encoding='utf-8')")
        text = text.replace("args.out_ffpga.write_text(patched)",
                            "args.out_ffpga.write_text(patched, encoding='utf-8')")
        gen_io.write_text(text, encoding="utf-8")
        gen_bits = work / "shrike_gen" / "gen_bitstreams.py"
        text = gen_bits.read_text(encoding="utf-8")
        text = text.replace("path.read_text()", "path.read_text(encoding='utf-8')")
        gen_bits.write_text(text, encoding="utf-8")
    (work / "shrike.mk").write_text("PROJECT := ShrikeTracesEasy\nTOP := ShrikeTracesEasy\nPROJECT_TYPE := verilog\n")
    generated_source = source
    if project_mode:
        # Imported I/O and top attributes describe the original standalone
        # project. In the instrumented build these ports are internal wires and
        # the analyzer wrapper is the physical top. Strip attributes only from
        # our generated copy; the user's project remains byte-for-byte intact.
        generated_source = re.sub(r"\(\*.*?\*\)", "", generated_source, flags=re.S)
    (src / "easy_dut.v").write_text(generated_source, encoding="utf-8")
    probe_parts = ([f"{16-width}'b0"] if width < 16 else []) + [port_map[n]["net"] for n in names]
    wrapper = f'''`timescale 1ns/1ps
// Generated wrapper. Edit the configuration, not this file.
module ShrikeTracesEasy(
  (* iopad_external_pin, clkbuf_inhibit *) input clk,
  (* iopad_external_pin *) input rst_n, spi_ss_n, spi_sck, spi_mosi,
  (* iopad_external_pin *) output clk_en, spi_miso, spi_miso_en, LED, LED_en
);
wire clear_pulse, capturing;
{wiring}
{top} dut ({', '.join(connections)});
wire [15:0] probe = {{{', '.join(probe_parts)}}};
wire trigger_event = {trigger_rtl};
shrike_traces_shell #(.USE_EXTERNAL_TRIGGER(1)) analyzer (
  .clk(clk), .rst_n(rst_n), .clk_en(clk_en),
  .spi_ss_n(spi_ss_n), .spi_sck(spi_sck), .spi_mosi(spi_mosi),
  .spi_miso(spi_miso), .spi_miso_en(spi_miso_en), .led(LED), .led_en(LED_en),
  .probe(probe), .trigger_event(trigger_event), .clear(clear_pulse), .capturing(capturing),
  .primed(), .triggered(), .done()
);
endmodule
'''
    (src / "top_easy.v").write_text(wrapper, encoding="utf-8")
    profile = {"schema_version": 1, "id": profile_id, "description": f"{top}: {condition}",
               "top_module": "ShrikeTracesEasy", "sample_count": 16, "trigger_index": 8,
               "bitstream": (work / "ffpga/build/bitstream/FPGA_bitstream_MCU.bin").relative_to(root).as_posix(),
               "signals": signals, "configuration": config,
               "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "assertions": [{"name": "trigger_inputs_ok", "expression": f"(not trigger) or ({condition})", "expect": 1}]}
    (work / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    print(f"Prepared {top}: {width}/16 probe bits; trigger {condition}", flush=True)
    print(f"Generated files: {work}", flush=True)
    return work, profile


def build_command(work: Path) -> list[str]:
    return make_command(work, ['top', 'ShrikeTracesEasy', 'VERILATOR='])


def check_board(port: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mpremote", "connect", port, "exec", "import os; print(os.uname().machine)"],
        text=True, capture_output=True, timeout=20,
    )
    if result.returncode:
        raise SetupError(f"Cannot connect to MicroPython on {port}: {result.stderr.strip() or result.stdout.strip()}")
    if "Shrike" not in result.stdout or "RP2040" not in result.stdout:
        raise SetupError(f"{port} did not identify as Shrike Lite with RP2040. Install the Shrike Lite MicroPython firmware.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build and capture a combinational or single-clock DUT from one configuration.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--port", default="auto", help="serial port; automatically selected if exactly one is available")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true", help="generate files without building or touching the board")
    modes.add_argument("--build-only", action="store_true", help="generate and build without touching the board")
    modes.add_argument("--capture-only", action="store_true", help="flash and capture the previously built image")
    parser.add_argument("--no-view", action="store_true")
    parser.add_argument("--trigger", help="override the trigger, e.g. 'count == 17 || up_down == 1'")
    args = parser.parse_args(argv)
    try:
        work, profile = prepare(args.config, trigger_override=args.trigger)
        if args.prepare_only:
            return 0
        if not args.build_only:
            try:
                import mpremote  # noqa: F401
                from serial.tools.list_ports import comports
            except ImportError as exc:
                raise SetupError("Install the host dependency first: python -m pip install -r requirements.txt") from exc
            ports = [p.device for p in comports()]
            if args.port == "auto":
                if len(ports) != 1:
                    raise SetupError(f"Select the board with --port. Available ports: {', '.join(ports) or 'none'}")
                args.port = ports[0]
            elif args.port not in ports:
                raise SetupError(f"Port {args.port} is unavailable. Available ports: {', '.join(ports) or 'none'}")
            print(f"Checking Shrike Lite on {args.port}...", flush=True)
            check_board(args.port)
        bitstream = ROOT / profile["bitstream"]
        if not args.capture_only:
            log_path = work / "build.log"
            print(f"Building FPGA image; details in {log_path}", flush=True)
            with log_path.open("w", encoding="utf-8") as log:
                result = subprocess.run(build_command(work), cwd=work, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise SetupError(f"Build failed; see {log_path}")
            if not bitstream.is_file():
                raise SetupError("Build did not produce the MCU bitstream.")
            (work / ".build-source-sha256").write_text(profile["source_sha256"] + "\n", encoding="ascii")
            print("Build complete.", flush=True)
        elif not bitstream.is_file():
            raise SetupError("No built image was found. Run 'python trace.py build' first.")
        elif not (work / ".build-source-sha256").is_file() or (work / ".build-source-sha256").read_text(encoding="ascii").strip() != profile["source_sha256"]:
            raise SetupError("The imported RTL changed after the last build. Run 'python trace.py build' again.")
        profile['bitstream_sha256'] = hashlib.sha256(bitstream.read_bytes()).hexdigest()
        (work / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
        if args.build_only:
            return 0
        base = [sys.executable, "-m", "mpremote", "connect", args.port]
        subprocess.run([*base, "cp", str(bitstream), ":"], check=True)
        subprocess.run([*base, "cp", str(ROOT / "firmware/micropython/shrike_traces.py"), ":"], check=True)
        subprocess.run([*base, "exec", f"import shrike; shrike.flash('{bitstream.name}')"], check=True)
        print(f"Capturing on {args.port}...", flush=True)
        subprocess.run([sys.executable, str(ROOT / "host/capture.py"), "--profile", str(work / "profile.json"),
                        "--port", args.port, "--mpremote-python", sys.executable], check=True)
        if not args.no_view:
            candidates = list((ROOT / "captures").glob(f"capture_{profile['id']}_*.vcd"))
            viewer = shutil.which("gtkwave") or shutil.which("gtkwave.exe")
            if viewer and candidates:
                try:
                    subprocess.Popen([viewer, str(max(candidates, key=lambda p: p.stat().st_mtime))])
                except OSError as exc:
                    print(f"Capture saved; the waveform viewer could not open: {exc}")
            else:
                print("Capture saved. Install GTKWave to open waveforms automatically.")
        return 0
    except (SetupError, RuntimeError, OSError, json.JSONDecodeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"error: {exc}\n")
