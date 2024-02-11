import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from collections import deque
from difflib import SequenceMatcher

discovered = set() # Stores the links we have found
crawled = set() # Stores the links we have found AND crawled
last_ten_links = deque(maxlen=10)

def scraper(url, resp):
    links = extract_next_links(url, resp)
    write_report()
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content


    # this function recieves a URL and a web response 
    # parse the web response page
    # extract enough information from the page (for the report)
    # return the scraped URLs
        # only URLs that are within the allowed domain/paths -- use is_valid to verify
        # defragment the URLs
        # can use BeautifulSoup to parse

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

                # Extract textual information and check textual information content
                text = tokenize(soup.get_text().lower())
                if not text: # tokenize() will return None if there is low textual content - do not crawl
                    return links 

                # If the page has already been scraped, return
                if resp.url in crawled:
                    return links

                crawled.add(resp.url)

                # Extract anchor information
                for a_tag in soup.find_all('a'):
                    href = a_tag.get("href")

                    if href is not None:
                        href = href.split('#')[0] # Defragment the URL
                        absolute_url = urljoin(url, href) # Transform relative to absolute URL
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
        if ('page' in url) or ('wp-json' in parsed.path) or ('wgEncodeBroad' in parsed.path) or ("action=download" in parsed.query) or ('ical=' in parsed.query) or ('share=' in parsed.query) or ('id=' in parsed.query) or ('rev=' in parsed.query) or ('precision=' in parsed.query): # or ('stayconnected/stayconnected' in url)
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def tokenize(text):
    tokens = re.findall(r'\b[a-zA-Z0-9]+\b', text) # regex expression for alphanumeric english characters
    if not is_high_quality_page(tokens):
        return None
    return tokens


# Crawl all pages with high textual information content
# A page is defined (by me) as having high textual information if it contains < 120 words, or < 160 tokens
def is_high_quality_page(tokens):
    if len(tokens) < 160 :
        print("LOW QUALITY PAGE")
        return False
    return True

def write_report():
    with open("report.txt", "w") as file:
        file.write("unique urls: " + str(len(crawled)))

# Return true for urls with over 90% similarity ratio
def check_url_similarity(url):
    for link in last_ten_links:
        if SequenceMatcher(None, url, link).ratio() >= 0.95:
            print("SIMILAR LINK DETECTED: ", url, " ", link)
            return True
    return False


        