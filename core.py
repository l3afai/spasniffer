#This is where main project orchestration will be handled
import argparse
import re 
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

"""
# SPASniffer

this project will be a project meant to sniff SPAs (single page applications) for URLs, Fetch structures, HTML injection sinks, and client side input reflection.
"""



def spider(url, scope, depth=3):
    initreq = requests.get(url)
    soup = BeautifulSoup(initreq.text, "html.parser")
    links = set()
    for tag in soup.find_all(attrs={"href": True}):
        links.add(tag["href"])
    for tag in soup.find_all(attrs={"src": True}):
        links.add(tag["src"])

    toscrape = []
    ignore = {"/", "", "#", "#top", "javascript:void(0)"}
    
    for link in links:
        link = link.strip()
        if not link or link in ignore or link.startswith("#"):
            continue
        full_url = urljoin(url, link.strip())
        if any(s in full_url for s in scope):
            toscrape.append(full_url)
    print(toscrape)
    if depth > 0:
        for link in toscrape:
            spider(link,scope,depth)
        depth -= 1
    return toscrape


  
def parser(url):
    resp = requests.get(url)

def main():
    parser = argparse.ArgumentParser(description='SPASniffer')
    parser.add_argument('--url', type=str, help="URL of the SPA")
    parser.add_argument('--scope',type=str, help="Scope of the SPA in a text file")
    args = parser.parse_args()
    with open(args.scope,"r") as sc:
        scope = sc.read().splitlines()
        sc.close()
    spider(args.url,scope)

if  __name__ == "__main__":
     main()

