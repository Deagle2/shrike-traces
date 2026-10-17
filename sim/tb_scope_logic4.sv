`timescale 1ns/1ps

module tb_scope_logic4;
  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic spi_ss_n = 1'b1;
  logic spi_sck = 1'b0;
  logic spi_mosi = 1'b0;
  wire spi_miso;
  wire spi_miso_en;
  wire clk_en;
  wire LED;
  wire LED_en;

  logic [7:0] response;
  logic [7:0] ignored;
  logic [7:0] low_byte;
  logic [7:0] high_byte;
  logic [15:0] sample;
  logic [15:0] expected;
  integer i;
  integer polls;

  always #5 clk = ~clk;

  ShrikeTracesLogic4 dut (
    .clk         (clk),
    .clk_en      (clk_en),
    .rst_n       (rst_n),
    .spi_ss_n    (spi_ss_n),
    .spi_sck     (spi_sck),
    .spi_mosi    (spi_mosi),
    .spi_miso    (spi_miso),
    .spi_miso_en (spi_miso_en),
    .LED         (LED),
    .LED_en      (LED_en)
  );

  function automatic [15:0] expected_word(
    input logic [3:0] vector,
    input logic       trigger_seen
  );
    logic term_ab;
    logic term_cd;
    logic result_y;
    begin
      term_ab = vector[0] & vector[1];
      term_cd = vector[2] & vector[3];
      result_y = term_ab | term_cd;
      expected_word = 16'h4000 |
                      ({12'h000, vector} << 7) |
                      {9'h000, result_y, term_cd, term_ab, vector};
      if (trigger_seen)
        expected_word = expected_word | 16'h8000;
    end
  endfunction

  task automatic spi_byte(
    input  logic [7:0] tx,
    output logic [7:0] rx
  );
    integer bit_index;
    begin
      rx = 8'h00;
      spi_sck = 1'b0;
      spi_ss_n = 1'b0;
      #200;
      for (bit_index = 7; bit_index >= 0; bit_index = bit_index - 1) begin
        spi_mosi = tx[bit_index];
        #100;
        spi_sck = 1'b1;
        #100;
        rx[bit_index] = spi_miso;
        spi_sck = 1'b0;
      end
      #200;
      spi_ss_n = 1'b1;
      spi_mosi = 1'b0;
      #400;
    end
  endtask

  task automatic request(
    input  logic [7:0] command,
    output logic [7:0] reply
  );
    begin
      spi_byte(command, ignored);
      repeat (8) @(posedge clk);
      spi_byte(8'h00, reply);
      repeat (8) @(posedge clk);
    end
  endtask

  initial begin
    $dumpfile("build/shrike_traces_logic4.vcd");
    $dumpvars(0, tb_scope_logic4);

    repeat (8) @(posedge clk);
    rst_n = 1'b1;
    repeat (8) @(posedge clk);

    request(8'h7e, response);
    if (response !== 8'h53)
      $fatal(1, "device ID expected 53, got %02h", response);

    request(8'h7f, response);
    if (response !== 8'h02)
      $fatal(1, "protocol version expected 02, got %02h", response);

    request(8'h03, response);
    if (response !== 8'ha3)
      $fatal(1, "CLEAR acknowledgement mismatch: %02h", response);

    request(8'h02, response);
    if (response !== 8'ha2)
      $fatal(1, "ARM acknowledgement mismatch: %02h", response);

    polls = 0;
    response = 8'h00;
    while (!response[0] && polls < 80) begin
      request(8'h01, response);
      polls = polls + 1;
    end

    if (!response[0])
      $fatal(1, "capture did not reach DONE; status=%02h", response);
    if (response[3:0] !== 4'b0111)
      $fatal(1, "final status expected x7, got %02h", response);
    if (!LED)
      $fatal(1, "LED did not reflect DONE");

    for (i = 0; i < 16; i = i + 1) begin
      request(8'h10 | i[3:0], low_byte);
      request(8'h20 | i[3:0], high_byte);
      sample = {high_byte, low_byte};
      expected = expected_word((i + 11) & 4'hf, i > 8);

      if (sample !== expected)
        $fatal(1, "logic4 trace[%0d] expected %04h, got %04h", i, expected, sample);
    end

    $display("PASS: logic4 truth table, trigger placement, and SPI trace verified");
    $finish;
  end

endmodule
