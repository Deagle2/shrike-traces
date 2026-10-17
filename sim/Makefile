IVERILOG ?= iverilog
VVP      ?= vvp

RTL_CORE := ../ffpga/src/demo_dut.v \
            ../ffpga/src/trigger_unit.v \
            ../ffpga/src/trace_mem_regs.v \
            ../ffpga/src/scope_controller.v \
            ../ffpga/src/shrike_traces_core.v

RTL_SPI := $(RTL_CORE) \
           ../ffpga/src/spi_target.v \
           ../ffpga/src/scope_spi_regs.v \
           ../ffpga/src/shrike_traces_shell.v \
           ../ffpga/src/top_spi.v

RTL_LOGIC4 := ../ffpga/src/and_or_dut.v \
              ../ffpga/src/trigger_unit.v \
              ../ffpga/src/trace_mem_regs.v \
              ../ffpga/src/scope_controller.v \
              ../ffpga/src/shrike_traces_core.v \
              ../ffpga/src/spi_target.v \
              ../ffpga/src/scope_spi_regs.v \
              ../ffpga/src/shrike_traces_shell.v \
              ../ffpga/src/top_logic4.v

RTL_C17 := ../ffpga/src/iscas85_c17.v \
           ../ffpga/src/c17_harness.v \
           ../ffpga/src/trigger_unit.v \
           ../ffpga/src/trace_mem_regs.v \
           ../ffpga/src/scope_controller.v \
           ../ffpga/src/shrike_traces_core.v \
           ../ffpga/src/spi_target.v \
           ../ffpga/src/scope_spi_regs.v \
           ../ffpga/src/shrike_traces_shell.v \
           ../ffpga/src/top_c17_scope.v

RTL_S27 := ../ffpga/src/iscas89_s27.v \
           ../ffpga/src/s27_harness.v \
           ../ffpga/src/trigger_unit.v \
           ../ffpga/src/trace_mem_regs.v \
           ../ffpga/src/scope_controller.v \
           ../ffpga/src/shrike_traces_core.v \
           ../ffpga/src/spi_target.v \
           ../ffpga/src/scope_spi_regs.v \
           ../ffpga/src/shrike_traces_shell.v \
           ../ffpga/src/top_s27_scope.v

.PHONY: all test test_core test_spi test_logic4 test_c17 test_s27 clean

all: test

test: test_core test_spi test_logic4 test_c17 test_s27

test_core: build/tb_scope_core.vvp
	$(VVP) $<

test_spi: build/tb_scope_spi.vvp
	$(VVP) $<

test_logic4: build/tb_scope_logic4.vvp
	$(VVP) $<

test_c17: build/tb_scope_c17.vvp
	$(VVP) $<

test_s27: build/tb_scope_s27.vvp
	$(VVP) $<

build/tb_scope_core.vvp: tb_scope_core.sv $(RTL_CORE)
	mkdir -p build
	$(IVERILOG) -g2012 -Wall -s tb_scope_core -o $@ $(RTL_CORE) $<

build/tb_scope_spi.vvp: tb_scope_spi.sv $(RTL_SPI)
	mkdir -p build
	$(IVERILOG) -g2012 -Wall -s tb_scope_spi -o $@ $(RTL_SPI) $<

build/tb_scope_logic4.vvp: tb_scope_logic4.sv $(RTL_LOGIC4)
	mkdir -p build
	$(IVERILOG) -g2012 -Wall -s tb_scope_logic4 -o $@ $(RTL_LOGIC4) $<

build/tb_scope_c17.vvp: tb_scope_c17.sv $(RTL_C17)
	mkdir -p build
	$(IVERILOG) -g2012 -Wall -s tb_scope_c17 -o $@ $(RTL_C17) $<

build/tb_scope_s27.vvp: tb_scope_s27.sv $(RTL_S27)
	mkdir -p build
	$(IVERILOG) -g2012 -Wall -s tb_scope_s27 -o $@ $(RTL_S27) $<

clean:
	rm -rf build
