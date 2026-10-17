`timescale 1ns/1ps

// shrike-traces logic4 profile. A 4-bit counter exercises all 16 input vectors,
// so no external switches or jumper wires are required.
module ShrikeTracesLogic4(
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

  wire       clear_pulse;
  wire       scope_capturing;
  wire       scope_primed;
  wire       scope_triggered;
  wire       scope_done;

  reg  [3:0] stimulus;
  wire       a = stimulus[0];
  wire       b = stimulus[1];
  wire       c = stimulus[2];
  wire       d = stimulus[3];
  wire       ab;
  wire       cd;
  wire       y;
  wire [15:0] probe;

  shrike_traces_shell #(
    .TRIGGER_MASK  (16'h000f),
    .TRIGGER_VALUE (16'h0003)
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

  // Exercise input vectors 0000 through 1111 repeatedly while capturing.
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      stimulus <= 4'h0;
    else if (clear_pulse)
      stimulus <= 4'h0;
    else if (scope_capturing)
      stimulus <= stimulus + 1'b1;
  end

  and_or_dut dut (
    .a  (a),
    .b  (b),
    .c  (c),
    .d  (d),
    .ab (ab),
    .cd (cd),
    .y  (y)
  );

  // Probe map:
  // [3:0] inputs a,b,c,d; [4] a&b; [5] c&d; [6] y;
  // [10:7] stimulus index; [14] primed; [15] triggered.
  assign probe[0]    = a;
  assign probe[1]    = b;
  assign probe[2]    = c;
  assign probe[3]    = d;
  assign probe[4]    = ab;
  assign probe[5]    = cd;
  assign probe[6]    = y;
  assign probe[10:7] = stimulus;
  assign probe[13:11] = 3'b000;
  assign probe[14]   = scope_primed;
  assign probe[15]   = scope_triggered;

endmodule
