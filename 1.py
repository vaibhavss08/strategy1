import asyncio
import numpy as np
import pandas as pd
import ccxt.async_support as ccxt
import logging
import ta
import time
import json
import websockets
from collections import deque, defaultdict
from datetime import datetime

try:
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot_realtime.log'),
        logging.StreamHandler()
    ]
)

class TradingBot:
    def __init__(self):
        self.exchange = None
        self.ws = None
        self.ws_connected = False
        self.last_ws_message = 0
        self.ws_queue = asyncio.Queue(maxsize=1000)  # Buffer for WebSocket messages
        self.price_queue = defaultdict(lambda: deque(maxlen=1800))  # 30 min * 60 sec = 1800 slots
        self.data_1min = defaultdict(lambda: deque(maxlen=200))  # For indicators
        self.data_15min = defaultdict(lambda: deque(maxlen=200))  # For indicators
        self.indicators = defaultdict(dict)
        self.live_prices = {}
        self.positions = {}
        self.capital = 1000  # Starting capital for paper trading
        self.last_trade_time = {}
        self.last_log_time = 0  # Single timestamp for all symbols
        self.pending_updates = defaultdict(dict)  # Buffer updates per symbol
        self.latest_timestamps = defaultdict(int)  # Store latest timestamp per symbol
        self.tasks = []
        self.price_precision = {}
        self.min_position_size = 0.001
        self.active_symbols = []
        self.candle_count = defaultdict(int)
        
        self.LEVERAGE = 10
        self.MAX_POSITIONS = 2
        self.TREND_THRESHOLD = 0.00005
        self.RISK_PER_TRADE = 0.02
        self.VOLUME_THRESHOLD = 30000000
        self.COOLDOWN_SECONDS = 30
        self.MIN_ATR = 0.000005
        self.WS_TIMEOUT = 60
        self.WS_RECONNECT_DELAY = 5
        self.MAX_RECONNECT_ATTEMPTS = 10
        self.LIVE_TRADING = False  # Set to False for paper trading
        self.MAX_STREAMS = 40  # Increased to match all symbols

    async def initialize(self):
        await self.initialize_exchange()
        self.active_symbols = await self.get_futures_symbols(40)  # Limited for performance
        logging.info(f"Loaded symbols: {self.active_symbols}")
        await self.load_initial_data(self.active_symbols)
        
        self.tasks = [
            asyncio.create_task(self.websocket_handler()),
            asyncio.create_task(self.process_ws_queue()),
            asyncio.create_task(self.update_prices()),
            asyncio.create_task(self.log_prices()),
            asyncio.create_task(self.trading_engine()),
            asyncio.create_task(self.connection_monitor())
        ]
        
        await asyncio.gather(*self.tasks)

    async def initialize_exchange(self):
        try:
            self.exchange = ccxt.binanceusdm({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True
                },
                'timeout': 30000
            })
            markets = await self.exchange.load_markets()
            for symbol, market in markets.items():
                self.price_precision[symbol] = market['precision']['price']
            logging.info("Exchange initialized successfully")
        except Exception as e:
            logging.error(f"Exchange init failed: {e}", exc_info=True)
            raise

    async def get_futures_symbols(self, limit=None):
        try:
            markets = await self.exchange.load_markets()
            futures_symbols = [symbol for symbol, market in markets.items() 
                             if market['swap'] and market['quote'] == 'USDT' and market['contract']]
            tickers = await self.exchange.fetch_tickers(futures_symbols)
            high_volume_symbols = [symbol for symbol in futures_symbols 
                                 if symbol in tickers and tickers[symbol].get('quoteVolume', 0) >= self.VOLUME_THRESHOLD]
            if limit:
                high_volume_symbols = sorted(high_volume_symbols, 
                                          key=lambda x: tickers[x]['quoteVolume'], 
                                          reverse=True)[:limit]
            return high_volume_symbols if high_volume_symbols else ['BTC/USDT:USDT', 'ETH/USDT:USDT']
        except Exception as e:
            logging.error(f"Error fetching futures symbols: {e}")
            return ['BTC/USDT:USDT', 'ETH/USDT:USDT']

    async def load_initial_data(self, symbols):
        try:
            if not symbols:
                logging.warning("No symbols provided to load initial data")
                return
            tasks = [self.load_symbol_data(symbol) for symbol in symbols]
            await asyncio.gather(*tasks)
            logging.info(f"Initial data loaded for {len(symbols)} symbols")
        except Exception as e:
            logging.error(f"Error loading initial data: {e}")

    async def load_symbol_data(self, symbol):
        try:
            candles_1m, candles_15m = await asyncio.gather(
                self.exchange.fetch_ohlcv(symbol, '1m', limit=200),
                self.exchange.fetch_ohlcv(symbol, '15m', limit=200)
            )
            self.data_1min[symbol].clear()
            self.data_15min[symbol].clear()
            self.price_queue[symbol].clear()  # Start with empty queue
            for candle in candles_1m:
                self.data_1min[symbol].append({
                    'timestamp': candle[0], 'open': float(candle[1]), 'high': float(candle[2]),
                    'low': float(candle[3]), 'close': float(candle[4]), 'volume': float(candle[5])
                })
            for candle in candles_15m:
                self.data_15min[symbol].append({
                    'timestamp': candle[0], 'open': float(candle[1]), 'high': float(candle[2]),
                    'low': float(candle[3]), 'close': float(candle[4]), 'volume': float(candle[5])
                })
            self.calculate_indicators(symbol)
            self.live_prices[symbol] = float(candles_1m[-1][4])
            self.latest_timestamps[symbol] = candles_1m[-1][0]
        except Exception as e:
            logging.warning(f"Error loading data for {symbol}: {e}")

    def calculate_indicators(self, symbol):
        try:
            df_1min = pd.DataFrame(self.data_1min[symbol])
            df_15min = pd.DataFrame(self.data_15min[symbol])
            if len(df_1min) < 50 or len(df_15min) < 50:
                return
            indicators = {}
            close_1m = df_1min['close']
            indicators['rsi_1m'] = ta.momentum.RSIIndicator(close_1m, window=14).rsi().iloc[-1]
            indicators['ema_50_1m'] = ta.trend.EMAIndicator(close_1m, window=50).ema_indicator().iloc[-1]
            indicators['ema_200_1m'] = ta.trend.EMAIndicator(close_1m, window=200).ema_indicator().iloc[-1]
            atr = ta.volatility.AverageTrueRange(
                df_1min['high'], df_1min['low'], close_1m, window=14
            ).average_true_range().iloc[-1]
            indicators['atr_1m'] = max(atr, self.MIN_ATR)
            close_15m = df_15min['close']
            indicators['rsi_15m'] = ta.momentum.RSIIndicator(close_15m, window=14).rsi().iloc[-1]
            indicators['ema_50_15m'] = ta.trend.EMAIndicator(close_15m, window=50).ema_indicator().iloc[-1]
            indicators['ema_200_15m'] = ta.trend.EMAIndicator(close_15m, window=200).ema_indicator().iloc[-1]
            self.indicators[symbol] = indicators
        except Exception as e:
            logging.warning(f"Error calculating indicators for {symbol}: {e}")

    async def websocket_handler(self):
        reconnect_attempts = 0
        while True:
            try:
                streams = [f"{symbol.split('/')[0].lower().replace('1000', '')}usdt@kline_1m" 
                          for symbol in self.active_symbols[:self.MAX_STREAMS]]
                ws_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
                logging.info(f"Connecting to WebSocket with {len(streams)} streams")
                
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
                    self.ws = websocket
                    self.ws_connected = True
                    self.last_ws_message = time.time()
                    logging.info("WebSocket connected successfully")
                    reconnect_attempts = 0
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=self.WS_TIMEOUT)
                            self.last_ws_message = time.time()
                            await self.ws_queue.put(json.loads(message))  # Queue the message
                        except asyncio.TimeoutError:
                            logging.warning("WebSocket timeout")
                            break
                        except Exception as e:
                            logging.warning(f"WebSocket message error: {e}")
            except Exception as e:
                logging.error(f"WebSocket connection error: {e}")
                self.ws_connected = False
                reconnect_attempts += 1
                if reconnect_attempts > self.MAX_RECONNECT_ATTEMPTS:
                    logging.error("Max reconnect attempts reached. Shutting down.")
                    raise
                await asyncio.sleep(self.WS_RECONNECT_DELAY)

    async def process_ws_queue(self):
        while True:
            try:
                message = await self.ws_queue.get()
                if 'data' not in message or message['data']['e'] != 'kline':
                    continue
                kline = message['data']['k']
                ws_symbol = message['data']['s']
                base = ws_symbol[:-4].upper()
                if base.startswith('1000'):
                    base = '1000' + base[4:]
                symbol = f"{base}/USDT:USDT"
                if symbol not in self.active_symbols:
                    continue
                
                # Buffer latest update
                self.pending_updates[symbol] = {
                    'price': float(kline['c']),
                    'timestamp': kline['t'],
                    'kline': kline
                }
                
                # Process finalized 1m candles for indicators
                if kline['x']:
                    candle = {
                        'timestamp': kline['t'],
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v'])
                    }
                    self.data_1min[symbol].append(candle)
                    self.candle_count[symbol] += 1
                    
                    if self.candle_count[symbol] % 15 == 0:
                        df_1min = pd.DataFrame(self.data_1min[symbol])
                        last_15 = df_1min[-15:] if len(df_1min) >= 15 else df_1min
                        if len(last_15) == 15:
                            self.data_15min[symbol].append({
                                'timestamp': last_15.iloc[0]['timestamp'],
                                'open': last_15.iloc[0]['open'],
                                'high': last_15['high'].max(),
                                'low': last_15['low'].min(),
                                'close': last_15.iloc[-1]['close'],
                                'volume': last_15['volume'].sum()
                            })
                    self.calculate_indicators(symbol)
                
                self.ws_queue.task_done()
            except Exception as e:
                logging.warning(f"Queue processing error: {e}")
            await asyncio.sleep(0)  # Yield control

    async def update_prices(self):
        while True:
            await asyncio.sleep(1)  # Update every second
            current_time = time.time()
            current_ms = int(current_time * 1000)
            for symbol in self.active_symbols:
                if symbol in self.pending_updates:
                    update = self.pending_updates[symbol]
                    price = update['price']
                    timestamp = update['timestamp']
                    del self.pending_updates[symbol]
                else:
                    # Use last known price if no update
                    price = self.live_prices.get(symbol, 0.0)
                    timestamp = self.latest_timestamps[symbol] or current_ms
                
                self.price_queue[symbol].append(price)
                self.live_prices[symbol] = price
                self.latest_timestamps[symbol] = timestamp

    async def log_prices(self):
        while True:
            current_time = time.time()
            if current_time - self.last_log_time >= 60:
                for symbol in self.active_symbols:
                    if symbol in self.live_prices and self.latest_timestamps[symbol]:
                        price = self.live_prices[symbol]
                        timestamp = self.latest_timestamps[symbol]
                        queue_length = len(self.price_queue[symbol])
                        ts_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        logging.info(
                            f"Symbol: {symbol} | Current Price: {price:.6f} | "
                            f"Timestamp: {ts_str} | Queue Length: {queue_length}"
                        )
                self.last_log_time = current_time
            await asyncio.sleep(1)  # Check every second

    async def trading_engine(self):
        while True:
            try:
                if not self.ws_connected:
                    await asyncio.sleep(1)
                    continue
                
                current_time = time.time()
                for symbol in self.active_symbols:
                    if (symbol not in self.live_prices or 
                        symbol not in self.indicators or 
                        len(self.positions) >= self.MAX_POSITIONS or 
                        len(self.price_queue[symbol]) < 1800):  # Ensure queue is full
                        continue
                    
                    price = self.live_prices[symbol]
                    indicators = self.indicators[symbol]
                    position = self.positions.get(symbol)
                    time_since_trade = current_time - self.last_trade_time.get(symbol, 0)
                    
                    if time_since_trade < self.COOLDOWN_SECONDS:
                        continue
                    
                    # Access prices from the queue
                    price_1min_ago = self.price_queue[symbol][1739]  # 1800 - 60 - 1
                    price_15min_ago = self.price_queue[symbol][899]  # 1800 - 900 - 1
                    price_30min_ago = self.price_queue[symbol][0]    # Oldest price
                    
                    trend_up = indicators['ema_50_15m'] > indicators['ema_200_15m']
                    rsi_1m = indicators['rsi_1m']
                    
                    if not position:
                        if (trend_up and rsi_1m < 40 and rsi_1m > 0 and 
                            price > price_1min_ago and price > price_15min_ago and price > price_30min_ago):
                            await self.enter_position(symbol, 'long', price, indicators['atr_1m'])
                            logging.info(f"PAPER LONG {symbol}: {price:.6f} | RSI: {rsi_1m:.1f} | Capital: {self.capital:.2f}")
                        elif (not trend_up and rsi_1m > 60 and rsi_1m < 100 and 
                              price < price_1min_ago and price < price_15min_ago and price < price_30min_ago):
                            await self.enter_position(symbol, 'short', price, indicators['atr_1m'])
                            logging.info(f"PAPER SHORT {symbol}: {price:.6f} | RSI: {rsi_1m:.1f} | Capital: {self.capital:.2f}")
                    elif position:
                        profit = (price - position['entry_price']) / position['entry_price'] * (1 if position['side'] == 'long' else -1)
                        if (profit > 0.005 or 
                            profit < -0.002 or 
                            (position['side'] == 'long' and price <= position['stop_loss']) or 
                            (position['side'] == 'short' and price >= position['stop_loss'])):
                            await self.exit_position(symbol, price)
                            logging.info(f"PAPER EXIT {symbol}: {price:.6f} | Profit: {profit*100:.2f}% | Capital: {self.capital:.2f}")
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.error(f"Trading engine error: {e}")
                await asyncio.sleep(1)

    async def enter_position(self, symbol, side, price, atr):
        risk_amount = self.capital * self.RISK_PER_TRADE
        position_size = min(risk_amount / (2 * atr), self.capital / price)
        position_size = max(position_size, self.min_position_size)
        
        if self.capital < position_size * price * 0.0004:
            return
            
        self.positions[symbol] = {
            'side': side, 
            'entry_price': price, 
            'size': position_size,
            'stop_loss': price - (2 * atr) if side == 'long' else price + (2 * atr),
            'entry_time': time.time()
        }
        self.capital -= position_size * price * 0.0004  # Simulated fees
        self.last_trade_time[symbol] = time.time()

    async def exit_position(self, symbol, price):
        position = self.positions[symbol]
        position_value = position['size'] * position['entry_price']
        current_value = position['size'] * price
        pnl = (current_value - position_value) if position['side'] == 'long' else (position_value - current_value)
        fees = position['size'] * price * 0.0004
        self.capital += position_value + pnl - fees
        del self.positions[symbol]
        self.last_trade_time[symbol] = time.time()

    async def connection_monitor(self):
        while True:
            try:
                if not self.ws_connected or (time.time() - self.last_ws_message > self.WS_TIMEOUT):
                    logging.warning("WebSocket connection issues detected")
                    if self.ws:
                        await self.ws.close()
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Monitor error: {e}")
                await asyncio.sleep(5)

async def main():
    bot = TradingBot()
    try:
        await bot.initialize()
    except (KeyboardInterrupt, Exception) as e:
        logging.error(f"Shutting down: {e}")
        for task in bot.tasks:
            task.cancel()
        if bot.ws:
            await bot.ws.close()
        if bot.exchange:
            await bot.exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
