import argparse
import json
import re


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
        return text(n.get("callee")) + "()"
    if t == "BinaryExpression":
        return text(n.get("left")) + " + " + text(n.get("right"))
    return ""


def source(s):
    for pat in ["location.hash", "location.search", "document.URL",
                "document.referrer", ".value", "event.data"]:
        if pat in s:
            return pat
    return None


def astscan(path, scope=[]):
    with open(path) as f:
        ast = json.load(f)

    urls = []
    fetches = []
    sinks = []
    reflects = []

    for n in walk(ast):
        t = n.get("type")

        # url in a string
        if t == "StringLiteral":
            v = str(n.get("value"))
            if re.match(r'^(https?://|//|/)', v):
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
                sinks.append((callee, text(args[0]) if args else "", line(n)))
            if callee == "document.write" or callee == "document.writeln":
                sinks.append((callee, text(args[0]) if args else "", line(n)))


        if t == "AssignmentExpression":
            left = text(n.get("left"))
            if left.endswith(".innerHTML") or left.endswith(".outerHTML"):
                sinks.append((left, text(n.get("right")), line(n)))


        if t in ("MemberExpression", "Identifier"):
            s = source(text(n))
            if s:
                reflects.append((s, text(n), line(n)))

    if scope:
        urls = [u for u in urls if u[0].startswith("/") or any(x in u[0] for x in scope)]

    return {"urls": urls, "fetches": fetches, "sinks": sinks, "reflects": reflects}

