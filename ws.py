from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import time
import random
import os
from Am import create_audio
import re

# Scrapper for mises.org
def extract_article(url):
    chrome_options = Options()
    ua = UserAgent()
    chrome_options.add_argument(f'user-agent={ua.random}')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 5))
        
        title = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        ).text
        
        # Remove quotes from the title
        title = title.replace("'", "").replace('"', "")
        
        # Find the first div that contains multiple p elements
        article_wrapper = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[p and p[2]]"))
        )
        paragraphs = article_wrapper.find_elements(By.TAG_NAME, "p")
        article_content = "\n\n".join([p.text for p in paragraphs])
        
        return title, article_content
    
    finally:
        driver.quit()

def save_to_file(title, content, url):
    filename = ''.join(e for e in title if e.isalnum() or e.isspace())
    filename = filename.replace(' ', '_') + '.txt'
    
    if len(filename) > 255:
        filename = filename[:255]
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"URL: {url}\n\n")
        f.write(f"Title: {title}\n\n")
        f.write("Content:\n\n")
        f.write(content)
    
    return filename

# Usage
url = "https://mises.org/mises-wire/president-mckinley-and-meddlers-trap"
title, content = extract_article(url)

# Save the extracted information to a file
filename = save_to_file(title, content, url)

print(f"Article information has been saved to {os.path.abspath(filename)}")

# Create audio file
audio_filename = create_audio(filename, title)
print(f"Audio version has been saved as {os.path.abspath(audio_filename)}")



