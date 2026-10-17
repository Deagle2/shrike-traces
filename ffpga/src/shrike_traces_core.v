`timescale 1ns/1ps

module shrike_traces_core #(
  parameter integer PROBE_WIDTH = 16,
  parameter integer TRACE_DEPTH = 16,
  parameter integer ADDR_WIDTH  = 4,
  parameter integer PRE_SAMPLES = 8,
  parameter integer USE_EXTERNAL_TRIGGER = 0
)(
  input  wire                   clk,
  input  wire                   rst_n,
  input  wire                   arm,
  input  wire                   clear,
  input  wire [PROBE_WIDTH-1:0] probe,
  input  wire [PROBE_WIDTH-1:0] trigger_mask,
  input  wire [PROBE_WIDTH-1:0] trigger_value,
  input  wire                   trigger_event,
  output wire                   capturing,
  output wire                   primed,
  output wire                   triggered,
  output wire                   done,
  input  wire [ADDR_WIDTH-1:0]  rd_index,
  output wire [PROBE_WIDTH-1:0] rd_data,
  output wire [ADDR_WIDTH-1:0]  trigger_ptr
);

  localparam [ADDR_WIDTH-1:0] PRE_OFFSET = PRE_SAMPLES;

  wire mask_match;
  wire trigger_match = USE_EXTERNAL_TRIGGER ? trigger_event : mask_match;
  wire mem_we;
  wire [ADDR_WIDTH-1:0] mem_wr_addr;
  wire [ADDR_WIDTH-1:0] first_sample_ptr;
  wire [ADDR_WIDTH-1:0] mem_rd_addr;

  trigger_unit #(.WIDTH(PROBE_WIDTH)) trigger (
    .probe (probe),
    .mask  (trigger_mask),
    .value (trigger_value),
    .match (mask_match)
  );

  scope_controller #(
    .TRACE_DEPTH (TRACE_DEPTH),
    .ADDR_WIDTH  (ADDR_WIDTH),
    .PRE_SAMPLES (PRE_SAMPLES)
  ) controller (
    .clk           (clk),
    .rst_n         (rst_n),
    .arm           (arm),
    .clear         (clear),
    .trigger_match (trigger_match),
    .mem_we        (mem_we),
    .mem_wr_addr   (mem_wr_addr),
    .capturing     (capturing),
    .primed        (primed),
    .triggered     (triggered),
    .done          (done),
    .trigger_ptr   (trigger_ptr)
  );

  // ADDR_WIDTH arithmetic intentionally wraps modulo 2**ADDR_WIDTH.
  assign first_sample_ptr = trigger_ptr - PRE_OFFSET;
  assign mem_rd_addr      = first_sample_ptr + rd_index;

  trace_mem_regs #(
    .WIDTH      (PROBE_WIDTH),
    .DEPTH      (TRACE_DEPTH),
    .ADDR_WIDTH (ADDR_WIDTH)
  ) trace_memory (
    .clk     (clk),
    .wr_en   (mem_we),
    .wr_addr (mem_wr_addr),
    .wr_data (probe),
    .rd_addr (mem_rd_addr),
    .rd_data (rd_data)
  );

endmodule
