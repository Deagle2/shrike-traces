`timescale 1ns/1ps

// shrike-traces instrumented ISCAS'85 c17 benchmark.
module ShrikeTracesC17(
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

  wire        clear_pulse;
  wire        scope_capturing;
  wire        scope_primed;
  wire        scope_triggered;
  wire        scope_done;
  wire [4:0]  vector;
  wire        n22;
  wire        n23;
  wire [15:0] probe;

  shrike_traces_shell #(
    .TRIGGER_MASK  (16'h001f),
    .TRIGGER_VALUE (16'h0008)
  ) analyzer (
    .clk         (clk),
    .rst_n       (rst_n),
    .clk_en      (clk_en),
    .spi_ss_n    (spi_ss_n),
    .spi_sck     (spi_sck),
    .spi_mosi    (spi_mosi),
    .spi_miso    (spi_miso),
    .spi_miso_en (spi_miso_en),
    .led         (LED),
    .led_en      (LED_en),
    .probe       (probe),
    .trigger_event (1'b0),
    .clear       (clear_pulse),
    .capturing   (scope_capturing),
    .primed      (scope_primed),
    .triggered   (scope_triggered),
    .done        (scope_done)
  );

  c17_harness benchmark (
    .clk    (clk),
    .rst_n  (rst_n),
    .clear  (clear_pulse),
    .enable (scope_capturing),
    .vector (vector),
    .n22    (n22),
    .n23    (n23)
  );

  // [4:0] benchmark inputs, [6:5] outputs, [14] primed, [15] triggered.
  assign probe[4:0]  = vector;
  assign probe[5]    = n22;
  assign probe[6]    = n23;
  assign probe[13:7] = 7'b0;
  assign probe[14]   = scope_primed;
  assign probe[15]   = scope_triggered;

endmodule
