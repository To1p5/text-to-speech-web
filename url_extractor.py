from bs4 import BeautifulSoup
import requests

def extract_from_url(url):
    """Extract article content from a webpage"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to find article title
    title = ""
    title_candidates = [
        soup.find('h1', {'class': ['article-title', 'entry-title', 'post-title']}),
        soup.find('meta', {'property': 'og:title'}),
        soup.find('title'),
        soup.find('h1')
    ]
    for candidate in title_candidates:
        if candidate:
            title = candidate.get('content', candidate.text)
            break
    
    # Try to find article content
    article_content = ""
    content_candidates = [
        soup.find('article'),
        soup.find('div', {'class': ['article-content', 'entry-content', 'post-content']}),
        soup.find('main'),
    ]
    
    for candidate in content_candidates:
        if candidate:
            # Remove unwanted elements
            for unwanted in candidate.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
                unwanted.decompose()
            
            # Get paragraphs
            paragraphs = candidate.find_all('p')
            article_content = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
            break
    
    if not article_content and not title:
        raise ValueError("Could not extract article content from the webpage")
        
    return article_content, title

if __name__ == "__main__":
    # Test the extractor
    test_url = input("Enter a URL to test: ")
    try:
        text, title = extract_from_url(test_url)
        print("\nExtracted content:")
        print("-" * 50)
        print("Title:", title)
        print("\nContent preview (first 500 chars):")
        print(text[:500] + "...")
        print("-" * 50)
    except Exception as e:
        print("Error:", str(e)) 