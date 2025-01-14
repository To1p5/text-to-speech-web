from bs4 import BeautifulSoup
import requests

def extract_from_url_fee(url):
    """Extract article title, subtitle, and main content from a Fee.org webpage"""
    # Add headers to mimic a regular browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract title (H1)
    title = ""
    title_element = soup.find('h1')
    if title_element:
        title = title_element.get_text().strip()
        print("Found title:", title)
    
    # Extract subtitle (H2)
    subtitle = ""
    subtitle_element = soup.find('h2')
    if subtitle_element:
        subtitle = subtitle_element.get_text().strip()
        print("Found subtitle:", subtitle)
    
    # Extract article content
    article_content = ""
    content_wrapper = soup.find('div', {'class': 'article-content-wrapper'})
    if content_wrapper:
        paragraphs = content_wrapper.find_all('p')
        article_content = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
        print("Found article content (first 100 chars):", article_content[:100])
    else:
        print("Could not find article-content-wrapper div")
        # Print the HTML structure to debug
        print("\nPage structure:")
        print(soup.prettify()[:1000])
    
    if not article_content and not title:
        raise ValueError("Could not extract article content from the webpage")
    
    # Combine the parts with appropriate spacing
    full_text = f"{title}\n\n{subtitle}\n\n{article_content}"
    return full_text, title

if __name__ == "__main__":
    # Test the extractor
    test_url = input("Enter a Fee.org article URL to test: ")
    try:
        text, title = extract_from_url_fee(test_url)
        print("\nExtracted content:")
        print("-" * 50)
        print(text[:500] + "...")  # Print first 500 characters
        print("-" * 50)
    except Exception as e:
        print("Error:", str(e)) 