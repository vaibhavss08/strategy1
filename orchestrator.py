import zmq
import json
import MetaTrader5 as mt5
import time

# Initialize MT5 connection to Darwinex Zero account
def initialize_mt5():
    if not mt5.initialize():
        print("MT5 initialization failed, error code:", mt5.last_error())
        return False
    print("MT5 initialized successfully")

    # Verify account connection
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to retrieve account info, error code:", mt5.last_error())
        mt5.shutdown()
        return False
    print(f"Connected to account #{account_info.login}, balance: {account_info.balance}")
    return True

# Check margin level
def check_margin_level():
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to retrieve account info for margin check")
        return False

    # Calculate margin level: (Equity / Margin) * 100
    if account_info.margin == 0:  # Avoid division by zero
        print("No margin used, assuming margin level is infinite")
        return True

    margin_level = (account_info.equity / account_info.margin) * 100
    print(f"Current margin level: {margin_level:.2f}%")
    if margin_level < 175:
        print(f"Margin level {margin_level:.2f}% is below 175%, skipping order placement")
        return False
    return True

# Convert units to lots (Darwinex Zero specific)
def units_to_lots(symbol, units):
    # In Darwinex Zero, lot sizes for stocks/CFDs vary; assuming 1 lot = 100 shares
    # 250 units = 2.5 lots, 500 units = 5 lots
    lot_size_per_unit = 0.01  # 1 unit = 0.01 lots (adjust based on symbol)
    lots = units * lot_size_per_unit
    return round(lots, 2)

# Place an order using MT5 API
def place_order(symbol, signal, size):
    # Check margin level before placing the order
    if not check_margin_level():
        return False

    # Map symbol to Darwinex Zero naming (e.g., AAPL might be AAPL.cfd)
    symbol = symbol + ".cfd"  # Adjust based on Darwinex Zero symbol naming
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found")
        return False

    # Ensure symbol is selected in Market Watch
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select {symbol} in Market Watch")
        return False

    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick data for {symbol}")
        return False

    price = tick.ask if signal == "LONG" else tick.bid

    # Calculate stop-loss and take-profit (1% SL, 2% TP)
    sl_multiplier = 0.99 if signal == "LONG" else 1.01
    tp_multiplier = 1.02 if signal == "LONG" else 0.98
    stop_loss = price * sl_multiplier
    take_profit = price * tp_multiplier

    # Convert units to lots
    lots = units_to_lots(symbol, size)

    # Prepare trade request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": mt5.ORDER_TYPE_BUY if signal == "LONG" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "type_time": mt5.ORDER_TIME_GTC,  # Good till canceled
        "type_filling": mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
    }

    # Send trade request
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed for {symbol}, retcode: {result.retcode}, error: {mt5.last_error()}")
        return False
    print(f"Order placed successfully: {symbol}, {signal}, {lots} lots, ticket: {result.order}")
    return True

# Main function
def main():
    # Initialize MT5
    if not initialize_mt5():
        return

    # Connect to ZeroMQ socket for trade signals
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.connect("tcp://127.0.0.1:5557")
    print("Connected to Spring Boot at tcp://127.0.0.1:5557")

    try:
        while True:
            message = socket.recv_string()
            print("Received trade signal:", message)
            trade_signal = json.loads(message)

            stock = trade_signal["stock"]
            signal = trade_signal["signal"]
            size = trade_signal["size"]

            # Place the order
            place_order(stock, signal, size)

    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        mt5.shutdown()
        socket.close()
        context.term()

if __name__ == "__main__":
    main()