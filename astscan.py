import argparse
import json
import re


#ai-genned chunk
SRC = [r'\blocation\.(hash|search|href|pathname)\b',
       r'\bdocument\.(URL|referrer|cookie)\b',
       r'\bwindow\.name\b',
       r'\b(localStorage|sessionStorage)\.getItem\b',
       r'\b(event|message)\.data\b',
       r'\$routeParams\b']
#end ai-genned chunk

def walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            if "type" in n:
                yield n
            for v in n.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(n, list):
            for i in n:
                stack.append(i)


def line(n):
    return (n.get("loc") or {}).get("start", {}).get("line", 0)


def source(s):
    for p in SRC:
        m = re.search(p, s)
        if m:
            return m.group(0)
    return None

def walkfunc(node, fn=None):
    stack = [(node, fn)]
    while stack:
        n, fn = stack.pop()
        if isinstance(n, dict):
            if n.get("type") in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
                fn = n
            if "type" in n:
                yield n, fn
            for v in n.values():
                if isinstance(v, (dict, list)):
                    stack.append((v, fn))
        elif isinstance(n, list):
            for i in n:
                stack.append((i, fn))

def text(n):
    if not isinstance(n, dict):
        return ""
    t = n.get("type")
    if t == "Identifier":
        return n.get("name", "")
    if t in ("StringLiteral", "DirectiveLiteral"):
        return str(n.get("value", ""))
    if t == "NumericLiteral":
        return str(n.get("value"))
    if t == "ThisExpression":
        return "this"
    if t == "TemplateElement":
        return str((n.get("value") or {}).get("raw", ""))
    if t == "TemplateLiteral":
        return "".join(text(q) for q in n.get("quasis") or [])
    if t == "MemberExpression":
        if n.get("computed"):
            return text(n.get("object")) + "[" + text(n.get("property")) + "]"
        return text(n.get("object")) + "." + text(n.get("property"))
    if t == "CallExpression":
        return text(n.get("callee")) + "(" + ", ".join(text(a) for a in n.get("arguments") or []) + ")"
    if t == "BinaryExpression":
        return text(n.get("left")) + " + " + text(n.get("right"))
    return ""



def memberprop(n):
    if not isinstance(n, dict) or n.get("type") != "MemberExpression":
        return None
    p = n.get("property") or {}
    if p.get("type") == "Identifier":
        return p.get("name")
    if p.get("type") in ("StringLiteral", "NumericLiteral"):
        return str(p.get("value"))
    return None

def astscan(path, scope=[]):
    with open(path) as f:
        ast = json.load(f)
    seen = set()
    urls = []
    fetches = []
    sinks = []
    reflects = []

    for n, fn in walkfunc(ast):
        t = n.get("type")

        # url in a string
        if t == "StringLiteral":
            v = str(n.get("value")).strip()
            if not re.match(r'^(https?://|//|/)', v):
                continue 
            if v in ("/", "//") or ".." in v or re.match(r'^/\(\$?', v):
                continue
            if v not in seen:
                seen.add(v)
                urls.append((v, line(n)))

        if t == "CallExpression":
            callee = text(n.get("callee"))
            args = n.get("arguments") or []

            # fetch structure
            if callee == "fetch":
                fetches.append(("GET", text(args[0]) if args else "", line(n)))
            if callee.endswith(".open") and len(args) > 1:
                fetches.append((text(args[0]), text(args[1]), line(n)))
            if callee.endswith(".html") or callee.endswith(".append"):
                sinks.append((callee, text(args[0]) if args else "", line(n), id(fn)))
            if callee == "document.write" or callee == "document.writeln":
                sinks.append((callee, text(args[0]) if args else "", line(n), id(fn)))


        if t == "AssignmentExpression" and memberprop(n.get("left")) in ("innerHTML", "outerHTML"):
            sinks.append((text(n.get("left")), text(n.get("right")), line(n), id(fn)))


        if t in ("MemberExpression", "Identifier"):
            s = source(text(n))
            if s:
                reflects.append((s, text(n), line(n)))
        taint = {}
    
    for n in walk(ast):
        if n.get("type") == "VariableDeclarator":
            i = n.get("id") or {}
            s = source(text(n.get("init")))
            if i.get("type") == "Identifier" and s:
                taint[i["name"]] = s
    for _ in range(5):
        for n in walk(ast):
            if n.get("type") == "AssignmentExpression":
                l = n.get("left") or {}
                if l.get("type") == "Identifier":
                    for k, s in taint.items():
                        if re.search(r'\b' + k + r'\b', text(n.get("right"))):
                            taint[l["name"]] = s
                            break

    sinkvals = [s[1] for s in sinks]
    reflects = [r for r in reflects if any(r[1] and r[1] in v for v in sinkvals)]
    for s in sinks:
        for k, src in taint.items():
            if re.search(r'\b' + k + r'\b', s[1]):
                reflects.append(("taint:" + src, s[1], s[2]))
    reflects = list(dict.fromkeys(reflects))

    if scope:
        urls = [u for u in urls if u[0].startswith("/") or any(x in u[0] for x in scope)]

    fetches = list(dict.fromkeys(fetches))
    return {"urls": urls, "fetches": fetches, "sinks": [s[:3] for s in sinks], "reflects": reflects, "taint": {k[1]: v for k, v in taint.items()}}
