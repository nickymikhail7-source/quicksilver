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

# Common US Tech/Popular Stocks (Manual List for Fuzzy Matching)
US_STOCKS = {
    "APPLE INC": "AAPL",
    "MICROSOFT CORPORATION": "MSFT",
    "AMAZON COM INC": "AMZN",
    "ALPHABET INC": "GOOGL",
    "GOOGLE": "GOOGL",
    "META PLATFORMS INC": "META",
    "FACEBOOK": "META",
    "TESLA INC": "TSLA",
    "NVIDIA CORP": "NVDA",
    "NETFLIX INC": "NFLX",
    "PALANTIR TECHNOLOGIES INC": "PLTR",
    "PALANTIR": "PLTR",
    "ADVANCED MICRO DEVICES": "AMD",
    "INTEL CORP": "INTC",
    "COCA COLA CO": "KO",
    "PEPSICO INC": "PEP",
    "DISNEY WALT CO": "DIS",
    "UBER TECHNOLOGIES INC": "UBER",
    "AIRBNB INC": "ABNB",
    "GAMESTOP CORP": "GME",
    "AMC ENTERTAINMENT": "AMC",
    "ROBINHOOD MARKETS INC": "HOOD",
    "ROBINHOOD": "HOOD",
    "COINBASE GLOBAL INC": "COIN",
    "COINBASE": "COIN",
    "ZOOM VIDEO COMMUNICATIONS": "ZM",
    "ZOOM": "ZM",
    "SHOPIFY INC": "SHOP",
    "SHOPIFY": "SHOP",
    "BLOCK INC": "SQ",
    "SQUARE": "SQ",
    "SPOTIFY TECHNOLOGY": "SPOT",
    "SPOTIFY": "SPOT",
    "SNAP INC": "SNAP",
    "SNAPCHAT": "SNAP",
    "PINTEREST INC": "PINS",
    "PINTEREST": "PINS",
    "ROKU INC": "ROKU",
    "ROKU": "ROKU",
    "DRAFTKINGS INC": "DKNG",
    "DRAFTKINGS": "DKNG"
}

# Common Indian Brand Names vs Listed Names (Manual List)
INDIAN_ALIAS_STOCKS = {
    "GROWW": "GROWW",
    "PAYTM": "PAYTM",
    "ZOMATO": "ZOMATO",
    "NAUKRI": "NAUKRI",
    "POLICYBAZAAR": "POLICYBZR",
    "NYKAA": "NYKAA",
    "DELHIVERY": "DELHIVERY",
    "LENSKART": "LENSKART", # Unlisted but good to handle if it ever lists or for similar names
    "OLA ELECTRIC": "OLAELEC",
    "MAMAARTH": "HONASA",
    "HONASA": "HONASA",
    "URBAN COMPANY": "URBAN",
    "BOAT": "BOAT",
    "SWIGGY": "SWIGGY"
}

def fuzzy_match_company(query):
    """Return the best matching symbol for a company name query.
    Checks US stocks first, then Indian Aliases, then NSE.
    """
    query_upper = query.upper()
    
    # 1. Check US Stocks first (Manual List)
    if query_upper in US_STOCKS:
        return f"{US_STOCKS[query_upper]}:NASDAQ"
        
    # Fuzzy match US stocks
    us_matches = difflib.get_close_matches(query_upper, US_STOCKS.keys(), n=1, cutoff=0.8)
    if us_matches:
        return f"{US_STOCKS[us_matches[0]]}:NASDAQ"

    # 2. Check Indian Aliases
    if query_upper in INDIAN_ALIAS_STOCKS:
        return f"{INDIAN_ALIAS_STOCKS[query_upper]}:NSE"
        
    alias_matches = difflib.get_close_matches(query_upper, INDIAN_ALIAS_STOCKS.keys(), n=1, cutoff=0.8)
    if alias_matches:
        return f"{INDIAN_ALIAS_STOCKS[alias_matches[0]]}:NSE"

    # 3. Check NSE Stocks
    if query_upper in NSE_NAME_TO_SYMBOL:
        return f"{NSE_NAME_TO_SYMBOL[query_upper]}:NSE"
        
    # Difflib match for NSE
    matches = difflib.get_close_matches(query_upper, NSE_NAME_TO_SYMBOL.keys(), n=1, cutoff=0.7)
    if matches:
        return f"{NSE_NAME_TO_SYMBOL[matches[0]]}:NSE"

    # 4. Smart Token Match (NSE)
    stopwords = {'LTD', 'LIMITED', 'PVT', 'PRIVATE', 'INC', 'CORP', 'CORPORATION', 'COMPANY', 'SERVICES', 'FINANCE', 'FINANCIAL', 'TECHNOLOGIES'}
    query_tokens = [t for t in query_upper.split() if t not in stopwords or len(query_upper.split()) == 1]
    
    if not query_tokens:
        query_tokens = query_upper.split()

    best_match = None
    best_score = 0

    for name, sym in NSE_NAME_TO_SYMBOL.items():
        name_tokens = name.split()
        matches_all_tokens = True
        for q_tok in query_tokens:
            if not any(n_tok.startswith(q_tok) for n_tok in name_tokens):
                matches_all_tokens = False
                break
        
        if matches_all_tokens:
            score = 100 - len(name_tokens)
            if score > best_score:
                best_score = score
                best_match = sym
                
    if best_match:
        return f"{best_match}:NSE"
        
    return None

def search_stocks(query):
    """Search for stocks matching the query (for autocomplete)"""
    query_upper = query.upper()
    results = []
    
    # Search US Stocks
    for name, sym in US_STOCKS.items():
        if query_upper in name or query_upper in sym:
            results.append({"symbol": f"{sym}:NASDAQ", "name": name})
            if len(results) >= 3: break
            
    # Search Indian Aliases
    for name, sym in INDIAN_ALIAS_STOCKS.items():
        if query_upper in name or query_upper in sym:
            results.append({"symbol": f"{sym}:NSE", "name": name})
            if len(results) >= 5: break
            
    # Search NSE Stocks
    count = 0
    for name, sym in NSE_NAME_TO_SYMBOL.items():
        if query_upper in name or query_upper in sym:
            results.append({"symbol": f"{sym}:NSE", "name": name})
            count += 1
            if count >= 5: break
            
    return results[:8]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        
        # Check for search mode
        mode = query_components.get('mode', [None])[0]
        if mode == 'search':
            q = query_components.get('q', [''])[0]
            if not q:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps([]).encode('utf-8'))
                return
                
            results = search_stocks(q)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(results).encode('utf-8'))
            return

        symbol = query_components.get('symbol', [None])[0]

        if not symbol:
            self.send_response(400)
            self.end_headers()
            debug_info = {'error': 'Symbol is required', 'received_query': str(query_components), 'path': self.path}
            self.wfile.write(json.dumps(debug_info).encode('utf-8'))
            return

        # Dynamic exchange detection
        if ':' not in symbol:
            # Try fuzzy match first
            fuzzy_sym = fuzzy_match_company(symbol)
            if fuzzy_sym:
                symbol = fuzzy_sym
            else:
                # Fall back to dynamic exchange detection
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
            # Extract Market Cap and P/E Ratio
            mkt_cap = "N/A"
            pe_ratio = "N/A"
            
            # Iterate through stats rows
            # Class 'gyFHrc' is the container for each stat row (Label + Value)
            stats_rows = soup.find_all("div", class_="gyFHrc")
            for row in stats_rows:
                text = row.get_text()
                if "Market cap" in text:
                    val_div = row.find("div", class_="P6K39c")
                    if val_div:
                        mkt_cap = val_div.get_text(strip=True)
                elif "P/E ratio" in text:
                    val_div = row.find("div", class_="P6K39c")
                    if val_div:
                        pe_val = val_div.get_text(strip=True)
                        # If Google returns '-', treat as N/A (common for loss-making companies)
                        if pe_val == '-':
                            pe_ratio = "-" # Keep as dash to indicate no ratio available
                        else:
                            pe_ratio = pe_val

            return {
                "symbol": symbol,
                "name": name,
                "price": price,
                "change": change,
                "isPositive": is_positive,
                "mktCap": mkt_cap,
                "pe": pe_ratio
            }

        except Exception as e:
            # Return None on error
            return None
