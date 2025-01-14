from bs4 import BeautifulSoup
import requests

def extract_from_mises(url):
    """Extract article title and content from a mises.org webpage"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract title from the specific h1 class
    title = ""
    title_element = soup.find('h1')  # Just find any h1 since we know it works
    if title_element:
        title = title_element.get_text().strip()
        print("Found title:", title)
    
    # Extract article content from the specific div class
    article_content = ""
    
    # Find the main article div
    content_wrapper = soup.find('div', class_=lambda x: x and 'prose' in x and 'max-w-none' in x)
    if content_wrapper:
        # Look for the inner div that contains the actual content
        inner_div = content_wrapper.find('div')
        if inner_div:
            # Get all paragraphs from the inner div
            paragraphs = inner_div.find_all('p')
            # Filter out empty paragraphs and those that only contain links
            valid_paragraphs = []
            for p in paragraphs:
                text = p.get_text().strip()
                # Only include paragraphs that have more than just a link
                if text and not (len(p.find_all('a')) == 1 and len(text) == len(p.find('a').get_text().strip())):
                    valid_paragraphs.append(text)
            
            article_content = ' '.join(valid_paragraphs)
            print("\nFound article content. First 200 chars:")
            print(article_content[:200] + "...")
            print(f"\nTotal paragraphs found: {len(valid_paragraphs)}")
    else:
        print("\nCould not find article content wrapper")
    
    if not article_content and not title:
        raise ValueError("Could not extract article content from the webpage")
            
    return article_content, title

if __name__ == "__main__":
    # Test the extractor
    test_url = input("Enter a mises.org article URL to test: ")
    try:
        text, title = extract_from_mises(test_url)
        print("\nExtracted content:")
        print("-" * 50)
        print("Title:", title)
        print("\nContent preview (first 500 chars):")
        print(text[:500] + "...")
        print("-" * 50)
    except Exception as e:
        print("Error:", str(e)) 