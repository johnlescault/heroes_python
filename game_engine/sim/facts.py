"""
Static code analysis of the player's files ("code facts").

Quests use these to check that a concept was really used (e.g. a for-loop),
and the Spellbook panel lists the player's own functions.
"""
import ast
import io
import re
import tokenize

CODE_COMMENT = re.compile(r"^#\s*[A-Za-z_][\w\.]*\s*(\(|=|\+=|-=)")


def analyze(source):
    facts = {
        "parse_ok": True, "comment_lines": 0, "commented_code": 0, "lines": 0,
        "has_for": False, "has_while": False, "has_if": False, "has_elif": False, "has_else": False,
        "uses_and": False, "uses_or": False, "uses_not": False,
        "defs": [], "recursive": [], "uses_return": False, "uses_global": False,
        "constants": {}, "uses_list": False, "uses_index": False, "uses_slice": False,
        "uses_fstring": False, "str_methods": [], "casts": [], "bitwise": [],
        "hex_literals": 0, "bin_literals": 0, "uses_open": False, "uses_print": False,
        "uses_input": False, "operators": [], "uses_append": False, "uses_len": False,
        "uses_range": False, "uses_break": False, "uses_dict": False, "docstrings": 0,
        "calls": [], "nested_loops": False, "uses_bin": False, "uses_hex": False,
        "uses_memory": False,
    }
    facts["lines"] = len([ln for ln in source.splitlines() if ln.strip()])
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                facts["comment_lines"] += 1
                if CODE_COMMENT.match(tok.string):
                    facts["commented_code"] += 1
            elif tok.type == tokenize.NUMBER:
                low = tok.string.lower()
                if low.startswith("0x"):
                    facts["hex_literals"] += 1
                elif low.startswith("0b"):
                    facts["bin_literals"] += 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(source)
    except SyntaxError:
        facts["parse_ok"] = False
        return facts

    ops, casts, methods, bitwise, calls = set(), set(), set(), set(), set()
    module_consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 1:
                    module_consts[t.id] = 0
    loads = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            facts["has_for"] = True
        elif isinstance(node, ast.While):
            facts["has_while"] = True
        elif isinstance(node, ast.If):
            facts["has_if"] = True
            if node.orelse:
                if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                    facts["has_elif"] = True
                else:
                    facts["has_else"] = True
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                facts["uses_and"] = True
            else:
                facts["uses_or"] = True
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                facts["uses_not"] = True
            elif isinstance(node.op, ast.Invert):
                bitwise.add("~")
        elif isinstance(node, ast.BinOp):
            name = type(node.op).__name__
            sym = {"BitAnd": "&", "BitOr": "|", "BitXor": "^", "LShift": "<<", "RShift": ">>"}.get(name)
            if sym:
                bitwise.add(sym)
            else:
                ops.add({"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "//",
                         "Mod": "%", "Pow": "**"}.get(name, name))
        elif isinstance(node, ast.AugAssign):
            name = type(node.op).__name__
            ops.add({"Add": "+=", "Sub": "-=", "Mult": "*="}.get(name, name))
        elif isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node)
            if doc:
                facts["docstrings"] += 1
            facts["defs"].append({"name": node.name, "args": [a.arg for a in node.args.args],
                                  "doc": (doc or "").strip().splitlines()[0][:80] if doc else "",
                                  "line": node.lineno})
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == node.name:
                    facts["recursive"].append(node.name)
                    break
            for sub in ast.walk(node):
                if isinstance(sub, (ast.For, ast.While)) and sub is not node:
                    for inner in ast.walk(sub):
                        if inner is not sub and isinstance(inner, (ast.For, ast.While)):
                            facts["nested_loops"] = True
        elif isinstance(node, ast.Return):
            facts["uses_return"] = True
        elif isinstance(node, ast.Global):
            facts["uses_global"] = True
        elif isinstance(node, (ast.List, ast.ListComp)):
            facts["uses_list"] = True
        elif isinstance(node, (ast.Dict, ast.DictComp)):
            facts["uses_dict"] = True
        elif isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                facts["uses_slice"] = True
            else:
                facts["uses_index"] = True
        elif isinstance(node, ast.JoinedStr):
            facts["uses_fstring"] = True
        elif isinstance(node, ast.Break):
            facts["uses_break"] = True
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loads[node.id] = loads.get(node.id, 0) + 1
            if node.id == "memory":
                facts["uses_memory"] = True
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
                if f.id in ("int", "float", "str", "bool", "round"):
                    casts.add(f.id)
                facts["uses_open"] |= f.id == "open"
                facts["uses_print"] |= f.id == "print"
                facts["uses_input"] |= f.id == "input"
                facts["uses_len"] |= f.id == "len"
                facts["uses_range"] |= f.id == "range"
                facts["uses_bin"] |= f.id == "bin"
                facts["uses_hex"] |= f.id == "hex"
            elif isinstance(f, ast.Attribute):
                methods.add(f.attr)
                calls.add(f.attr)
                facts["uses_append"] |= f.attr == "append"

    for name in module_consts:
        module_consts[name] = loads.get(name, 0)
    facts["constants"] = module_consts
    facts["operators"] = sorted(ops)
    facts["casts"] = sorted(casts)
    facts["str_methods"] = sorted(m for m in methods if m in {
        "upper", "lower", "split", "strip", "replace", "find", "startswith", "endswith",
        "join", "count", "title", "capitalize", "index", "isdigit"})
    facts["bitwise"] = sorted(bitwise)
    facts["calls"] = sorted(calls)
    facts["recursive"] = sorted(set(facts["recursive"]))
    return facts


def merge(*fact_dicts):
    """Combine facts of several files (booleans OR-ed, counts added, lists joined)."""
    out = {}
    for f in fact_dicts:
        for k, v in f.items():
            if k not in out:
                out[k] = v if not isinstance(v, (list, dict)) else (list(v) if isinstance(v, list) else dict(v))
            elif isinstance(v, bool):
                out[k] = out[k] or v
            elif isinstance(v, (int, float)):
                out[k] += v
            elif isinstance(v, list):
                for item in v:
                    if item not in out[k]:
                        out[k].append(item)
            elif isinstance(v, dict):
                out[k].update(v)
    return out
