"""A deliberately bounded Cypher reader. Every token must be understood.

Supports labelled fixed-length patterns, scalar expressions, aggregation, WITH,
OPTIONAL MATCH, ordering and UNION. Graph values may be counted, but never
projected. Unsupported Cypher syntax fails closed before database execution.
"""
from dataclasses import dataclass
import re

from core.graph_schema import QUERY_NODE_SCHEMA, QUERY_RELATIONSHIP_SCHEMA, QUERY_RELATIONSHIP_PATTERNS


@dataclass(frozen=True)
class ValueType:
    kind: str = "scalar"
    label: str = ""


SCALAR = ValueType()
TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*(?:\n|$)|/\*[\s\S]*?\*/)"
    r"|(?P<string>'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
    r"|(?P<parameter>\$[^\W\d]\w*)|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<identifier>[^\W\d]\w*)|(?P<symbol><-|->|<=|>=|<>|!=|=~|[(){}\[\],.:+*/%<>=-])",
    re.UNICODE,
)
FUNCTIONS = {"count", "collect", "sum", "avg", "min", "max", "coalesce", "tolower",
             "toupper", "trim", "ltrim", "rtrim", "tostring", "tointeger", "tofloat",
             "size", "length", "abs", "round", "ceil", "floor", "replace", "substring",
             "split", "head", "last", "reverse", "type"}
PRECEDENCE = {"OR": 1, "XOR": 2, "AND": 3, "=": 4, "<>": 4, "!=": 4, "<": 4,
              ">": 4, "<=": 4, ">=": 4, "IN": 4, "CONTAINS": 4, "STARTS": 4,
              "ENDS": 4, "IS": 4, "=~": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


def validate_chat_cypher(query: str) -> None:
    if len(query) > 20000:
        raise ValueError("Query is too large.")
    tokens = []
    index = 0
    while index < len(query):
        match = TOKEN.match(query, index)
        if match is None:
            raise ValueError(f"Unsupported Cypher syntax at position {index}.")
        if match.lastgroup not in {"space", "comment"}:
            tokens.append((match.lastgroup, match.group()))
        index = match.end()
    if len(tokens) > 2000:
        raise ValueError("Query has too many tokens.")
    try:
        Reader(tokens).query()
    except (RecursionError, IndexError) as exc:
        raise ValueError("Query is incomplete or nested too deeply.") from exc


class Reader:
    def __init__(self, tokens):
        self.tokens = tokens + [("end", "<END>")]
        self.i = 0
        self.variables: dict[str, ValueType] = {}

    def peek(self, offset=0):
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)][1].upper()

    def take(self, value=None):
        if value is not None and self.peek() != value:
            raise ValueError(f"Expected {value}; unsupported Cypher syntax.")
        token = self.tokens[self.i]
        self.i += 1
        return token[1]

    def accept(self, value):
        if self.peek() == value:
            self.take()
            return True
        return False

    def identifier(self):
        if self.tokens[self.i][0] != "identifier":
            raise ValueError("Expected a plain identifier.")
        return self.take()

    def bind(self, name, value):
        if name in self.variables and self.variables[name] != value:
            raise ValueError("Conflicting variable types.")
        self.variables[name] = value

    def query(self):
        columns = self.branch()
        while self.accept("UNION"):
            self.accept("ALL")
            self.variables = {}
            if self.branch() != columns:
                raise ValueError("Cypher UNION branches must return the same column aliases.")
        self.take("<END>")

    def branch(self):
        while True:
            if self.accept("OPTIONAL"):
                self.take("MATCH")
                self.patterns()
            elif self.accept("MATCH"):
                self.patterns()
            elif self.accept("WITH"):
                self.projection(final=False)
            elif self.accept("RETURN"):
                return self.projection(final=True)
            else:
                raise ValueError("Only MATCH, OPTIONAL MATCH, WITH and RETURN are supported.")
            if self.accept("WHERE"):
                self.scalar(self.expression())

    def patterns(self):
        self.pattern()
        while self.accept(","):
            self.pattern()

    def pattern(self):
        left = self.node()
        while self.peek() in {"-", "<-"}:
            reverse = self.take() == "<-"
            self.take("[")
            name = self.identifier() if self.tokens[self.i][0] == "identifier" else ""
            self.take(":")
            relation = self.identifier()
            if relation not in QUERY_RELATIONSHIP_SCHEMA:
                raise ValueError(f"Cypher query uses unknown relationship type: {relation}")
            rel_type = ValueType("relationship", relation)
            if name:
                self.bind(name, rel_type)
            self.properties(rel_type)
            self.take("]")
            self.take("-" if reverse else "->")
            right = self.node()
            source, target = (right, left) if reverse else (left, right)
            if relation != "CONNECTED_TO" and not any(
                p.relationship_type == relation and p.source_label == source.label
                and p.target_label == target.label for p in QUERY_RELATIONSHIP_PATTERNS
            ):
                raise ValueError("Cypher query uses invalid direction or endpoint labels.")
            left = right
        return SCALAR

    def node(self):
        self.take("(")
        name = self.identifier() if self.tokens[self.i][0] == "identifier" else ""
        if self.accept(":"):
            label = self.identifier()
            if label not in QUERY_NODE_SCHEMA:
                raise ValueError(f"Cypher query uses unknown node label: {label}")
            value = ValueType("node", label)
            if name:
                self.bind(name, value)
        elif name and name in self.variables and self.variables[name].kind == "node":
            value = self.variables[name]
        else:
            raise ValueError("Every new node must have an explicit allowed label.")
        self.properties(value)
        self.take(")")
        return value

    def properties(self, value):
        if not self.accept("{"):
            return
        if self.accept("}"):
            return
        while True:
            self.property(value, self.identifier())
            self.take(":")
            self.scalar(self.expression())
            if not self.accept(","):
                break
        self.take("}")

    def property(self, value, name):
        schema = QUERY_NODE_SCHEMA if value.kind == "node" else QUERY_RELATIONSHIP_SCHEMA
        if value.kind not in {"node", "relationship"} or name not in schema.get(value.label, ()):
            raise ValueError(f"Cypher query uses unknown property: {name}")
        return SCALAR

    def projection(self, *, final):
        self.accept("DISTINCT")
        projected = {}
        columns = []
        while True:
            start = self.i
            value = self.expression()
            expression_tokens = self.tokens[start:self.i]
            if final:
                self.scalar(value)
            if self.accept("AS"):
                name = self.identifier()
            elif len(expression_tokens) == 1 and expression_tokens[0][0] == "identifier":
                name = expression_tokens[0][1]
            elif final:
                name = "".join(t[1] for t in expression_tokens)
            else:
                raise ValueError("WITH expressions require an alias.")
            if name in projected:
                raise ValueError("Duplicate projection alias.")
            projected[name] = value
            columns.append(name)
            if not self.accept(","):
                break
        old_variables = self.variables
        self.variables = {**old_variables, **projected} if final else projected
        if self.accept("ORDER"):
            self.take("BY")
            while True:
                self.scalar(self.expression())
                if not self.accept("ASC"):
                    self.accept("DESC")
                if not self.accept(","):
                    break
        for clause in ("SKIP", "LIMIT"):
            if self.accept(clause):
                if self.tokens[self.i][0] not in {"number", "parameter"}:
                    raise ValueError(f"{clause} requires a literal or parameter.")
                self.take()
        return columns

    def scalar(self, value):
        if value.kind != "scalar":
            raise ValueError("Whole graph values and property maps cannot be returned or transformed.")

    def expression(self, minimum=0):
        if self.accept("NOT"):
            self.scalar(self.expression(4))
            left = SCALAR
        elif self.peek() in {"+", "-"}:
            self.take()
            self.scalar(self.expression(7))
            left = SCALAR
        else:
            left = self.atom()
        while self.peek() in PRECEDENCE and PRECEDENCE[self.peek()] >= minimum:
            operator = self.take().upper()
            if operator == "IS":
                self.accept("NOT")
                self.take("NULL")
            else:
                self.scalar(left)
                if operator in {"STARTS", "ENDS"}:
                    self.take("WITH")
                self.scalar(self.expression(PRECEDENCE[operator] + 1))
            left = SCALAR
        return left

    def atom(self):
        kind, text = self.tokens[self.i]
        if kind in {"string", "number", "parameter"} or self.peek() in {"NULL", "TRUE", "FALSE"}:
            self.take()
            return SCALAR
        if self.accept("["):
            if not self.accept("]"):
                self.scalar(self.expression())
                while self.accept(","):
                    self.scalar(self.expression())
                self.take("]")
            return SCALAR
        if self.peek() == "(":
            # A label or a relationship after the first balanced node marks a pattern predicate.
            depth, end = 0, self.i
            for end in range(self.i, len(self.tokens)):
                if self.tokens[end][1] == "(": depth += 1
                if self.tokens[end][1] == ")": depth -= 1
                if depth == 0: break
            if end + 1 < len(self.tokens) and self.tokens[end + 1][1] in {"-", "<-"}:
                return self.pattern()
            self.take("(")
            value = self.expression()
            self.take(")")
            return value
        if self.accept("CASE"):
            if self.peek() != "WHEN":
                self.scalar(self.expression())
            if self.peek() != "WHEN":
                raise ValueError("CASE requires WHEN.")
            while self.accept("WHEN"):
                self.scalar(self.expression())
                self.take("THEN")
                self.scalar(self.expression())
            if self.accept("ELSE"):
                self.scalar(self.expression())
            self.take("END")
            return SCALAR
        name = self.identifier()
        if self.accept("("):
            function = name.lower()
            if function not in FUNCTIONS:
                raise ValueError(f"Unsupported function: {name}")
            self.accept("DISTINCT")
            args = []
            if self.accept("*"):
                if function != "count":
                    raise ValueError("Only count(*) is supported.")
            elif self.peek() != ")":
                args.append(self.expression())
                while self.accept(","):
                    args.append(self.expression())
            self.take(")")
            if function == "type":
                if len(args) != 1 or args[0].kind != "relationship":
                    raise ValueError("type() requires a bound relationship.")
            elif function != "count":
                for arg in args:
                    self.scalar(arg)
            return SCALAR
        if name not in self.variables:
            raise ValueError(f"Unknown variable: {name}")
        value = self.variables[name]
        if self.accept("."):
            return self.property(value, self.identifier())
        return value
