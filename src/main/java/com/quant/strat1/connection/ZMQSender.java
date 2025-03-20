package com.quant.strat1.connection;

import com.google.gson.Gson;
import com.quant.strat1.model.TradeSignal;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import org.zeromq.ZMQ;

@Component
public class ZMQSender {
    private ZMQ.Socket tradeSocket;
    private final Gson gson = new Gson();

    @PostConstruct
    public void init() {
        ZMQ.Context context = ZMQ.context(1);
        tradeSocket = context.socket(ZMQ.PUSH);
        tradeSocket.bind("tcp://127.0.0.1:5557");
        System.out.println("ZMQSender bound to Python at tcp://127.0.0.1:5557");
    }

    public void sendTradeSignal(TradeSignal signal) {
        String msg = gson.toJson(signal);
        tradeSocket.send(msg.getBytes(ZMQ.CHARSET));
        System.out.println("Sent trade signal: " + msg);
    }
}