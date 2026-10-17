`timescale 1ns/1ps

module S27Baseline(
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

  wire [3:0] vector;
  wire       g17;

  assign clk_en      = 1'b1;
  assign LED_en      = 1'b1;
  assign LED         = g17;
  assign spi_miso    = 1'b0;
  assign spi_miso_en = 1'b0;

  s27_harness benchmark (
    .clk(clk), .rst_n(rst_n), .clear(1'b0),
    .enable(1'b1), .vector(vector), .g17(g17)
  );

  wire unused_spi = spi_ss_n ^ spi_sck ^ spi_mosi ^ vector[0];

endmodule
