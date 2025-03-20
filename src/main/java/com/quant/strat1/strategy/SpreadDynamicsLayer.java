package com.quant.strat1.strategy;

import java.util.ArrayDeque;

public class SpreadDynamicsLayer {
    private final ArrayDeque<Double> spreadQueue = new ArrayDeque<>(5); // 5-second spread
    private final ArrayDeque<Double> historicalSpreads = new ArrayDeque<>(25); // For averaging

    public class SDLResult {
        public boolean widening;
        public boolean narrowing;

        SDLResult(boolean widening, boolean narrowing) {
            this.widening = widening;
            this.narrowing = narrowing;
        }
    }

    public SDLResult compute(double bid, double ask) {
        double spread = ask - bid;
        spreadQueue.add(spread);
        if (spreadQueue.size() > 5) spreadQueue.removeFirst();

        historicalSpreads.add(spread);
        if (historicalSpreads.size() > 25) historicalSpreads.removeFirst();

        if (spreadQueue.size() < 5 || historicalSpreads.size() < 25) {
            return new SDLResult(false, false);
        }

        double currentSpread = 0.0;
        for (Double sp : spreadQueue) currentSpread += sp;
        currentSpread /= 5.0;

        double avgSpread = 0.0;
        Double[] spreads = historicalSpreads.toArray(new Double[0]);
        for (int i = spreads.length - 25; i < spreads.length - 5; i += 5) {
            double windowSpread = 0.0;
            for (int j = i; j < i + 5; j++) windowSpread += spreads[j];
            avgSpread += windowSpread / 5.0;
        }
        avgSpread /= 4.0;

        boolean widening = currentSpread > 1.5 * avgSpread;
        boolean narrowing = currentSpread < 0.7 * avgSpread;
        return new SDLResult(widening, narrowing);
    }
}