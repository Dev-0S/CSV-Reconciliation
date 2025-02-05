import csv
import random
import io
import zipfile
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages
import requests
import csv, io
from django.shortcuts import render
from django.http import HttpResponse

def index(request):

    reconciliation_result = None

    if request.method == 'POST':
        internal_file = request.FILES.get('internal_file')
        external_file = request.FILES.get('external_file')
        
        if not internal_file or not external_file:
            messages.error(request, "Both files are required.")
        else:
            try:
                # Dictionaries to store CSV rows keyed by trade_id
                internal_data = {}
                external_data = {}

                # Process the Internal CSV File
                internal_text = internal_file.read().decode('utf-8')
                internal_reader = csv.DictReader(io.StringIO(internal_text))
                for row in internal_reader:
                    trade_id = row.get('trade_id')
                    if trade_id:
                        internal_data[trade_id] = row

                # Process the External CSV File
                external_text = external_file.read().decode('utf-8')
                external_reader = csv.DictReader(io.StringIO(external_text))
                for row in external_reader:
                    trade_id = row.get('trade_id')
                    if trade_id:
                        external_data[trade_id] = row

                # Reconciliation
                reconciled = []           # Trades present in both files
                missing_in_external = []  # Trades in internal only
                missing_in_internal = []  # Trades in external only

                for trade_id, internal_trade in internal_data.items():
                    if trade_id in external_data:
                        external_trade = external_data[trade_id]
                        if internal_trade.get('amount') == external_trade.get('amount'):
                            status = 'Matched'
                        else:
                            status = 'Mismatch'
                        reconciled.append({
                            'trade_id': trade_id,
                            'internal_amount': internal_trade.get('amount'),
                            'external_amount': external_trade.get('amount'),
                            'status': status,
                        })
                    else:
                        missing_in_external.append(internal_trade)

                for trade_id, external_trade in external_data.items():
                    if trade_id not in internal_data:
                        missing_in_internal.append(external_trade)

                reconciliation_result = {
                    'reconciled': reconciled,
                    'missing_in_external': missing_in_external,
                    'missing_in_internal': missing_in_internal,
                }
            except Exception as e:
                messages.error(request, f"Error processing files: {str(e)}")

    return render(request, 'reconciliation/index.html', {'result': reconciliation_result})


def generate_csv_view(request):

    if request.method == 'POST':
        # Get user-provided file names; add .csv if missing.
        internal_filename = request.POST.get('internal_filename', 'internal_trades.csv').strip()
        external_filename = request.POST.get('external_filename', 'external_trades.csv').strip()
        if not internal_filename.endswith('.csv'):
            internal_filename += '.csv'
        if not external_filename.endswith('.csv'):
            external_filename += '.csv'

        # Prepare CSV files in memory.
        internal_buffer = io.StringIO()
        external_buffer = io.StringIO()
        internal_writer = csv.writer(internal_buffer)
        external_writer = csv.writer(external_buffer)

        header = ["trade_id", "amount", "date"]
        internal_writer.writerow(header)
        external_writer.writerow(header)

        def format_date(i):
            day = ((i - 1) % 28) + 1
            return f"2025-01-{day:02d}"

        # Determine random number of errors between 2 and 9.
        total_errors = random.randint(2, 9)
        # One error is the extra trade that is in external but not internal.
        mismatches_count = total_errors - 1
        error_trade_ids = random.sample([f"T{i}" for i in range(1, 101)], mismatches_count)

        # Generate 100 trades.
        for i in range(1, 101):
            trade_id = f"T{i}"
            amount = 1000 + i * 10
            date = format_date(i)

            internal_writer.writerow([trade_id, amount, date])
            if trade_id in error_trade_ids:
                # Mismatch: add an error by increasing the amount by 50.
                external_amount = amount + 50
            else:
                external_amount = amount
            external_writer.writerow([trade_id, external_amount, date])

        # Add an extra trade in the external file.
        extra_trade_id = "T101"
        extra_amount = 1000 + 101 * 10
        extra_date = format_date(101)
        external_writer.writerow([extra_trade_id, extra_amount, extra_date])

        # Get CSV content.
        internal_csv_content = internal_buffer.getvalue()
        external_csv_content = external_buffer.getvalue()

        # Create a ZIP file in memory containing both CSV files.
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(internal_filename, internal_csv_content)
            zip_file.writestr(external_filename, external_csv_content)
        zip_buffer.seek(0)

        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="generated_csv.zip"'
        return response

    else:
        # Render the CSV Generator form.
        return render(request, 'reconciliation/generate_csv.html')
    
import requests
import csv, io
from django.shortcuts import render
from django.http import HttpResponse

def crypto_pnl_view(request):
    """
    This view fetches live crypto data for BTC, ETH, LTC, XRP, and BNB.
    It displays a form for uploading a CSV file of trades.
    Upon upload, it computes the PnL for each trade (and aggregates by symbol)
    and calculates a weighted average entry price for buy trades.
    """
    # Define coins to fetch (CoinGecko uses IDs like "bitcoin", "ethereum", etc.)
    coin_ids = "bitcoin,ethereum,litecoin,ripple,binancecoin"
    api_url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": coin_ids,
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        crypto_data = response.json()
        # Build a dictionary keyed by the uppercase symbol (e.g., "BTC")
        live_prices = {}
        for coin in crypto_data:
            live_prices[coin["symbol"].upper()] = {
                "current_price": coin["current_price"],
                "high_24h": coin.get("high_24h"),
                "low_24h": coin.get("low_24h"),
                "name": coin["name"],
            }
    else:
        live_prices = {}

    pnl_results = {}  # Aggregated PnL per crypto symbol
    trades = []       # List to store processed trade records

    # Dictionaries to accumulate total cost and quantity for "buy" trades (for weighted average entry price)
    entry_prices = {}
    entry_quantities = {}

    # Process CSV file upload if present
    if request.method == "POST" and "trade_file" in request.FILES:
        trade_file = request.FILES["trade_file"]
        decoded_file = trade_file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        # Expected CSV columns: trade_id, symbol, trade_type, quantity, trade_price, trade_date
        for row in reader:
            symbol = row["symbol"].strip().upper()
            trade_type = row.get("trade_type", "buy").strip().lower()  # default to "buy" if not specified
            try:
                quantity = float(row["quantity"])
                trade_price = float(row["trade_price"])
            except ValueError:
                continue  # Skip rows with invalid numeric data

            live_price = live_prices.get(symbol, {}).get("current_price")
            if live_price is None:
                pnl = None
            else:
                # Simple PnL calculation:
                # For buy: (live_price - trade_price) * quantity
                # For sell: (trade_price - live_price) * quantity
                if trade_type == "buy":
                    pnl = (live_price - trade_price) * quantity
                elif trade_type == "sell":
                    pnl = (trade_price - live_price) * quantity
                else:
                    pnl = None
            row["pnl"] = pnl
            trades.append(row)
            if pnl is not None:
                pnl_results[symbol] = pnl_results.get(symbol, 0) + pnl

            # For entry price calculation, we only consider "buy" trades.
            if trade_type == "buy":
                if symbol in entry_prices:
                    entry_prices[symbol] += trade_price * quantity
                    entry_quantities[symbol] += quantity
                else:
                    entry_prices[symbol] = trade_price * quantity
                    entry_quantities[symbol] = quantity

    # Attach PnL and weighted average entry price to each coin in live_prices
    for symbol, coin in live_prices.items():
        coin["pnl"] = pnl_results.get(symbol, 0)  # Default to 0 if no trades exist
        if symbol in entry_prices and entry_quantities[symbol] > 0:
            coin["entry"] = entry_prices[symbol] / entry_quantities[symbol]
        else:
            coin["entry"] = None

    context = {
        "live_prices": live_prices,
        "pnl_results": pnl_results,  # Still available if needed
        "trades": trades,
    }
    return render(request, "reconciliation/crypto_pnl.html", context)

import csv
import io
import random
from datetime import date, timedelta
from django.http import HttpResponse

def generate_dummy_trades_csv(request):
    """
    Generate a CSV file containing dummy trades for a set of cryptocurrencies.
    
    Dummy trade columns:
      - trade_id: A unique trade identifier (e.g., T001, T002, …)
      - symbol: The coin symbol (e.g., BTC, ETH, XRP, BNB, LTC)
      - trade_type: "buy" or "sell" (randomly chosen)
      - quantity: A random float (in units of the coin)
      - trade_price: A random price between the coin's low and high for the day
      - trade_date: A random date within the past 7 days
    """
    # Define our coins with the provided dummy data.
    coins = [
        {"symbol": "BTC", "current_price": 97494, "high": 99019, "low": 96026},
        {"symbol": "ETH", "current_price": 2764.7, "high": 2824.26, "low": 2633.94},
        {"symbol": "XRP", "current_price": 2.42, "high": 2.57, "low": 2.36},
        {"symbol": "BNB", "current_price": 569.01, "high": 578.36, "low": 557.25},
        {"symbol": "LTC", "current_price": 104.31, "high": 108.19, "low": 98.76},
    ]

    # Create an in-memory file to hold the CSV data.
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV header
    writer.writerow(["trade_id", "symbol", "trade_type", "quantity", "trade_price", "trade_date"])

    # Set the number of dummy trades to generate.
    num_trades = 20

    for i in range(1, num_trades + 1):
        # Randomly choose one coin
        coin = random.choice(coins)
        trade_id = f"T{i:03d}"  # e.g., T001, T002, ...
        trade_type = random.choice(["buy", "sell"])
        # Generate a random quantity between 0.1 and 5.0 (you can adjust this range)
        quantity = round(random.uniform(0.1, 5.0), 4)
        # Generate a random trade price between the coin's low and high
        trade_price = round(random.uniform(coin["low"], coin["high"]), 2)
        # Generate a random trade date in the past 7 days.
        days_ago = random.randint(0, 7)
        trade_date = (date.today() - timedelta(days=days_ago)).isoformat()
        
        writer.writerow([trade_id, coin["symbol"], trade_type, quantity, trade_price, trade_date])

    # Prepare the CSV data as a downloadable file.
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dummy_trades.csv"'
    return response