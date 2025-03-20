package com.quant.strat1.service;

import com.quant.strat1.connection.ZMQSender;
import com.quant.strat1.model.TickData;
import com.quant.strat1.model.TradeSignal;
import com.quant.strat1.strategy.SpreadDynamicsLayer;
import com.quant.strat1.strategy.TickMomentumLayer;
import com.quant.strat1.strategy.VolatilityTrigger;
import com.quant.strat1.strategy.VolumeMomentumLayer;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class StrategyEngine {
    private static final String[] STOCKS = {"AAPL", "MSFT", "AMZN", "TSLA", "NVDA"};
    private final Map<String, VolatilityTrigger> volatilityTriggers = new HashMap<>();
    private final Map<String, VolumeMomentumLayer> volumeMomentumLayers = new HashMap<>();
    private final Map<String, SpreadDynamicsLayer> spreadDynamicsLayers = new HashMap<>();
    private final Map<String, TickMomentumLayer> tickMomentumLayers = new HashMap<>();
    private final ZMQSender zmqSender;

    public StrategyEngine(ZMQSender zmqSender) {
        this.zmqSender = zmqSender;
    }

    @PostConstruct
    public void init() {
        for (String stock : STOCKS) {
            volatilityTriggers.put(stock, new VolatilityTrigger());
            volumeMomentumLayers.put(stock, new VolumeMomentumLayer());
            spreadDynamicsLayers.put(stock, new SpreadDynamicsLayer());
            tickMomentumLayers.put(stock, new TickMomentumLayer());
        }
    }

    public void processTick(TickData tickData) {
        String stock = tickData.getStock();
        VolatilityTrigger vt = volatilityTriggers.get(stock);
        VolumeMomentumLayer vml = volumeMomentumLayers.get(stock);
        SpreadDynamicsLayer sdl = spreadDynamicsLayers.get(stock);
        TickMomentumLayer tml = tickMomentumLayers.get(stock);

        if (vt == null || vml == null || sdl == null || tml == null) {
            System.out.println("Unknown stock: " + stock);
            return;
        }

        // Compute strategy layers
        boolean vtSignal = vt.compute(tickData.getPrice());
        boolean vmlSignal = vml.compute(tickData.getVolume());
        SpreadDynamicsLayer.SDLResult sdlResult = sdl.compute(tickData.getBid(), tickData.getAsk());
        TickMomentumLayer.TMLResult tmlResult = tml.compute(tickData.getPrice());

        // Generate trade signals
        if (vtSignal) {
            if ((vmlSignal || sdlResult.narrowing) && tmlResult.up) {
                // Long Signal
                int size = (vmlSignal && sdlResult.narrowing) ? 500 : 250;
                zmqSender.sendTradeSignal(new TradeSignal(stock, "LONG", size));
            } else if ((vmlSignal || sdlResult.widening) && tmlResult.down) {
                // Short Signal
                int size = (vmlSignal && sdlResult.widening) ? 500 : 250;
                zmqSender.sendTradeSignal(new TradeSignal(stock, "SHORT", size));
            }
        }
    }
}