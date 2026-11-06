#This is where main project orchestration will be handled
import argparse
import re 
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import tqdm
"""
# SPASniffer

this project will be a project meant to sniff SPAs (single page applications) for URLs, Fetch structures, HTML injection sinks, and client side input reflection.
"""

def spider(url, scope, depth=3, visited=None, progress=True):
    if visited is None:
        visited = set()
    toscrape = []
    links = set()
    ignore = {"/", "", "#", "#top", "javascript:void(0)"}
    if url in visited or depth < 0:
        return
    visited.add(url)
    initreq = requests.get(url)
    soup = BeautifulSoup(initreq.text, "html.parser")
    
    for tag in soup.find_all(attrs={"href": True}):
        links.add(tag["href"])
    for tag in soup.find_all(attrs={"src": True}):
        links.add(tag["src"])

    
    for link in links:
        link = link.strip()
        if not link or link in ignore or link.startswith("#"):
            continue
        full_url = urljoin(url, link.strip())
        if any(s in full_url for s in scope):
            toscrape.append(full_url)
    
    if depth > 0:
        for link in toscrape:
            spider(link,scope,depth-1,visited)
        
    return visited


  
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
    spscan = spider(args.url,scope)

if  __name__ == "__main__":
     main()

