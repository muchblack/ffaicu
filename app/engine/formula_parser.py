"""安全的公式解析器。

支援語法：
  expr     = term (('+' | '-') term)*
  term     = factor (('*' | '/') factor)*
  factor   = NUMBER | IDENT | 'rand' '(' expr ')' | '(' expr ')'

IDENT 會從 variables dict 查值。
rand(N) 回傳 0 到 N-1 的隨機整數。
"""

from __future__ import annotations

import random
import re
from typing import Callable

_TOKEN_RE = re.compile(r"\s*(rand|[a-z][a-z0-9_]*|\d+|[+\-*/()])\s*", re.IGNORECASE)


class FormulaError(Exception):
    pass


def _tokenize(formula: str) -> list[str]:
    tokens = []
    pos = 0
    for m in _TOKEN_RE.finditer(formula):
        if m.start() != pos and formula[pos : m.start()].strip():
            raise FormulaError(f"Unexpected character at position {pos}: {formula[pos:m.start()]}")
        tokens.append(m.group(1))
        pos = m.end()
    if pos != len(formula) and formula[pos:].strip():
        raise FormulaError(f"Unexpected trailing: {formula[pos:]}")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str], variables: dict[str, int], rng: Callable[[int], int]):
        self.tokens = tokens
        self.pos = 0
        self.variables = variables
        self.rng = rng

    def peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected: str | None = None) -> str:
        tok = self.peek()
        if expected is not None and tok != expected:
            raise FormulaError(f"Expected '{expected}', got '{tok}'")
        self.pos += 1
        return tok  # type: ignore[return-value]

    def parse_expr(self) -> int:
        result = self.parse_term()
        while self.peek() in ("+", "-"):
            op = self.consume()
            right = self.parse_term()
            result = result + right if op == "+" else result - right
        return result

    def parse_term(self) -> int:
        result = self.parse_factor()
        while self.peek() in ("*", "/"):
            op = self.consume()
            right = self.parse_factor()
            if op == "*":
                result = result * right
            else:
                result = result // right if right != 0 else 0
        return result

    def parse_factor(self) -> int:
        tok = self.peek()
        if tok is None:
            raise FormulaError("Unexpected end of expression")

        # 數字
        if tok.isdigit():
            self.consume()
            return int(tok)

        # rand(expr)
        if tok.lower() == "rand":
            self.consume()
            self.consume("(")
            n = self.parse_expr()
            self.consume(")")
            return self.rng(n) if n > 0 else 0

        # 括號
        if tok == "(":
            self.consume()
            result = self.parse_expr()
            self.consume(")")
            return result

        # 變數
        if tok[0].isalpha() or tok.startswith("_"):
            self.consume()
            if tok in self.variables:
                return self.variables[tok]
            raise FormulaError(f"Unknown variable: {tok}")

        raise FormulaError(f"Unexpected token: {tok}")


def evaluate(formula: str, variables: dict[str, int], rng: Callable[[int], int] | None = None) -> int:
    """解析並計算公式字串。

    Args:
        formula: 如 "(str + job_level) * rand(50)"
        variables: 變數名到值的映射
        rng: 隨機數產生器，預設 random.randint(0, n-1)
    """
    if rng is None:
        rng = lambda n: random.randint(0, n - 1) if n > 0 else 0

    tokens = _tokenize(formula)
    if not tokens:
        return 0
    parser = _Parser(tokens, variables, rng)
    result = parser.parse_expr()
    if parser.pos < len(parser.tokens):
        raise FormulaError(f"Unexpected token after expression: {parser.peek()}")
    return result
