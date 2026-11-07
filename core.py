import argparse
import re 
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm
import subprocess
from astscan import astscan
import os
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
        for link in tqdm(toscrape,):
            spider(link,scope,depth-1,visited)
        
    return visited



def jsparser(url):
   
    js_code = requests.get(url).content
    process = subprocess.Popen(
        ['node', 'parser.js'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    

    stdout, stderr = process.communicate(input=js_code)
    
    if process.returncode != 0:
        print(f"error: {stderr.decode('utf-8', errors='ignore')}")
            
    with open("test.ast", "wb") as file:
        file.write(stdout)
    return astscan("test.ast")

def main():
    parser = argparse.ArgumentParser(description='SPASniffer')
    parser.add_argument('--url', type=str, help="URL of the SPA")
    parser.add_argument('--scope',type=str, help="Scope of the SPA in a text file")
    args = parser.parse_args()
    with open(args.scope,"r") as sc:
        scope = sc.read().splitlines()
        sc.close()
    spscan = spider(args.url,scope)
    js_files = [item for item in spscan if item.endswith(".js")]
    #for now im too lazy to make a proper project management function so its gonna be hardcoded
    os.makedirs("engagement1",exist_ok=True)
    for idx,js_file in enumerate(js_files):
        with open(f"engagement1/{idx}-results.json","w") as file:
            file.write(str(jsparser(js_file)))
        print(f"wrote {idx}")



    
if  __name__ == "__main__":

     main()

