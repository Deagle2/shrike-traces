`timescale 1ns/1ps

// v0.1 capture memory: flip-flop/register backed, not physical BRAM.
// A 16 x 16 implementation is only 256 bits and keeps the first milestone
// independent of the SLG47910 BRAM pseudo-port mapping.
module trace_mem_regs #(
  parameter integer WIDTH      = 16,
  parameter integer DEPTH      = 16,
  parameter integer ADDR_WIDTH = 4
)(
  input  wire                  clk,
  input  wire                  wr_en,
  input  wire [ADDR_WIDTH-1:0] wr_addr,
  input  wire [WIDTH-1:0]      wr_data,
  input  wire [ADDR_WIDTH-1:0] rd_addr,
  output wire [WIDTH-1:0]      rd_data
);

  (* keep *) reg [WIDTH-1:0] memory [0:DEPTH-1];

  always @(posedge clk) begin
    if (wr_en)
      memory[wr_addr] <= wr_data;
  end

  assign rd_data = memory[rd_addr];

endmodule
