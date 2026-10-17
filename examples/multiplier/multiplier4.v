module multiplier4 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [7:0] product
);
    assign product = a * b;
endmodule
