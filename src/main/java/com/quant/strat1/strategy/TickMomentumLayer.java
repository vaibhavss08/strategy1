package com.quant.strat1.strategy;

import java.util.ArrayDeque;

public class TickMomentumLayer {
    private final ArrayDeque<Double> tickPriceQueue = new ArrayDeque<>(5); // 5-second prices

    public class TMLResult {
        public boolean up;
        public boolean down;

        TMLResult(boolean up, boolean down) {
            this.up = up;
            this.down = down;
        }
    }

    public TMLResult compute(double price) {
        tickPriceQueue.add(price);
        if (tickPriceQueue.size() > 5) tickPriceQueue.removeFirst();

        if (tickPriceQueue.size() < 5) return new TMLResult(false, false);

        Double[] prices = tickPriceQueue.toArray(new Double[0]);
        double priceChange = (prices[4] - prices[0]) / prices[0] * 100.0;
        return new TMLResult(priceChange > 0.5, priceChange < -0.5);
    }
}