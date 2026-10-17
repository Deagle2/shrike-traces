`timescale 1ns/1ps

module tb_scope_core;
  localparam int PROBE_WIDTH = 16;
  localparam int TRACE_DEPTH = 16;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic arm = 1'b0;
  logic clear = 1'b0;
  logic start = 1'b0;

  wire [7:0] dut_count;
  wire [1:0] dut_state;
  wire dut_running;
  wire dut_done;
  wire dut_terminal;
  wire capturing;
  wire primed;
  wire triggered;
  wire done;
  logic [3:0] rd_index;
  wire [15:0] rd_data;
  wire [3:0] trigger_ptr;
  wire [15:0] probe;

  logic [15:0] snapshot [0:15];
  logic [15:0] expected;
  integer i;
  integer timeout;

  always #5 clk = ~clk;

  demo_dut dut (
    .clk      (clk),
    .rst_n    (rst_n),
    .start    (start),
    .count    (dut_count),
    .state    (dut_state),
    .running  (dut_running),
    .done     (dut_done),
    .terminal (dut_terminal)
  );

  assign probe[7:0] = dut_count;
  assign probe[9:8] = dut_state;
  assign probe[10]  = dut_running;
  assign probe[11]  = dut_done;
  assign probe[12]  = start;
  assign probe[13]  = dut_terminal;
  assign probe[14]  = primed;
  assign probe[15]  = triggered;

  shrike_traces_core #(
    .PROBE_WIDTH (PROBE_WIDTH),
    .TRACE_DEPTH (TRACE_DEPTH),
    .ADDR_WIDTH  (4),
    .PRE_SAMPLES (8)
  ) scope (
    .clk           (clk),
    .rst_n         (rst_n),
    .arm           (arm),
    .clear         (clear),
    .probe         (probe),
    .trigger_mask  (16'h03ff),
    .trigger_value (16'h0120),
    .trigger_event (1'b0),
    .capturing     (capturing),
    .primed        (primed),
    .triggered     (triggered),
    .done          (done),
    .rd_index      (rd_index),
    .rd_data       (rd_data),
    .trigger_ptr   (trigger_ptr)
  );

  initial begin
    $dumpfile("build/shrike_traces.vcd");
    $dumpvars(0, tb_scope_core);

    repeat (4) @(posedge clk);
    rst_n <= 1'b1;

    @(posedge clk);
    arm <= 1'b1;
    @(posedge clk);
    arm <= 1'b0;

    timeout = 0;
    while (!primed && timeout < 40) begin
      @(posedge clk);
      timeout = timeout + 1;
    end
    if (!primed)
      $fatal(1, "scope never became primed");

    // Start the DUT only after the pre-trigger history is valid.
    @(posedge clk);
    start <= 1'b1;
    @(posedge clk);
    start <= 1'b0;

    timeout = 0;
    while (!done && timeout < 160) begin
      @(posedge clk);
      timeout = timeout + 1;
    end
    if (!done)
      $fatal(1, "scope never completed capture");
    if (!triggered)
      $fatal(1, "DONE asserted without trigger status");
    if (capturing)
      $fatal(1, "capturing remained high in DONE");

    // Circular-buffer readout must be chronological. Index 8 is the trigger.
    for (i = 0; i < TRACE_DEPTH; i = i + 1) begin
      rd_index = i[3:0];
      #1;
      if (i <= 8)
        expected = 16'h4500 + (8'h18 + i);
      else
        expected = 16'hc500 + (8'h18 + i);

      if (rd_data !== expected)
        $fatal(1, "trace[%0d] expected %04h, got %04h", i, expected, rd_data);
      snapshot[i] = rd_data;
    end

    if (snapshot[8][7:0] != 8'h20)
      $fatal(1, "trigger is not at logical index 8");

    // Once DONE, the frozen trace must not change.
    repeat (12) @(posedge clk);
    for (i = 0; i < TRACE_DEPTH; i = i + 1) begin
      rd_index = i[3:0];
      #1;
      if (rd_data !== snapshot[i])
        $fatal(1, "trace changed after DONE at index %0d", i);
    end

    $display("PASS: trigger centered at index 8; 8 pre + 1 trigger + 7 post samples verified");
    $finish;
  end

endmodule
