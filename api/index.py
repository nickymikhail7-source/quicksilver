from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        symbol = query_components.get('symbol', [None])[0]

        if not symbol:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Symbol is required'}).encode('utf-8'))
            return

        # Dynamic exchange detection - no hardcoding!
        # If user didn't specify exchange (e.g. "AAPL" vs "AAPL:NASDAQ")
        if ':' not in symbol:
            symbol_upper = symbol.upper()
            # Try exchanges in order: NSE -> BSE -> NASDAQ
            result = self.try_exchanges(symbol_upper)
            if result:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Stock {symbol} not found on NSE, BSE, or NASDAQ'}).encode('utf-8'))
        else:
            # User specified exchange explicitly (e.g. "RELIANCE:NSE")
            result = self.fetch_stock_data(symbol)
            if result:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Stock {symbol} not found'}).encode('utf-8'))

    def try_exchanges(self, symbol):
        """Try to find stock on NSE, BSE, then NASDAQ in that order"""
        exchanges = ['NSE', 'BSE', 'NASDAQ']
        for exchange in exchanges:
            full_symbol = f"{symbol}:{exchange}"
            result = self.fetch_stock_data(full_symbol)
            # Valid stock found if:
            # 1. Result exists
            # 2. Price is not N/A
            # 3. Name is not equal to symbol (if name == symbol, stock not found on that exchange)
            if result and result.get('price') != 'N/A' and result.get('name') != full_symbol:
                return result
        return None

    def fetch_stock_data(self, symbol):
        url = f"https://www.google.com/finance/quote/{symbol}"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Class for price: YMlKec (common for both US and India)
            # Find all matches and pick the LAST one with a currency symbol
            # (Indices appear first, actual stock price appears later)
            price_divs = soup.find_all('div', class_='YMlKec')
            price = "N/A"
            price_candidates = []
            
            for div in price_divs:
                text = div.text.strip()
                # Collect all elements with currency symbols
                if '$' in text or '₹' in text or '€' in text or '£' in text:
                    price_candidates.append(text)
            
            # Use the LAST candidate (stock price comes after indices/related stocks)
            if price_candidates:
                if ':NSE' in symbol or ':BSE' in symbol:
                    # For Indian stocks, filter for ₹ only and use FIRST occurrence
                    inr_prices = [p for p in price_candidates if '₹' in p]
                    price = inr_prices[0] if inr_prices else price_candidates[0]
                else:
                    # For US stocks, filter by price range to avoid indices/micro-caps
                    # Major stocks are typically $50-$500
                    valid_prices = []
                    for p in price_candidates:
                        try:
                            # Extract numeric value
                            numeric = p.replace('$', '').replace(',', '').strip()
                            val = float(numeric)
                            # Filter: skip indices (>10k) and micro-caps (<$50)
                            if 50 <= val <= 10000:
                                valid_prices.append(p)
                        except:
                            pass
                    
                    # Use first valid price, or fallback to last candidate
                    price = valid_prices[0] if valid_prices else price_candidates[-1]
            
            # Fallback: if no currency symbol found, take the first one
            if price == "N/A" and price_divs:
                price = price_divs[0].text.strip()
            
            # Class for name: zzDege
            name_div = soup.find('div', class_='zzDege')
            name = name_div.text.strip() if name_div else symbol

            # Class for change: P2Luy Ez2Ioe (positive) or P2Luy Ebnabc (negative)
            change = "0.00%"
            is_positive = True
            
            # Fallback change logic
            change_div = soup.find('div', class_='JwB6zf')
            if change_div:
                change = change_div.text.strip()
                is_positive = '+' in change or 'Up' in str(change_div)
            
            # Return data dict instead of sending response
            return {
                'symbol': symbol,
                'name': name,
                'price': price,
                'change': change,
                'isPositive': is_positive,
                'mktCap': 'N/A',
                'pe': 'N/A'
            }

        except Exception as e:
            # Return None on error
            return None
