"""Read and write the Lua data files used by Transport Fever 3.

The game stores user data as Lua source in the form::

    function data()
    return { key = "value", [1] = 2, ... }
    end

Only the data subset is supported: tables, strings, numbers, booleans, nil and
the special numbers the serializer may emit (``math.huge``, ``inf``, ``nan``).
Tables whose keys are exactly ``1..n`` become lists; empty tables become ``[]``;
everything else becomes a dict.
"""

from __future__ import annotations

import math
import re
from typing import Any

__all__ = ["LuaDataError", "loads", "dumps"]


class LuaDataError(ValueError):
    pass


_TOKEN = re.compile(
    r"""
    (?P<ws>\s+|--\[(?P<eq>=*)\[.*?\](?P=eq)\]|--[^\n]*)
  | (?P<long>\[(?P<leq>=*)\[.*?\](?P=leq)\])
  | (?P<str>"(?:[^"\\\n]|\\.|\\\n)*"|'(?:[^'\\\n]|\\.|\\\n)*')
  | (?P<num>0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
  | (?P<op>[{}\[\]=,;()\-])
    """,
    re.VERBOSE | re.DOTALL,
)

_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "\\": "\\", '"': '"', "'": "'", "\n": "\n",
}

_SPECIAL_NAMES = {
    "true": True,
    "false": False,
    "nil": None,
    "math.huge": math.inf,
    "inf": math.inf,
    "nan": math.nan,
}


def _unescape(body: str) -> str:
    """Decode a Lua string literal body. Escapes denote bytes; the game writes UTF-8."""
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out += ch.encode("utf-8")
            i += 1
            continue
        i += 1
        esc = body[i]
        if esc in _ESCAPES:
            out += _ESCAPES[esc].encode("utf-8")
            i += 1
        elif esc.isdigit():
            digits = re.match(r"\d{1,3}", body[i:]).group(0)
            out.append(int(digits))
            i += len(digits)
        elif esc == "x":
            out.append(int(body[i + 1 : i + 3], 16))
            i += 3
        elif esc == "z":
            i += 1
            while i < len(body) and body[i].isspace():
                i += 1
        elif esc == "u":
            end = body.index("}", i)
            out += chr(int(body[i + 2 : end], 16)).encode("utf-8")
            i = end + 1
        else:
            raise LuaDataError(f"invalid escape \\{esc}")
    return out.decode("utf-8", errors="replace")


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                raise LuaDataError(f"unexpected character {text[pos]!r} at offset {pos}")
            pos = m.end()
            kind = m.lastgroup
            if kind == "ws":
                continue
            if kind in ("eq", "leq"):  # inner groups never are lastgroup; defensive
                continue
            self.tokens.append((kind, m.group(kind)))
        self.i = 0

    def peek(self, offset: int = 0) -> tuple[str, str] | None:
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else None

    def next(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise LuaDataError("unexpected end of input")
        self.i += 1
        return tok

    def expect(self, value: str) -> None:
        kind, text = self.next()
        if text != value:
            raise LuaDataError(f"expected {value!r}, got {text!r}")

    def accept(self, value: str) -> bool:
        tok = self.peek()
        if tok is not None and tok[1] == value and tok[0] in ("op", "name"):
            self.i += 1
            return True
        return False

    def document(self) -> Any:
        if self.accept("function"):
            self.expect("data")
            self.expect("(")
            self.expect(")")
            self.expect("return")
            value = self.value()
            self.expect("end")
        elif self.accept("return"):
            value = self.value()
        else:
            value = self.value()
        if self.peek() is not None:
            raise LuaDataError(f"trailing tokens after value: {self.peek()[1]!r}")
        return value

    def value(self) -> Any:
        kind, text = self.next()
        if kind == "str":
            return _unescape(text[1:-1])
        if kind == "long":
            body = text[text.index("[", 1) + 1 : text.rindex("]", 0, len(text) - 1)]
            return body[1:] if body.startswith("\n") else body
        if kind == "num":
            return _number(text)
        if kind == "name":
            if text in _SPECIAL_NAMES:
                return _SPECIAL_NAMES[text]
            raise LuaDataError(f"unsupported identifier {text!r}")
        if text == "-":
            operand = self.value()
            if not isinstance(operand, (int, float)) or isinstance(operand, bool):
                raise LuaDataError("unary minus on non-number")
            return -operand
        if text == "{":
            return self.table()
        if text == "(":
            inner = self.value()
            self.expect(")")
            return inner
        raise LuaDataError(f"unexpected token {text!r}")

    def table(self) -> Any:
        items: dict[Any, Any] = {}
        next_index = 1
        while not self.accept("}"):
            tok = self.peek()
            nxt = self.peek(1)
            if tok and tok[1] == "[" and tok[0] == "op":
                self.next()
                key = self.value()
                self.expect("]")
                self.expect("=")
                items[key] = self.value()
            elif tok and tok[0] == "name" and nxt and nxt[1] == "=" and tok[1] not in _SPECIAL_NAMES:
                self.next()
                self.next()
                items[tok[1]] = self.value()
            else:
                items[next_index] = self.value()
                next_index += 1
            if not (self.accept(",") or self.accept(";")):
                self.expect("}")
                break
        items = {k: v for k, v in items.items() if v is not None}
        if not items:
            return []
        if all(isinstance(k, int) and not isinstance(k, bool) for k in items) and sorted(items) == list(
            range(1, len(items) + 1)
        ):
            return [items[k] for k in range(1, len(items) + 1)]
        return items


def _number(text: str) -> int | float:
    if text.lower().startswith("0x"):
        return int(text, 16)
    if re.fullmatch(r"\d+", text):
        return int(text)
    return float(text)


def loads(text: str) -> Any:
    """Parse a Lua data document (``function data() return ... end``, ``return ...`` or a bare value)."""
    return _Parser(text).document()


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if", "in",
    "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
}


def _dump_value(value: Any, indent: int) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "(0/0)"
        if math.isinf(value):
            return "math.huge" if value > 0 else "-math.huge"
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        return f'"{escaped}"'
    pad = "\t" * (indent + 1)
    if isinstance(value, (list, tuple)):
        if not value:
            return "{ }"
        body = "".join(f"{pad}{_dump_value(v, indent + 1)},\n" for v in value)
        return "{\n" + body + "\t" * indent + "}"
    if isinstance(value, dict):
        if not value:
            return "{ }"
        lines = []
        for key, item in value.items():
            if isinstance(key, str) and _IDENT.fullmatch(key) and key not in _KEYWORDS:
                k = key
            else:
                k = f"[{_dump_value(key, indent + 1)}]"
            lines.append(f"{pad}{k} = {_dump_value(item, indent + 1)},\n")
        return "{\n" + "".join(lines) + "\t" * indent + "}"
    raise TypeError(f"cannot serialize {type(value).__name__} to Lua")


def dumps(value: Any) -> str:
    """Serialize to the game's userdata format (``function data() return ... end``)."""
    return "function data()\nreturn " + _dump_value(value, 0) + "\nend\n"
