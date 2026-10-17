`timescale 1ns/1ps

// Deterministic, board-only stimulus harness for the unmodified ISCAS'85 c17
// netlist. The five-bit counter eventually exercises all 32 input vectors.
module c17_harness(
  input  wire       clk,
  input  wire       rst_n,
  input  wire       clear,
  input  wire       enable,
  output wire [4:0] vector,
  output wire       n22,
  output wire       n23
);

  reg [4:0] stimulus;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      stimulus <= 5'd0;
    else if (clear)
      stimulus <= 5'd0;
    else if (enable)
      stimulus <= stimulus + 1'b1;
  end

  assign vector = stimulus;

  c17 dut (
    .N1  (stimulus[0]),
    .N2  (stimulus[1]),
    .N3  (stimulus[2]),
    .N6  (stimulus[3]),
    .N7  (stimulus[4]),
    .N22 (n22),
    .N23 (n23)
  );

endmodule
