`timescale 1ns/1ps

// c17 plus the same autonomous stimulus harness, without shrike-traces. This
// provides the physical implementation baseline for instrumentation overhead.
module C17Baseline(
  (* iopad_external_pin, clkbuf_inhibit *) input  clk,
  (* iopad_external_pin *)                 output clk_en,
  (* iopad_external_pin *)                 input  rst_n,

  (* iopad_external_pin *) input  spi_ss_n,
  (* iopad_external_pin *) input  spi_sck,
  (* iopad_external_pin *) input  spi_mosi,
  (* iopad_external_pin *) output spi_miso,
  (* iopad_external_pin *) output spi_miso_en,

  (* iopad_external_pin *) output LED,
  (* iopad_external_pin *) output LED_en
);

  wire [4:0] vector;
  wire       n22;
  wire       n23;

  assign clk_en      = 1'b1;
  assign LED_en      = 1'b1;
  assign LED         = n22 ^ n23;
  assign spi_miso    = 1'b0;
  assign spi_miso_en = 1'b0;

  c17_harness benchmark (
    .clk    (clk),
    .rst_n  (rst_n),
    .clear  (1'b0),
    .enable (1'b1),
    .vector (vector),
    .n22    (n22),
    .n23    (n23)
  );

  // Keep the fixed shrike-traces pin interface identical for a fair I/O plan.
  wire unused_spi = spi_ss_n ^ spi_sck ^ spi_mosi ^ vector[0];

endmodule
