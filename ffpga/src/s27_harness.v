`timescale 1ns/1ps

// Deterministic stimulus around the unmodified sequential ISCAS'89 s27.
// When capture is idle, 4'b0111 drives the circuit into a known fixed state
// within two clocks despite the benchmark's intentionally reset-less DFFs.
module s27_harness(
  input  wire       clk,
  input  wire       rst_n,
  input  wire       clear,
  input  wire       enable,
  output wire [3:0] vector,
  output wire       g17
);

  reg [3:0] stimulus;
  wire [3:0] applied = enable ? stimulus : 4'b0111;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      stimulus <= 4'd0;
    else if (clear)
      stimulus <= 4'd0;
    else if (enable)
      stimulus <= stimulus + 1'b1;
  end

  assign vector = stimulus;

  s27 dut (
    .CK  (clk),
    .G0  (applied[0]),
    .G1  (applied[1]),
    .G2  (applied[2]),
    .G3  (applied[3]),
    .G17 (g17)
  );

endmodule
