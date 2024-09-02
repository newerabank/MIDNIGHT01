import asyncio
import requests
from telegram import Bot
from datetime import datetime, timedelta
import re

# Binance API URL for futures klines data (public API)
base_url = "https://fapi.binance.com"
klines_endpoint = "/fapi/v1/klines"
ticker_24h_endpoint = "/fapi/v1/ticker/24hr"

# Telegram Bot Token
bot_token = "6433482640:AAGo-ewBlLTSgb8vIyeefd4R9SwRE36zyGU"
chat_id = "@VVBRTR34"  # Replace with your channel or chat ID

def fetch_high_volume_pairs(limit=75):
    try:
        response = requests.get(base_url + ticker_24h_endpoint, timeout=10)
        response.raise_for_status()
        tickers = response.json()
        
        usdt_pairs = []
        for ticker in tickers:
            symbol = ticker["symbol"]
            volume = float(ticker["quoteVolume"])
            
            # Include only pairs ending with "USDT"
            if symbol.endswith("USDT"):
                usdt_pairs.append({
                    "symbol": symbol,
                    "volume": volume
                })
        
        # Sort by volume in descending order and select the first 75 pairs
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return usdt_pairs[:limit]
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching data: {e}")
        return []

async def get_kline_data(symbol, interval, limit):
    try:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        response = requests.get(base_url + klines_endpoint, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Timeout occurred while fetching data for {symbol} and {interval}")
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching data for {symbol} and {interval}: {e}")
    return None

async def send_telegram_message(bot, message):
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

def calculate_next_scan_delay():
    now = datetime.now()
    # Calculate the next hour's 2-minute mark
    next_scan_time = now.replace(minute=2, second=0, microsecond=0) + timedelta(hours=1)
    
    # Calculate the delay until the next scan
    delay_seconds = (next_scan_time - now).total_seconds()
    return delay_seconds

async def main():
    bot = Bot(token=bot_token)

    # Fetch high volume USDT pairs and sort them by volume
    symbols_to_monitor = fetch_high_volume_pairs()

    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Get the current date and time
            results = []
            monitored_count = 0
            for pair in symbols_to_monitor:
                symbol = pair["symbol"]
                volume = pair["volume"]

                kline_data = await get_kline_data(symbol, "1h", 2)  # Fetch the last two 1-hour candles
                if kline_data is None or len(kline_data) < 2:
                    continue  # Skip to the next symbol if data fetching failed
                open_price = float(kline_data[0][1])
                close_price = float(kline_data[0][4])
                percentage_change = ((close_price - open_price) / open_price) * 100

                # Determine color, direction, and format the result with +/- sign
                color_emoji = "🔴" if percentage_change < 0 else "🟢"
                direction = "decreased" if percentage_change < 0 else "increased"
                sign = "-" if percentage_change < 0 else "+"

                # Include the first 5 pairs and the rest only if their change is over ±3%
                if monitored_count < 5 or abs(percentage_change) >= 3:
                    results.append(f"| {symbol:<10} | {color_emoji} {sign}{abs(percentage_change):>6.2f}% | {volume:>15,.0f} |")
                    monitored_count += 1

            # Create a table-like message with boundaries
            header = f"| {'Symbol':<10} | {'Change':<8} | {'Volume':>15} |"
            separator = "+" + "-"*12 + "+" + "-"*10 + "+" + "-"*17 + "+"
            table = "\n".join([separator, header, separator] + results + [separator])
            alert_message = (
                f"Hourly Changes and Volumes ({current_time}):\n\n"
                f"{table}"
            )

            # Print the alert to the console (optional)
            print(alert_message)

            # Split the message if it's too long
            max_message_length = 4096
            if len(alert_message) > max_message_length:
                message_parts = [alert_message[i:i+max_message_length] for i in range(0, len(alert_message), max_message_length)]
                for part in message_parts:
                    await send_telegram_message(bot, part)
            else:
                await send_telegram_message(bot, alert_message)

            # Calculate delay until the next hourly scan at :02
            delay_seconds = calculate_next_scan_delay()
            await asyncio.sleep(delay_seconds)

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
