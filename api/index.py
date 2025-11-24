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

        # Default to NASDAQ if no exchange specified for common tech stocks
        if ':' not in symbol:
            if symbol in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']:
                symbol = f"{symbol}:NSE"
            else:
                symbol = f"{symbol}:NASDAQ"

        url = f"https://www.google.com/finance/quote/{symbol}"
        
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Class for price: YMlKec fxKbKc
            price_div = soup.find('div', class_='YMlKec fxKbKc')
            price = price_div.text.strip().replace('₹', '').replace('$', '').replace(',', '') if price_div else "N/A"
            
            # Class for name: zzDege
            name_div = soup.find('div', class_='zzDege')
            name = name_div.text.strip() if name_div else symbol

            # Class for change: P2Luy Ez2Ioe (positive) or P2Luy Ebnabc (negative) - simplified selector
            # Actually, let's look for the percentage change specifically
            # It's usually in a span/div near the price.
            # Let's try a more robust way: finding the element with aria-label containing "Up" or "Down"
            
            change = "0.00%"
            is_positive = True
            
            # Fallback change logic (simplified for reliability)
            # We can try to find the percentage text directly if we can identify a unique class
            # Based on inspection: "JwB6zf" seems to be the percentage change class often
            change_div = soup.find('div', class_='JwB6zf')
            if change_div:
                change = change_div.text.strip()
                is_positive = '+' in change or 'Up' in str(change_div)
            
            # Clean up price
            try:
                price_float = float(price)
                price = f"{price_float:,.2f}"
            except:
                pass

            data = {
                'symbol': symbol,
                'name': name,
                'price': price,
                'change': change,
                'isPositive': is_positive,
                'mktCap': 'N/A', # Harder to scrape reliably without more complex logic
                'pe': 'N/A'
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
