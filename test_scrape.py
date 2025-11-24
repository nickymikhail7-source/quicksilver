import requests
from bs4 import BeautifulSoup

def test_scrape(symbol):
    url = f"https://www.google.com/finance/quote/{symbol}"
    print(f"Testing {url}...")
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try original selector
        price_div = soup.find('div', class_='YMlKec fxKbKc')
        print(f"Selector 'YMlKec fxKbKc': {price_div.text.strip() if price_div else 'Not Found'}")
        
        # Try relaxed selector
        price_div_relaxed = soup.find('div', class_='YMlKec')
        print(f"Selector 'YMlKec': {price_div_relaxed.text.strip() if price_div_relaxed else 'Not Found'}")
        
        # Try another common one
        price_div_other = soup.find('div', class_='AHmHk')
        print(f"Selector 'AHmHk': {price_div_other.text.strip() if price_div_other else 'Not Found'}")

    except Exception as e:
        print(f"Error: {e}")

test_scrape("AAPL:NASDAQ")
test_scrape("RELIANCE:NSE")
