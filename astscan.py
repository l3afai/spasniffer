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
    if t == "BooleanLiteral":
        return str(n.get("value")).lower()
    if t == "ThisExpression":
        return "this"
    if t == "TemplateElement":
        return str((n.get("value") or {}).get("raw", ""))
    if t == "TemplateLiteral":
        parts = []
        quasis = n.get("quasis") or []
        exprs = n.get("expressions") or []
        for i, q in enumerate(quasis):
            parts.append(str((q.get("value") or {}).get("raw", "")))
            if i < len(exprs):
                parts.append(f"${{{text(exprs[i])}}}")
        return "".join(parts)
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


def parse_path(n):
    if not isinstance(n, dict):
        return "", []
    t = n.get("type")

    if t == "StringLiteral":
        val = str(n.get("value", "")).strip().split("?")[0]
        return val, []

    if t == "TemplateLiteral":
        parts = []
        params = []
        quasis = n.get("quasis") or []
        exprs = n.get("expressions") or []
        for i, q in enumerate(quasis):
            parts.append(str((q.get("value") or {}).get("raw", "")))
            if i < len(exprs):
                param_name = text(exprs[i]) or f"param{i+1}"
                param_name = re.sub(r'[^a-zA-Z0-9_]', '_', param_name).strip('_') or f"param{i+1}"
                params.append(param_name)
                parts.append(f"{{{param_name}}}")
        full = "".join(parts).split("?")[0]
        return full, params

    return "", []


def infer_schema(n):
    if not isinstance(n, dict):
        return {"type": "string"}
    t = n.get("type")

    if t == "CallExpression":
        callee = text(n.get("callee"))
        args = n.get("arguments") or []
        if callee == "JSON.stringify" and args:
            return infer_schema(args[0])

    if t == "ObjectExpression":
        props = {}
        for p in n.get("properties") or []:
            if p.get("type") in ("ObjectProperty", "Property"):
                k = (p.get("key") or {}).get("name") or str((p.get("key") or {}).get("value", ""))
                if k:
                    props[k] = infer_schema(p.get("value"))
        return {"type": "object", "properties": props}

    if t == "ArrayExpression":
        elements = n.get("elements") or []
        item_schema = infer_schema(elements[0]) if elements else {"type": "string"}
        return {"type": "array", "items": item_schema}

    if t == "NumericLiteral":
        val = n.get("value")
        return {"type": "integer" if isinstance(val, int) else "number"}
    if t == "BooleanLiteral":
        return {"type": "boolean"}
    return {"type": "string"}

#Ai genned part
def parse_http_call(n):
    callee = text(n.get("callee"))
    args = n.get("arguments") or []
    if not args:
        return None

    method = None
    path_node = None
    body_node = None
    opt_node = None

    # fetch(url, [opts])
    if callee == "fetch":
        method = "GET"
        path_node = args[0]
        if len(args) > 1 and args[1].get("type") == "ObjectExpression":
            opt_node = args[1]

    # axios.get/post or custom client calls: api.get(url, ...)
    elif any(callee.endswith(m) for m in (".get", ".delete", ".head", ".options")):
        method = callee.split(".")[-1].upper()
        path_node = args[0]
        if len(args) > 1 and args[1].get("type") == "ObjectExpression":
            opt_node = args[1]

    elif any(callee.endswith(m) for m in (".post", ".put", ".patch")):
        method = callee.split(".")[-1].upper()
        path_node = args[0]
        if len(args) > 1:
            body_node = args[1]
        if len(args) > 2 and args[2].get("type") == "ObjectExpression":
            opt_node = args[2]

    if not method or not path_node:
        return None

    path, path_params = parse_path(path_node)
    if not path or not re.match(r'^(https?://|//|/)', path):
        return None

    query_params = []
    if opt_node:
        for prop in opt_node.get("properties") or []:
            k = (prop.get("key") or {}).get("name") or str((prop.get("key") or {}).get("value", ""))
            v = prop.get("value") or {}
            if k == "method" and v.get("type") == "StringLiteral":
                method = str(v.get("value")).upper()
            elif k == "body":
                body_node = v
            elif k == "params" and v.get("type") == "ObjectExpression":
                for q in v.get("properties") or []:
                    qk = (q.get("key") or {}).get("name") or str((q.get("key") or {}).get("value", ""))
                    if qk:
                        query_params.append(qk)

    return {
        "method": method.lower(),
        "path": path,
        "path_params": path_params,
        "query_params": query_params,
        "body_schema": infer_schema(body_node) if body_node else None,
        "line": line(n),
    }

#End ai genned part

def add_to_openapi(spec, op):
    path = op["path"]
    method = op["method"]
    if path not in spec["paths"]:
        spec["paths"][path] = {}

    params = []
    for p in op["path_params"]:
        params.append({"name": p, "in": "path", "required": True, "schema": {"type": "string"}})
    for q in op["query_params"]:
        params.append({"name": q, "in": "query", "required": False, "schema": {"type": "string"}})

    entry = {
        "summary": f"Discovered {method.upper()} {path}",
        "responses": {"200": {"description": "Discovered from bundle"}},
    }
    if params:
        entry["parameters"] = params

    if op["body_schema"] and method in ("post", "put", "patch"):
        entry["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": op["body_schema"]}},
        }

    spec["paths"][path][method] = entry


def astscan(target, scope=[]):
    # accepts either file path string or pre-parsed dict
    if isinstance(target, dict):
        ast = target
    else:
        with open(target, "r", encoding="utf-8") as f:
            ast = json.load(f)

    seen = set()
    urls = []
    fetches = []
    sinks = []
    reflects = []
    openapi = {
        "openapi": "3.0.3",
        "info": {"title": "SPASniffer Auto-genned API list", "version": "1.0.0"},
        "paths": {},
    }

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
            op = parse_http_call(n)
            if op:
                add_to_openapi(openapi, op)
                fetches.append((op["method"].upper(), op["path"], op["line"]))

            callee = text(n.get("callee"))
            args = n.get("arguments") or []

            # XHR open
            if callee.endswith(".open") and len(args) > 1:
                fetches.append((text(args[0]), text(args[1]), line(n)))
            if callee.endswith(".html") or callee.endswith(".append"):
                sinks.append((callee, text(args[0]) if args else "", line(n), id(fn)))
            if callee in "document.write" or callee in "document.writeln":
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
                        if re.search(r'\b' + re.escape(k) + r'\b', text(n.get("right"))):
                            taint[l["name"]] = s
                            break

    sinkvals = [s[1] for s in sinks]
    reflects = [r for r in reflects if any(r[1] and r[1] in v for v in sinkvals)]
    for s in sinks:
        for k, src in taint.items():
            if re.search(r'\b' + re.escape(k) + r'\b', s[1]):
                reflects.append(("taint:" + src, s[1], s[2]))
    reflects = list(dict.fromkeys(reflects))

    if scope:
        urls = [u for u in urls if u[0].startswith("/") or any(x in u[0] for x in scope)]

    fetches = list(dict.fromkeys(fetches))

    return {
        "urls": urls,
        "fetches": fetches,
        "sinks": [s[:3] for s in sinks],
        "reflects": reflects,
        "taint": taint,
        "openapi": openapi,
    }