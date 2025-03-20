package com.quant.strat1.strategy;

import java.util.ArrayDeque;

public class VolatilityTrigger {
    private final ArrayDeque<Double> priceQueue = new ArrayDeque<>(300); // 5 min of 1-second prices
    private final ArrayDeque<Double> rvQueue = new ArrayDeque<>(60);     // 1-min RV
    private final ArrayDeque<Double> rvAvgQueue = new ArrayDeque<>(300); // 5-min RV avg

    public boolean compute(double price) {
        priceQueue.add(price);
        if (priceQueue.size() > 300) priceQueue.removeFirst();

        if (priceQueue.size() < 60) return false;

        double rvT = calculateRV();
        rvQueue.add(rvT);
        if (rvQueue.size() > 60) rvQueue.removeFirst();

        double rvAvg = calculateRVavg();
        rvAvgQueue.add(rvAvg);
        if (rvAvgQueue.size() > 300) rvAvgQueue.removeFirst();

        return rvAvg > 0 && rvT > 3.5 * rvAvg;
    }

    private double calculateRV() {
        Double[] prices = priceQueue.toArray(new Double[0]);
        double rvT = 0.0;
        for (int i = prices.length - 60; i < prices.length - 1; i++) {
            if (prices[i] > 0 && prices[i + 1] > 0) {
                double returnVal = Math.log(prices[i + 1] / prices[i]);
                rvT += returnVal * returnVal;
            }
        }
        return rvT;
    }

    private double calculateRVavg() {
        if (rvQueue.size() < 5) return 0.0;
        Double[] rvs = rvQueue.toArray(new Double[0]);
        double rvAvg = 0.0;
        for (int i = rvs.length - 5; i < rvs.length; i++) {
            rvAvg += rvs[i];
        }
        return rvAvg / 5.0;
    }
}