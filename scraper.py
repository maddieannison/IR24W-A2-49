import re
import hashlib
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from collections import deque, defaultdict
from difflib import SequenceMatcher
from collections import Counter
import validators
from nltk.corpus import stopwords
import nltk
nltk.download('stopwords')

discovered = set() # Stores the links we have found
crawled = set() # Stores the hashes of the links we have crawled
longest_page = 0
longest_page_url = ""
tokens_counter = Counter()
subdomain_counter = {}
ngrams_list = []
stop_words = set(stopwords.words('english'))
last_ten_links = deque(maxlen=10)

def scraper(url, resp):
    links = extract_next_links(url, resp)
    write_report()
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    links = []

    if resp:
            # If we have already found this link, return
            if resp.url in discovered:
                return links
            discovered.add(resp.url)

            if resp.status == 200: # avoid any responses other than valid, including 204 No Content

                # Check for traps
                if check_url_similarity(resp.url):
                    return links
                last_ten_links.append(resp.url)
            
                # Extract information from the web response page
                soup = BeautifulSoup(resp.raw_response.content, 'lxml')
                crawled_content = soup.get_text().lower()

                # Check for exact matches
                hash = compute_hash(crawled_content)
                if hash in crawled:
                    return links
                crawled.add(hash)

                # Check for partial matches
                if check_content_similarity(crawled_content):
                    return links

                # Extract textual information and check textual information content
                text = process_page(crawled_content, resp.url)
                if not text: # process_page() will return None if there is low textual content - do not crawl
                    return links

                # Extract anchor information
                for a_tag in soup.find_all('a'):
                    href = a_tag.get("href")

                    if href is not None:
                        href = href.split('#')[0] # Defragment the URL
                        try:
                            absolute_url = urljoin(url, href) # Transform relative to absolute URL
                        except Exception as e:
                            print(f"An error occurred: {e}. Skipping this link: {absolute_url}.")
                        links.append(absolute_url)
    return links

def is_valid(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False

        # Only crawl urls in the uci ics domain
        if not parsed.hostname:
            return False
        if not re.match(r"(.*\.ics\.uci\.edu|.*\.cs\.uci\.edu|.*\.informatics\.uci\.edu|.*\.stat\.uci\.edu)$", parsed.hostname.lower()):
                return False
        
        # Avoid common traps found during testing
        if ('page' in url) or ('wp-json' in parsed.path) or ('wgEncodeBroad' in parsed.path) or ("action=download" in parsed.query) or ('ical=' in parsed.query) or ('share=' in parsed.query) or ('id=' in parsed.query) or ('rev=' in parsed.query) or ('precision=' in parsed.query) or ("swiki.ics.uci.edu/doku" in url) or ("wiki.ics.uci.edu/doku" in url):
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv|txt|ppsx"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|jpeg)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

# Return true for urls with over 95% similarity ratio
def check_url_similarity(url):
    for link in last_ten_links:
        if SequenceMatcher(None, url, link).ratio() >= 0.95:
            return True
    return False

# Computes hash of page content
def compute_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

# Using ngrams, calculate content similarity and returns true if it is over the threshold of 90%
def check_content_similarity(text):
    global ngrams_list
    this_ngram = compute_ngrams(text, n=3)
    for ngram in ngrams_list:
        similarity = compute_ngram_similarity(this_ngram, ngram)
        if similarity > 0.9:
            return True
    ngrams_list.append(this_ngram)
    return False

# Given a text, compute a list of ngrams of size n
def compute_ngrams(text, n):
    words = text.split()
    ngrams = []
    for i in range(len(words) - n + 1):
        ngram = ' '.join(words[i:i+n])
        ngrams.append(ngram)
    return ngrams

# Compute similarity given two lists of ngrams
def compute_ngram_similarity(ngram1, ngram2): # https://pythonhosted.org/ngram/tutorial.html
    intersection = len(set(ngram1) & set(ngram2))
    union = len(set(ngram1) | set(ngram2))
    similarity = intersection / union if union != 0 else 0
    return similarity

# Processes the text from the web page, including counting tokens and identifying subdomains
def process_page(text, url):
    count_words(text, url)
    tokens = re.findall(r'\b[a-zA-Z0-9]+\b', text) # regex expression for alphanumeric english characters
    if not is_high_quality_page(tokens):
        return None
    update_token_counter(tokens)
    update_subdomain_counter(url)
    return tokens

# Count the number of words on the page, and set longest page
def count_words(text, url):
    global longest_page
    global longest_page_url
    if len(text.split()) > longest_page:
        longest_page = len(text.split())
        longest_page_url = url

# Crawl all pages with high textual information content
# A page is defined (by me) as having high textual information if it contains < 120 words, or < 160 tokens
def is_high_quality_page(tokens):
    if len(tokens) < 160 :
        return False
    return True

# Filter out stop words and add them to the tokens counter
def update_token_counter(tokens):
    filtered_tokens = [token for token in tokens if token.lower() not in stop_words]
    tokens_counter.update(filtered_tokens)

# If the url is a subdomain of ics.uci.edu, update the subdomain counter
def update_subdomain_counter(url):
    if is_subdomain(url):
        subdomain = get_subdomain(url)
        if subdomain in subdomain_counter:
            subdomain_counter[subdomain] += 1
        else:
            subdomain_counter[subdomain] = 1

# Breaks down the url into parts to compare to ics.uci.edu and returns a boolean if it is/isn't a subdomain
def is_subdomain(url):
    parsed_url = urlparse(url)
    parsed_ics = urlparse('https://ics.uci.edu')

    url_domain_parts = parsed_url.netloc.split('.')
    ics_domain_parts = parsed_ics.netloc.split('.')

    # Check if the given URL is longer and ends with the same domain as the ICS URL
    return url_domain_parts[-len(ics_domain_parts):] == ics_domain_parts and len(url_domain_parts) > len(ics_domain_parts)

# Strips the subdomain to return the required format (e.g. http://vision.ics.uci.edu/docs/prev to http://vision.ics.uci.edu)
def get_subdomain(url):
    parsed_url = urlparse(url)
    subdomain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return subdomain

# Write the report to answer questions
def write_report():
    with open("report.txt", "w") as file:
        file.write(f"unique urls: {str(len(crawled))}\n")
        file.write(f"Longest page: {longest_page} words at {longest_page_url}\n")
        file.write("50 most common tokens across all pages (excluding stop words):\n")
        for token, count in tokens_counter.most_common(50):
            file.write(f"{token}: {count}\n")
        file.write("ics.uci.edu subdomains:\n")
        sorted_subdomains = sorted(subdomain_counter.items())
        for subdomain, count in sorted_subdomains:
            file.write(f"{subdomain}: {count}\n")
