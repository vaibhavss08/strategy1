package com.quant.strat1.model;

public class TickData {
    private String stock;
    private double price;
    private double bid;
    private double ask;
    private double volume;
    private long timestamp;

    public String getStock() { return stock; }
    public void setStock(String stock) { this.stock = stock; }
    public double getPrice() { return price; }
    public void setPrice(double price) { this.price = price; }
    public double getBid() { return bid; }
    public void setBid(double bid) { this.bid = bid; }
    public double getAsk() { return ask; }
    public void setAsk(double ask) { this.ask = ask; }
    public double getVolume() { return volume; }
    public void setVolume(double volume) { this.volume = volume; }
    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }
}