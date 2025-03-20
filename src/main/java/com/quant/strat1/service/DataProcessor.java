package com.quant.strat1.service;

import com.quant.strat1.connection.ZMQReceiver;
import com.quant.strat1.model.TickData;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
public class DataProcessor {
    private final ZMQReceiver zmqReceiver;
    private final StrategyEngine strategyEngine;

    public DataProcessor(ZMQReceiver zmqReceiver, StrategyEngine strategyEngine) {
        this.zmqReceiver = zmqReceiver;
        this.strategyEngine = strategyEngine;
    }

    @PostConstruct
    public void start() {
        ExecutorService executor = Executors.newSingleThreadExecutor();
        executor.submit(this::process);
    }

    private void process() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                TickData tickData = zmqReceiver.receiveTickData();
                if (tickData != null) {
                    strategyEngine.processTick(tickData);
                }
            } catch (Exception e) {
                System.err.println("Error processing tick data: " + e.getMessage());
            }
        }
    }
}