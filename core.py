import argparse
import json
import os
import subprocess
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm
import subprocess
from astscan import astscan

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
    try:
        initreq = requests.get(url, timeout=10)
        soup = BeautifulSoup(initreq.text, "html.parser")
    except Exception as e:
        print(f"Couldn't fetch {url},{e}")
        return visited

    for tag in soup.find_all(attrs={"href": True}):
        links.add(tag["href"])
    for tag in soup.find_all(attrs={"src": True}):
        links.add(tag["src"])

    
    for link in links:
        link = link.strip()
        if not link or link in ignore or link.startswith("#"):
            continue
        full_url = urljoin(url, link)
        if any(s in full_url for s in scope):
            toscrape.append(full_url)
    
    if depth > 0:
        for link in tqdm(toscrape, disable=not progress):
            spider(link, scope, depth - 1, visited, progress=False)

    return visited



def jsparser(url):
    try:
        js_code = requests.get(url, timeout=15).content
    except Exception as e:
        print(f"Couldn't fetch {url},{e}")
        return {}

    process = subprocess.Popen(
        ['node', 'parser.js'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    

    stdout, stderr = process.communicate(input=js_code)
    
    if process.returncode != 0:
        print(f"error: {stderr.decode('utf-8', errors='ignore')}")
    try:
        ast_json = json.loads(stdout.decode('utf-8', errors='ignore'))
        return astscan(ast_json)
    except Exception as e:
        print(f"[-] failed to parse AST json for {url}: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description='SPASniffer')
    parser.add_argument('--url', type=str, required=True, help="URL of the SPA")
    parser.add_argument('--scope', type=str, required=True, help="Scope of the SPA in a text file")
    parser.add_argument('--openapi-out', type=str, default=None, help="Output destination for openapi.json")
    args = parser.parse_args()
    merged_openapi = {
        "openapi": "3.0.3",
        "info": {"title": "SPASniffer Discovered API", "version": "1.0.0"},
        "paths": {},
    }

    with open(args.scope,"r") as sc:
        scope = sc.read().splitlines()

    spscan = spider(args.url,scope)
    js_files = [item for item in spscan if item.endswith(".js")]

    for idx, js_file in enumerate(js_files):
        result = jsparser(js_file)

        # write valid formatted JSON result per file
        with open(f"engagement/{idx}-results.json", "w", encoding="utf-8") as file:
            json.dump(result, file, indent=2)
        print(f"[parsed {js_file} at engagement/{idx}-results.json")

        # aggregate discovered routes
        file_paths = result.get("openapi", {}).get("paths", {})
        for path, methods in file_paths.items():
            if path not in merged_openapi["paths"]:
                merged_openapi["paths"][path] = {}
            merged_openapi["paths"][path].update(methods)

    # write openapi spec
    openapi_file = args.openapi_out or "engagement/openapi.json"
    with open(openapi_file, "w", encoding="utf-8") as f:
        json.dump(merged_openapi, f, indent=2)

    total_endpoints = sum(len(m) for m in merged_openapi["paths"].values())
    print(f"Total routes: {len(merged_openapi['paths'])}, Total operations: {total_endpoints}")



    
if  __name__ == "__main__":

    merged_openapi = {
        "openapi": "3.0.3",
        "info": {"title": "SPASniffer Autogenned API Spec", "version": "1.0.0"},
        "paths": {},
    }
