// 8-bit synchronous up/down counter supplied for the user trial.
module up_down_counter (
    input wire clk,
    input wire reset,
    input wire up_down,
    output reg [7:0] count
);
    always @(posedge clk) begin
        if (reset)
            count <= 8'b0;
        else if (up_down)
            count <= count + 1'b1;
        else
            count <= count - 1'b1;
    end
endmodule
