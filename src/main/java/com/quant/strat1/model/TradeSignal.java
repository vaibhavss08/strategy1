package com.quant.strat1.model;

public class TradeSignal {
    private String stock;
    private String signal; // "LONG" or "SHORT"
    private int size;

    public TradeSignal(String stock, String signal, int size) {
        this.stock = stock;
        this.signal = signal;
        this.size = size;
    }

    // Getters
    public String getStock() { return stock; }
    public String getSignal() { return signal; }
    public int getSize() { return size; }
}