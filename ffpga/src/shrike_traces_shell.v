`timescale 1ns/1ps

// Reusable shrike-traces transport and capture shell. A DUT-specific top only
// supplies a 16-bit probe bus and consumes capture state as needed.
module shrike_traces_shell #(
  parameter [15:0] TRIGGER_MASK  = 16'hffff,
  parameter [15:0] TRIGGER_VALUE = 16'h0000,
  parameter integer USE_EXTERNAL_TRIGGER = 0
)(
  input  wire        clk,
  input  wire        rst_n,
  output wire        clk_en,
  input  wire        spi_ss_n,
  input  wire        spi_sck,
  input  wire        spi_mosi,
  output wire        spi_miso,
  output wire        spi_miso_en,
  output wire        led,
  output wire        led_en,
  input  wire [15:0] probe,
  input  wire        trigger_event,
  output wire        clear,
  output wire        capturing,
  output wire        primed,
  output wire        triggered,
  output wire        done
);

  wire [7:0] spi_rx_data;
  wire       spi_rx_valid;
  wire [7:0] spi_tx_data;
  wire       spi_tx_hold;
  wire       arm;
  wire [3:0] trigger_ptr;
  wire [3:0] rd_index;
  wire [15:0] rd_data;

  assign clk_en = 1'b1;
  assign led_en = 1'b1;
  assign led    = done;

  spi_target #(
    .CPOL  (1'b0),
    .CPHA  (1'b0),
    .WIDTH (8),
    .LSB   (1'b0)
  ) spi (
    .i_clk           (clk),
    .i_rst_n         (rst_n),
    .i_enable        (1'b1),
    .i_ss_n          (spi_ss_n),
    .i_sck           (spi_sck),
    .i_mosi          (spi_mosi),
    .o_miso          (spi_miso),
    .o_miso_oe       (spi_miso_en),
    .o_rx_data       (spi_rx_data),
    .o_rx_data_valid (spi_rx_valid),
    .i_tx_data       (spi_tx_data),
    .o_tx_data_hold  (spi_tx_hold)
  );

  scope_spi_regs registers (
    .clk         (clk),
    .rst_n       (rst_n),
    .rx_data     (spi_rx_data),
    .rx_valid    (spi_rx_valid),
    .tx_data     (spi_tx_data),
    .arm_pulse   (arm),
    .clear_pulse (clear),
    .capturing   (capturing),
    .primed      (primed),
    .triggered   (triggered),
    .done        (done),
    .trigger_ptr (trigger_ptr),
    .rd_index    (rd_index),
    .rd_data     (rd_data)
  );

  shrike_traces_core #(
    .PROBE_WIDTH (16),
    .TRACE_DEPTH (16),
    .ADDR_WIDTH  (4),
    .PRE_SAMPLES (8),
    .USE_EXTERNAL_TRIGGER (USE_EXTERNAL_TRIGGER)
  ) scope (
    .clk           (clk),
    .rst_n         (rst_n),
    .arm           (arm),
    .clear         (clear),
    .probe         (probe),
    .trigger_mask  (TRIGGER_MASK),
    .trigger_value (TRIGGER_VALUE),
    .trigger_event (trigger_event),
    .capturing     (capturing),
    .primed        (primed),
    .triggered     (triggered),
    .done          (done),
    .rd_index      (rd_index),
    .rd_data       (rd_data),
    .trigger_ptr   (trigger_ptr)
  );

endmodule
