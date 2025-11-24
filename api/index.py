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
                # Revert to SYMBOL:EXCHANGE format as NASDAQ:SYMBOL redirects to index
                symbol = f"{symbol}:NASDAQ"

        url = f"https://www.google.com/finance/quote/{symbol}"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Class for price: YMlKec (common for both US and India)
            # Find all matches and pick the one with a currency symbol to avoid indices
            price_divs = soup.find_all('div', class_='YMlKec')
            price = "N/A"
            
            for div in price_divs:
                text = div.text.strip()
                # Check for common currency symbols or if it looks like a price (not just a number)
                if '$' in text or '₹' in text or '€' in text or '£' in text:
                    price = text
                    break
            
            # Fallback: if no currency symbol found, take the first one (might be an index, but better than nothing)
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
            
            # We don't need to re-format the price as float because we want to keep the currency symbol
            # Google Finance usually formats it well (e.g. "₹1,234.56")

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
