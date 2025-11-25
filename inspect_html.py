from bs4 import BeautifulSoup

with open('/tmp/aapl_finance.html', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find elements containing "Market cap"
for elem in soup.find_all(string="Market cap"):
    parent = elem.parent
    grandparent = parent.parent
    great_grandparent = grandparent.parent
    print(f"Label: {elem}")
    print(f"Great Grandparent: {great_grandparent.name} class={great_grandparent.get('class')}")
    
    # Print all text in the great grandparent to see if value is there
    print(f"Full Text: {great_grandparent.get_text(separator='|', strip=True)}")
    
    # Print children of great grandparent
    for child in great_grandparent.find_all(recursive=False):
        print(f"  Child: {child.name} class={child.get('class')} text={child.get_text(strip=True)}")

print("-" * 20)

# Find elements containing "P/E ratio"
for elem in soup.find_all(string="P/E ratio"):
    parent = elem.parent
    grandparent = parent.parent
    great_grandparent = grandparent.parent
    print(f"Label: {elem}")
    print(f"Full Text: {great_grandparent.get_text(separator='|', strip=True)}")
