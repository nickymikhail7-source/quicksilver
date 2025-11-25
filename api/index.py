import csv
import io
import difflib
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests
from bs4 import BeautifulSoup

# Load NSE/BSE stock list (symbol -> company name) once at module load time
def load_nse_stock_list():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        # CSV is encoded in ISO-8859-1
        text = resp.content.decode('ISO-8859-1')
        reader = csv.DictReader(io.StringIO(text))
        symbol_to_name = {}
        name_to_symbol = {}
        for row in reader:
            sym = row.get('SYMBOL')
            name = row.get('NAME OF COMPANY')
            if sym and name:
                symbol_to_name[sym.upper()] = name
                name_to_symbol[name.upper()] = sym.upper()
        return symbol_to_name, name_to_symbol
    except Exception as e:
        # If download fails, return empty dicts – fallback to existing logic
        return {}, {}

# Global stock dictionaries
NSE_SYMBOL_TO_NAME, NSE_NAME_TO_SYMBOL = load_nse_stock_list()

def fuzzy_match_company(query):
    """Return the best matching NSE symbol for a company name query.
    1. Exact match
    2. Difflib close match
    3. Smart token match (handles 'Jio Finance' -> 'Jio Financial Services')
    """
    query_upper = query.upper()
    
    # 1. Direct lookup
    if query_upper in NSE_NAME_TO_SYMBOL:
        return NSE_NAME_TO_SYMBOL[query_upper]
        
    # 2. Difflib match (good for typos)
    matches = difflib.get_close_matches(query_upper, NSE_NAME_TO_SYMBOL.keys(), n=1, cutoff=0.7)
    if matches:
        return NSE_NAME_TO_SYMBOL[matches[0]]

    # 3. Smart Token Match
    # Normalize query: remove common noise words if they aren't the only words
    stopwords = {'LTD', 'LIMITED', 'PVT', 'PRIVATE', 'INC', 'CORP', 'CORPORATION', 'COMPANY', 'SERVICES', 'FINANCE', 'FINANCIAL'}
    query_tokens = [t for t in query_upper.split() if t not in stopwords or len(query_upper.split()) == 1]
    
    if not query_tokens:
        query_tokens = query_upper.split() # Revert if we stripped everything

    best_match = None
    best_score = 0

    for name, sym in NSE_NAME_TO_SYMBOL.items():
        name_tokens = name.split()
        
        # Check if all query tokens match a prefix of a word in the company name
        # e.g. "JIO" matches "JIO", "FIN" matches "FINANCIAL"
        matches_all_tokens = True
        for q_tok in query_tokens:
            if not any(n_tok.startswith(q_tok) for n_tok in name_tokens):
                matches_all_tokens = False
                break
        
        if matches_all_tokens:
            # Prefer shorter names (closer match) to avoid matching "Jio" to "Jio Something Else Very Long"
            # Score = inverse of name length
            score = 100 - len(name_tokens)
            if score > best_score:
                best_score = score
                best_match = sym
                
    return best_match



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
        # Resolve symbol: if user didn't specify exchange, try fuzzy match first (company name)
        if ':' not in symbol:
            # Try fuzzy match against NSE company names
            fuzzy_sym = fuzzy_match_company(symbol)
            if fuzzy_sym:
                symbol = f"{fuzzy_sym}:NSE"
            else:
                # Fall back to dynamic exchange detection (NSE/BSE/NASDAQ)
                result = self.try_exchanges(symbol.upper())
                if result:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode('utf-8'))
                    return
                else:
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': f'Stock {symbol} not found'}).encode('utf-8'))
                    return
        # If symbol already includes exchange, just fetch data
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
            return

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
