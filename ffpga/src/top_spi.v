`timescale 1ns/1ps

// shrike-traces v0.2: RP2040-controlled capture and trace readout over SPI0.
module ShrikeTraces(
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

  wire clear_pulse;
  wire scope_capturing;
  wire scope_primed;
  wire scope_triggered;
  wire scope_done;

  reg start;
  reg started;
  wire dut_rst_n = rst_n && !clear_pulse;
  wire [7:0] dut_count;
  wire [1:0] dut_state;
  wire dut_running;
  wire dut_done;
  wire dut_terminal;
  wire [15:0] probe;

  shrike_traces_shell #(
    .TRIGGER_MASK  (16'h03ff),
    .TRIGGER_VALUE (16'h0120)
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

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      start   <= 1'b0;
      started <= 1'b0;
    end else if (clear_pulse) begin
      start   <= 1'b0;
      started <= 1'b0;
    end else begin
      start <= 1'b0;
      if (scope_primed && !started) begin
        start   <= 1'b1;
        started <= 1'b1;
      end
    end
  end

  demo_dut dut (
    .clk      (clk),
    .rst_n    (dut_rst_n),
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
  assign probe[14]  = scope_primed;
  assign probe[15]  = scope_triggered;

endmodule
