`timescale 1ns/1ps

// Pure combinational DUT for the shrike-traces logic4 demonstration.
// Boolean function: y = (a & b) | (c & d)
module and_or_dut(
  input  wire a,
  input  wire b,
  input  wire c,
  input  wire d,
  output wire ab,
  output wire cd,
  output wire y
);

  assign ab = a & b;
  assign cd = c & d;
  assign y  = ab | cd;

endmodule
