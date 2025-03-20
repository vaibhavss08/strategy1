package com.quant.strat1.connection;

import com.google.gson.Gson;
import com.quant.strat1.model.TickData;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.stereotype.Component;
import org.zeromq.ZMQ;

@Component
public class ZMQReceiver {
    private ZMQ.Socket pullSocket;
    private ZMQ.Context context;
    private final Gson gson = new Gson();

    @PostConstruct
    public void init() {
        int retries = 3;
        while (retries > 0) {
            try {
                // Initialize ZeroMQ context and socket
                context = ZMQ.context(1);
                pullSocket = context.socket(ZMQ.PULL);
                pullSocket.connect("tcp://127.0.0.1:5556");
                System.out.println("ZMQReceiver connected to Node.js at tcp://127.0.0.1:5556");
                return;
            } catch (Exception e) {
                System.err.println("Failed to initialize ZMQReceiver: " + e.getMessage());
                retries--;
                if (retries == 0) {
                    throw new RuntimeException("Failed to initialize ZMQReceiver after 3 retries", e);
                }
                try {
                    Thread.sleep(1000); // Wait 1 second before retrying
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException("Interrupted during ZMQReceiver initialization", ie);
                }
            }
        }
    }

    public TickData receiveTickData() {
        if (pullSocket == null) {
            throw new IllegalStateException("ZMQReceiver not initialized; pullSocket is null");
        }
        String msg = pullSocket.recvStr();
        if (msg == null) return null;
        try {
            return gson.fromJson(msg, TickData.class);
        } catch (Exception e) {
            System.err.println("Failed to parse tick data: " + msg + ", error: " + e.getMessage());
            return null;
        }
    }

    @PreDestroy
    public void close() {
        try {
            if (pullSocket != null) {
                pullSocket.close();
                System.out.println("ZMQReceiver pullSocket closed");
            }
            if (context != null) {
                context.term();
                System.out.println("ZMQReceiver context terminated");
            }
        } catch (Exception e) {
            System.err.println("Error closing ZMQReceiver resources: " + e.getMessage());
        }
    }
}