package com.quant.strat1.strategy;

import java.util.ArrayDeque;

public class VolumeMomentumLayer {
    private final ArrayDeque<Double> volumeQueue = new ArrayDeque<>(5); // 5-second volume
    private final ArrayDeque<Double> historicalVolumes = new ArrayDeque<>(25); // For averaging

    public boolean compute(double volume) {
        volumeQueue.add(volume);
        if (volumeQueue.size() > 5) volumeQueue.removeFirst();

        historicalVolumes.add(volume);
        if (historicalVolumes.size() > 25) historicalVolumes.removeFirst();

        if (volumeQueue.size() < 5 || historicalVolumes.size() < 25) return false;

        double currentVolume = 0.0;
        for (Double vol : volumeQueue) currentVolume += vol;

        double avgVolume = 0.0;
        Double[] vols = historicalVolumes.toArray(new Double[0]);
        for (int i = vols.length - 25; i < vols.length - 5; i += 5) {
            double windowVol = 0.0;
            for (int j = i; j < i + 5; j++) windowVol += vols[j];
            avgVolume += windowVol;
        }
        avgVolume /= 4.0; // Average of 4 previous 5-second windows

        return currentVolume > 3.0 * avgVolume;
    }
}