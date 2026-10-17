# Vulcan's Makefile for SLG47910V / Shrike Lite, part of shrike-gen
#
# Role-aware: automatically detects workspace vs project context.
# A project directory is identified by the presence of a *.ffpga file.
#
# ── WORKSPACE MODE (no *.ffpga here / shrike.mk) ─────────────────────────────
#   make init                  create ./shrike-gen symlink + set up mpremote
#   make project Name          create a new Verilog project skeleton
#   make vhdlproject Name      create a new VHDL project skeleton
#   make list                  list existing projects
#   make mpremote-install      install the flash tool (mpremote) into ~/.local
#   make help                  show this message
#
# ── PROJECT MODE (*.ffpga / shrike.mk present) ───────────────────────────────
#   make                       update + full build (if top module annotated with (* top *))
#   make top                   update + build with -top TOP from shrike.mk
#   make top <TopModuleName>   update + build with -top <TopModuleName>
#   make update                regenerate .ffpga and io_spec_in.txt from io_map.pcf
#                              (also re-scans ffpga/src/*.v — picks up new/renamed files)
#   make build                 lint → synth → pnr → collect (skip update)
#   make lint                  verilator lint only
#   make synth                 synthesis only
#   make flash                 copy bitstream to MCU + shrike.flash() the FPGA
#   make clean                 remove all build outputs (keeps source + constraints)
#   make help                  show help message

# Setting up Bash as the default shell.
SHELL := /bin/bash

# ── Context detection ─────────────────────────────────────────────────────────
# The presence of a *.ffpga file is the canonical marker for a project dir.
_FFPGA_FILE := $(firstword $(wildcard *.ffpga))

# ── Shared: mpremote provisioning (used by `init` in workspace mode and by
PYTHON       ?= python3
AUTO_INSTALL ?= 1
MPREMOTE     ?= $(if $(shell command -v mpremote 2>/dev/null),mpremote,$(PYTHON) -m mpremote)

.PHONY: mpremote-install

# Install into the Python user site (~/.local) — no venv, system packages
# untouched. Idempotent: if mpremote is importable OR on PATH (pipx/uv/system),
# use that and install nothing. On PEP 668 distros the --user install is
# retried with --break-system-packages (still writes only to ~/.local).
mpremote-install:
	@if $(PYTHON) -c "import mpremote" 2>/dev/null || command -v mpremote >/dev/null 2>&1; then \
	  echo "  mpremote: already available"; \
	else \
	  echo "  mpremote: installing into user site (no venv)..."; \
	  $(PYTHON) -m pip install --user mpremote 2>/dev/null \
	    || $(PYTHON) -m pip install --user --break-system-packages mpremote \
	    || { echo "  mpremote: pip install FAILED — is pip present? ($(PYTHON) -m pip --version)"; exit 1; }; \
	  $(PYTHON) -c "import mpremote" >/dev/null 2>&1 \
	    && echo "  mpremote: OK ($(PYTHON) -m mpremote)" \
	    || { echo "  mpremote: not importable after install"; exit 1; }; \
	fi

ifeq (,$(_FFPGA_FILE))
# =============================================================================
# WORKSPACE MODE
# =============================================================================

SHRIKE_GEN := shrike_gen/shrike-gen.py

.DEFAULT_GOAL := help
.PHONY: init project _project vhdlproject _vhdlproject list help

# ── make init ─────────────────────────────────────────────────────────────────
init:
	@if [ -e shrike-gen ]; then \
	  echo "  shrike-gen already exists — skipping"; \
	else \
		chmod +x shrike_gen/shrike-gen.py; \
		ln -sf shrike_gen/shrike-gen.py shrike-gen; \
		echo "  Symlink created: ./shrike-gen → shrike_gen/shrike-gen.py"; \
	fi
	@echo "  Setting up flash tooling..."
	@$(MAKE) --no-print-directory mpremote-install \
	 || echo "  mpremote: skipped — 'make flash' will retry, or run 'make mpremote-install'"

# ── make project [NAME=]ProjectName ──────────────────────────────────────────
# Also supports positional form: make project MyBlink
# The word after "project" on the command line is captured as a Make target
# (which would normally fail); the catch-all rule below silences it.
_POSITIONAL_NAME := $(filter-out project vhdlproject,$(MAKECMDGOALS))

project: _project

_project:
	@name="$(or $(NAME),$(_POSITIONAL_NAME))"; \
	if [ -z "$$name" ]; then \
		echo ""; \
		echo "  Usage:  make project NAME=<ProjectName>"; \
		echo "          make project <ProjectName>"; \
		echo ""; \
		exit 1; \
	fi; \
	python3 $(SHRIKE_GEN) "$$name"

# ── make vhdlproject [NAME=]ProjectName ───────────────────────────────────────
vhdlproject: _vhdlproject

_vhdlproject:
	@name="$(or $(NAME),$(_POSITIONAL_NAME))"; \
	if [ -z "$$name" ]; then \
		echo ""; \
		echo "  Usage:  make vhdlproject NAME=<ProjectName>"; \
		echo "          make vhdlproject <ProjectName>"; \
		echo ""; \
		exit 1; \
	fi; \
	python3 $(SHRIKE_GEN) --type vhdl "$$name"

# Swallow the positional project name so Make doesn't error on an unknown target
$(filter-out project vhdlproject list help _project _vhdlproject init mpremote-install,$(MAKECMDGOALS)):
	@:

# ── make list ─────────────────────────────────────────────────────────────────
list:
	@echo ""
	@echo "  Projects in $(CURDIR):"
	@for d in */Makefile; do \
		proj=$$(dirname $$d); \
		ffpga=$$proj/*.ffpga; \
		[ -f $$ffpga ] && echo "    $$proj" || true; \
	done
	@echo ""

# ── make help ─────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Shrike Lite / SLG47910V shrike-gen"
	@echo ""
	@echo "  make init                       create ./shrike-gen symlink + set up mpremote"
	@echo "  make project ProjectName        create a new Verilog project"
	@echo "  make vhdlproject ProjectName    create a new VHDL project (oss-cad-suite)"
	@echo "  make list                       list existing projects"
	@echo "  make mpremote-install           install the flash tool (mpremote) into ~/.local"
	@echo ""
	@echo " cd ProjectName"
	@echo ""
	@echo " Then, inside the project:"
	@echo "    Verilog: Edit ffpga/src/main.v       edit Verilog"
	@echo "    VHDL:    Edit ffpga/src/main.vhd     edit VHDL"
	@echo "    Edit io_map.pcf                      edit pin constraints"
	@echo "    make                                 update + full build"
	@echo "    make update                          regenerate .ffpga + io_spec_in.txt"
	@echo "    make build                           build only (skip update)"
	@echo "    make flash                           flash the bitstream to the FPGA"
	@echo "    make clean                           clean build outputs"
	@echo ""
	@echo "  Bitstreams land in: ProjectName/ffpga/build/bitstream/"
	@echo "    FPGA_bitstream_MCU.bin"
	@echo "    FPGA_bitstream_OTP.bin"
	@echo "    FPGA_bitstream_FLASH_MEM.bin"
	@echo ""

else
# =============================================================================
# PROJECT MODE  —  identity comes from shrike.mk (written by shrike-gen)
# =============================================================================

include shrike.mk

# ── Project type (verilog or vhdl, set in shrike.mk) ─────────────────────────
PROJECT_TYPE ?= verilog

# ── Directories ───────────────────────────────────────────────────────────────
PROJECT_DIR := $(CURDIR)
SRC_DIR     := $(PROJECT_DIR)/ffpga/src
BUILD_DIR   := $(PROJECT_DIR)/ffpga/build
TOOLS_DIR   := $(PROJECT_DIR)/shrike_gen

# ── Generator scripts ─────────────────────────────────────────────────────────
GEN_IO_SPEC    := $(TOOLS_DIR)/gen_io_spec.py
GEN_FFPGA      := $(TOOLS_DIR)/gen_ffpga.py
GEN_FPGA_DATA  := $(TOOLS_DIR)/gen_fpga_data.py
GEN_BITSTREAMS := $(TOOLS_DIR)/gen_bitstreams.py

# ── Tool binaries (Go Configure Software Hub) ─────────────────────────────────
GCSW        ?= /opt/go-configure-sw-hub/bin/external
YOSYS       := $(GCSW)/yosys/v59/yosys
VERILATOR   := $(GCSW)/verilator/bin/verilator_bin
EDA_PLACER  := $(GCSW)/eda-placer/v23/eda-placer

VERILATOR_ROOT         := $(GCSW)/verilator
EFLX_COMPILER_INSTALL  := $(GCSW)/eda-placer/v23
export VERILATOR_ROOT
export EFLX_COMPILER_INSTALL

# ── OSS-CAD-Suite tools (for VHDL via GHDL+Yosys) ────────────────────────────
OSS_CAD    := /opt/oss-cad-suite
YOSYS_VHDL := $(OSS_CAD)/bin/yosys
GHDL       := $(OSS_CAD)/bin/ghdl
#GHDL_PREFIX:= $(OSS_CAD)/lib/ghdl
#export GHDL_PREFIX
# ── Sources / constraints / outputs ───────────────────────────────────────────
# Discover all Verilog sources in SRC_DIR automatically
VSRC_FILES     := $(wildcard $(SRC_DIR)/*.v)
VSRC_BASENAMES := $(notdir $(VSRC_FILES))
# Quoted paths for yosys read_verilog (relative from BUILD_DIR → ../src/)
SYNTH_VFILES   := $(patsubst %,"../src/%",$(VSRC_BASENAMES))

# Discover all VHDL sources in SRC_DIR automatically
VHDSRC_FILES     := $(wildcard $(SRC_DIR)/*.vhd)
VHDSRC_BASENAMES := $(notdir $(VHDSRC_FILES))

# ── Top-module handling ───────────────────────────────────────────────────────
#   make                       → no -top flag (yosys auto-detects (* top *))
#   make top                   → synth_xilinx ... -top TOP from shrike.mk
#   make top <TopModuleName>   → synth_xilinx ... -top <TopModuleName>
_KNOWN_MAKE_TARGETS := all update build lint synth pnr collect clean check-tools \
                       flash check-mpremote help top mpremote-install
_TOP_MODULE_ARG     := $(filter-out $(_KNOWN_MAKE_TARGETS),$(MAKECMDGOALS))

ifeq (top,$(filter top,$(MAKECMDGOALS)))
  ifneq (,$(_TOP_MODULE_ARG))
    SYNTH_TOP_FLAG := -top $(_TOP_MODULE_ARG)
  else
    SYNTH_TOP_FLAG := -top $(TOP)
  endif
else
  SYNTH_TOP_FLAG :=
endif

PCF        := $(PROJECT_DIR)/io_map.pcf
IO_SPEC    := $(BUILD_DIR)/io_spec_in.txt
FLOOR_PLAN := $(BUILD_DIR)/floorplanspec.fp
FLOOR_PLAN_TEMPLATE := $(PROJECT_DIR)/ffpga/floorplanspec.fp
FFPGA      := $(PROJECT_DIR)/$(PROJECT).ffpga
NETLIST    := $(BUILD_DIR)/netlist.edif
SYNTH_YS   := $(BUILD_DIR)/synth_script.ys

.DEFAULT_GOAL := all

.PHONY: all update build lint synth pnr collect clean check-tools flash check-mpremote help top

# ── all: update then full build ───────────────────────────────────────────────
all: update build

# ── top: update then force synthesis with explicit -top flag ─────────────────
# Usage: make top                  → -top TOP from shrike.mk
#        make top <TopModuleName>  → -top <TopModuleName>
# This is needed when the top module is not annotated with (* top *)
top: update
	@# The selected top is a command-line value, not a file dependency. Remove
	@# only the generated netlist so switching profiles cannot reuse stale RTL.
	@$(RM) $(NETLIST)
	@$(MAKE) --no-print-directory build SYNTH_TOP_FLAG='$(SYNTH_TOP_FLAG)'

# Swallow the positional module-name argument so Make doesn't error on it
$(filter-out $(_KNOWN_MAKE_TARGETS),$(MAKECMDGOALS)):
	@:

# ── update: regenerate .ffpga and io_spec_in.txt from io_map.pcf ──────────────
ifeq ($(PROJECT_TYPE),vhdl)
_SRC_BASENAMES_FOR_FFPGA := $(VHDSRC_BASENAMES)
else
_SRC_BASENAMES_FOR_FFPGA := $(VSRC_BASENAMES)
endif

update: $(PCF) $(FLOOR_PLAN_TEMPLATE) $(BUILD_DIR)
	@echo "=== Update: generating io_spec_in.txt and $(PROJECT).ffpga ==="
	cp $(FLOOR_PLAN_TEMPLATE) $(FLOOR_PLAN)
	python3 $(GEN_IO_SPEC) \
		--pcf        $(PCF) \
		--out-iospec $(IO_SPEC)
	python3 $(GEN_FFPGA) \
		--project    $(PROJECT) \
		--sources    $(_SRC_BASENAMES_FOR_FFPGA) \
		--pcf        $(PCF) \
		--max-cpu    $$(nproc) \
		--out        $(FFPGA)
	@echo "Update OK"

# ── build: full pipeline (lint → synth → pnr → collect) ──────────────────────
build: check-tools pnr

# ── check-tools: verify external binaries and generated inputs exist ──────────
check-tools:
ifeq ($(PROJECT_TYPE),vhdl)
	@test -x "$(YOSYS_VHDL)" || (echo "ERROR: yosys not found at $(YOSYS_VHDL) (oss-cad-suite missing?)"; exit 1)
	@test -x "$(GHDL)"       || (echo "ERROR: ghdl not found at $(GHDL) (oss-cad-suite missing?)";   exit 1)
else
	@test -x $(YOSYS)     || (echo "ERROR: yosys not found at $(YOSYS)"; exit 1)
	@test -x $(VERILATOR) || (echo "ERROR: verilator not found at $(VERILATOR)"; exit 1)
endif
	@test -x $(EDA_PLACER) || (echo "ERROR: eda-placer not found at $(EDA_PLACER)"; exit 1)
	@test -f $(IO_SPEC)    || (echo "ERROR: io_spec_in.txt missing — run: make update"; exit 1)
	@test -f $(FLOOR_PLAN) || (echo "ERROR: floorplanspec.fp missing in $(BUILD_DIR)"; exit 1)
	@echo "Tools OK"

# ── lint ──────────────────────────────────────────────────────────────────────
lint: check-tools
	@echo "=== Lint ==="
ifeq ($(PROJECT_TYPE),vhdl)
	cd $(SRC_DIR) && $(GHDL) -a --std=08 $(VHDSRC_BASENAMES)
else
	cd $(SRC_DIR) && $(VERILATOR) \
		+1364-2005ext+.v \
		-I$(SRC_DIR) \
		--lint-only \
		-Wno-WIDTHEXPAND \
		-Wno-WIDTHTRUNC \
		--timing \
		$(VSRC_BASENAMES)
endif
	@echo "Lint OK"

# ── synth ─────────────────────────────────────────────────────────────────────
ifeq ($(PROJECT_TYPE),vhdl)

# VHDL synthesis via GHDL plugin in oss-cad-suite yosys.
# Run yosys from SRC_DIR so ghdl can resolve .vhd files by basename.
# Output paths use absolute BUILD_DIR so they land in the right place.
_VHDL_TOP := $(if $(_TOP_MODULE_ARG),$(_TOP_MODULE_ARG),$(TOP))
define VHDL_SYNTH_SCRIPT
ghdl --std=08 --work=work $(VHDSRC_BASENAMES) -e $(_VHDL_TOP)
synth_xilinx -nobram -noiopad -nodsp -abc9
clean
autoname
write_verilog "$(BUILD_DIR)/post_synth_results.v"
write_edif "$(BUILD_DIR)/netlist.edif"
tee -q -o $(BUILD_DIR)/post_synth_report.txt stat
endef

synth: lint $(NETLIST)

$(NETLIST): $(VHDSRC_FILES) | $(BUILD_DIR)
	@echo "=== VHDL Synthesis (ghdl + yosys) ==="
	$(file >$(SYNTH_YS),$(VHDL_SYNTH_SCRIPT))
	cd $(SRC_DIR) && $(YOSYS_VHDL) -m ghdl \
		-e '(.*)is implicitly declared\.' \
		-Q \
		-s $(SYNTH_YS)
	@echo "Synthesis OK — netlist: $(NETLIST)"

else

define SYNTH_SCRIPT
read_verilog -sv $(SYNTH_VFILES)
hierarchy -check
flatten -noscopeinfo
synth_xilinx -nobram -noiopad -nodsp -abc9$(if $(SYNTH_TOP_FLAG), $(SYNTH_TOP_FLAG))
clean
autoname
write_verilog "post_synth_results.v"
write_edif "netlist.edif"
tee -q -o post_synth_report.txt stat
endef

ifeq ($(VERILATOR),)
synth: $(NETLIST)
else
synth: lint $(NETLIST)
endif

$(NETLIST): $(VSRC_FILES) | $(BUILD_DIR)
	@echo "=== Synthesis ==="
	$(file >$(SYNTH_YS),$(SYNTH_SCRIPT))
	cd $(BUILD_DIR) && $(YOSYS) \
		-e '(.*)is implicitly declared\.' \
		-Q \
		-s synth_script.ys
	@echo "Synthesis OK — netlist: $(NETLIST)"

endif

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)/bitstream $(BUILD_DIR)/ta_message

# ── pnr: place & route, then collect ─────────────────────────────────────────
pnr: synth
	@echo "=== Place & Route ==="
	$(eval RUNDIR := $(shell mktemp -d /tmp/eflx_XXXXXXXX))
	mkdir -p $(RUNDIR)/config $(RUNDIR)/out
	cp $(IO_SPEC)    $(RUNDIR)/config/io_spec_in.txt
	cp $(FLOOR_PLAN) $(RUNDIR)/config/floorplanspec.fp
	$(eval FPGA_DATA_BLOB := $(shell python3 $(GEN_FPGA_DATA) \
		--netlist $(NETLIST) \
		--fp      $(RUNDIR)/config/floorplanspec.fp \
		--io      $(RUNDIR)/config/io_spec_in.txt))
	@set -o pipefail; \
	 cd $(RUNDIR)/out && $(EDA_PLACER) FPGA_DATA '$(FPGA_DATA_BLOB)' 0 \
		2>&1 | tee $(BUILD_DIR)/PNR_STDOUT.log \
	|| { echo "ERROR: eda-placer failed — see $(BUILD_DIR)/PNR_STDOUT.log"; exit 1; }
	@echo "=== Collecting results ==="
	$(MAKE) collect RUNDIR=$(RUNDIR)
	@echo "PnR OK"

# ── collect: gather eda-placer outputs into ffpga/build/ ─────────────────────
collect:
	@test -n "$(RUNDIR)" || (echo "ERROR: RUNDIR not set"; exit 1)
	@for eflx in $(RUNDIR)/out/EFLX_*.bin $(RUNDIR)/out/EFLX_*.log $(RUNDIR)/out/EFLX_*.sdc; do \
		[ -f "$$eflx" ] || continue; \
		base=$$(basename "$$eflx"); \
		fpga=$$(echo "$$base" | sed 's/EFLX_/FPGA_/'); \
		cp "$$eflx" "$(BUILD_DIR)/$$fpga"; \
		echo "  $$base → $$fpga"; \
	done
	@for f in \
		FPGA_bitstream.bin FPGA_bitstream.log FPGA_bitstream_AXI.log \
		FPGA_case_analysis_RBB.sdc FPGA_case_analysis_top1per.sdc \
		PNR_PACK_PLACE.log PNR_TIMING.log PNR_ROUTE.log PNR_IO.log \
		PNR_PLACER_REGION.log PNR_PLACER_RESOURCE.log PNR_PLACER_TIMING.log \
		clock_tree.txt resource-utilization-report.log \
		PNR_RESOURCE.log PNR_IO.v PNR_STDOUT.log PNR_OUTPUT.log \
		PNR_TRIAL_ROUTE_TIMING.log PNR_PLACE.log RouterInfo.txt \
		EFLX_COMPILER_last_saved.prj $(TOP)_eflx.vm $(TOP)_eflx_array_wrapper.vm; do \
		test -f $(RUNDIR)/out/$$f && cp $(RUNDIR)/out/$$f $(BUILD_DIR)/ || true; \
	done
	@if [ -d $(RUNDIR)/out/minplacer ]; then \
		mkdir -p $(BUILD_DIR)/minplacer; \
		cp -r $(RUNDIR)/out/minplacer/. $(BUILD_DIR)/minplacer/; \
	fi
	@if [ -d $(RUNDIR)/out/ta_message ]; then \
		mkdir -p $(BUILD_DIR)/ta_message; \
		cp -r $(RUNDIR)/out/ta_message/. $(BUILD_DIR)/ta_message/; \
	fi
	@if [ -f "$(BUILD_DIR)/FPGA_bitstream_AXI.log" ]; then \
		mkdir -p $(BUILD_DIR)/bitstream; \
		python3 $(GEN_BITSTREAMS) \
			--axi     $(BUILD_DIR)/FPGA_bitstream_AXI.log \
			--outdir  $(BUILD_DIR)/bitstream \
			--project $(PROJECT) \
			--netlist netlist.edif; \
	fi
	@echo "Collected outputs to $(BUILD_DIR)"

# ── flash: load bitstream onto the MCU, then configure the FPGA via mpremote ──
# VARIANT: MCU | OTP | FLASH_MEM
VARIANT ?= MCU
# FROM: flash another project by name, e.g. make flash FROM=Blink2
FROM ?= $(PROJECT)
# PORT: target a specific board, e.g. make flash PORT=/dev/ttyACM0
PORT ?=
MPCONNECT := $(if $(PORT),connect port:$(PORT),)

# Projects are siblings under the workspace root, so a different one is ../<name>.
ifeq ($(FROM),$(PROJECT))
_FLASH_PROJECT_DIR := $(PROJECT_DIR)
else
_FLASH_PROJECT_DIR := $(PROJECT_DIR)/../$(FROM)
endif

# Override directly for an off-tree file: make flash BITSTREAM=/abs/path/to/file.bin
BITSTREAM ?= $(_FLASH_PROJECT_DIR)/ffpga/build/bitstream/FPGA_bitstream_$(VARIANT).bin
DEV_NAME  := $(notdir $(BITSTREAM))

flash: check-mpremote
	@test -f "$(BITSTREAM)" || { \
	  echo "ERROR: bitstream not found:"; \
	  echo "    $(BITSTREAM)"; \
	  echo "  Build that project first (cd into it, run: make),"; \
	  echo "  or pass BITSTREAM=/path/to/file.bin"; \
	  exit 1; }
	@if [ "$(VARIANT)" = "OTP" ] && [ "$(I_KNOW_OTP_IS_FOREVER)" != "1" ]; then \
	  echo "REFUSING: OTP programming is irreversible."; \
	  echo "Re-run with: make flash VARIANT=OTP I_KNOW_OTP_IS_FOREVER=1"; \
	  exit 1; \
	fi
	@echo "=== Flash: $(BITSTREAM) → MCU → FPGA ==="
	$(MPREMOTE) $(MPCONNECT) cp "$(BITSTREAM)" :
	$(MPREMOTE) $(MPCONNECT) exec "import shrike; shrike.flash('$(DEV_NAME)')"
	@echo "Flash OK"

check-mpremote:
	@if $(MPREMOTE) --help >/dev/null 2>&1; then \
	  : ; \
	elif [ "$(AUTO_INSTALL)" = "1" ]; then \
	  $(MAKE) --no-print-directory mpremote-install; \
	else \
	  echo "ERROR: mpremote not found. Run: make mpremote-install"; \
	  exit 1; \
	fi

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -f  $(BUILD_DIR)/netlist.edif $(BUILD_DIR)/post_synth_results.v
	rm -f  $(BUILD_DIR)/post_synth_report.txt $(BUILD_DIR)/synth_script.ys
	rm -f  $(BUILD_DIR)/FPGA_bitstream* $(BUILD_DIR)/EFLX_bitstream* $(BUILD_DIR)/PNR_*.log
	rm -f  $(BUILD_DIR)/clock_tree.txt $(BUILD_DIR)/resource-utilization-report.log
	rm -f  $(BUILD_DIR)/FPGA_case_analysis_*.sdc $(BUILD_DIR)/*.vm
	rm -rf $(BUILD_DIR)/minplacer $(BUILD_DIR)/ta_message $(BUILD_DIR)/bitstream
	@echo "Clean OK"

# ── help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
ifeq ($(PROJECT_TYPE),vhdl)
	@echo "  $(PROJECT) — SLG47910V (Shrike Lite) VHDL build"
	@echo "  Toolchain: oss-cad-suite (ghdl + yosys) at $(OSS_CAD)"
else
	@echo "  $(PROJECT) — SLG47910V (Shrike Lite) build"
endif
	@echo ""
	@echo "  make                          update + full build"
ifeq ($(PROJECT_TYPE),vhdl)
	@echo "  make top                      update + build, elaborate top entity TOP (shrike.mk)"
	@echo "  make top <TopEntityName>      update + build, elaborate custom top entity"
else
	@echo "  make top                      update + build, set top module to TOP (shrike.mk)"
	@echo "  make top <TopModuleName>      update + build, set top module to custom <TopModuleName>"
endif
	@echo "  make update                   regenerate .ffpga and io_spec_in.txt from io_map.pcf"
	@echo "  make build                    lint → synth → pnr → collect (skip update)"
ifeq ($(PROJECT_TYPE),vhdl)
	@echo "  make lint                     ghdl -a analysis only"
	@echo "  make synth                    VHDL synthesis only (ghdl + yosys -m ghdl)"
else
	@echo "  make lint                     verilator lint only"
	@echo "  make synth                    synthesis only"
endif
	@echo "  make flash                    cp bitstream to MCU + shrike.flash() the FPGA"
	@echo "  make flash FROM=Other         flash another project's bitstream"
	@echo "  make flash PORT=/dev/ttyACM0  target a specific board"
	@echo "  make clean                    remove build outputs"
	@echo ""
	@echo "  Edit files:"
ifeq ($(PROJECT_TYPE),vhdl)
	@echo "    ffpga/src/*.vhd     VHDL sources (all .vhd files are picked up automatically)"
else
	@echo "    ffpga/src/*.v       Verilog sources (all .v files are picked up automatically)"
endif
	@echo "    io_map.pcf          pin constraints"
	@echo ""
ifeq ($(PROJECT_TYPE),vhdl)
	@echo "  Sources detected: $(VHDSRC_BASENAMES)"
else
	@echo "  Sources detected: $(VSRC_BASENAMES)"
endif
	@echo ""
	@echo "  Bitstreams land in: ffpga/build/bitstream/"
	@echo "    FPGA_bitstream_MCU.bin"
	@echo "    FPGA_bitstream_OTP.bin"
	@echo "    FPGA_bitstream_FLASH_MEM.bin"
	@echo ""
endif
