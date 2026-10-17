`timescale 1ns/1ps

// Mask/value trigger. Mask bits at zero are don't-care bits.
module trigger_unit #(
  parameter integer WIDTH = 16
)(
  input  wire [WIDTH-1:0] probe,
  input  wire [WIDTH-1:0] mask,
  input  wire [WIDTH-1:0] value,
  output wire             match
);

  assign match = ((probe & mask) == (value & mask));

endmodule
