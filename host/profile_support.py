"""Validated, data-only signal profiles for shrike-traces captures."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ProfileError(ValueError):
    """Raised when a shrike-traces profile is invalid."""


def _profile_path(profile: str | Path) -> Path:
    candidate = Path(profile)
    if candidate.suffix.lower() == ".json" or candidate.parent != Path("."):
        return candidate.expanduser().resolve()
    return (PROFILES_DIR / f"{candidate.name}.json").resolve()


def load_profile(profile: str | Path) -> dict[str, Any]:
    path = _profile_path(profile)
    if not path.is_file():
        raise ProfileError(f"profile not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    validate_profile(data)
    data["_path"] = path
    return data


def list_profiles() -> list[dict[str, Any]]:
    return [load_profile(path) for path in sorted(PROFILES_DIR.glob("*.json"))]


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != 1:
        raise ProfileError("schema_version must be 1")
    for field in ("id", "description", "top_module", "bitstream", "signals"):
        if field not in profile:
            raise ProfileError(f"missing required field: {field}")
    if not NAME_PATTERN.fullmatch(profile["id"]):
        raise ProfileError("profile id must be an identifier")
    if not NAME_PATTERN.fullmatch(profile["top_module"]):
        raise ProfileError("top_module must be a Verilog identifier")

    sample_count = profile.get("sample_count", 16)
    trigger_index = profile.get("trigger_index", 8)
    if not isinstance(sample_count, int) or not 1 <= sample_count <= 16:
        raise ProfileError("sample_count must be between 1 and 16")
    if not isinstance(trigger_index, int) or not 0 <= trigger_index < sample_count:
        raise ProfileError("trigger_index must select a stored sample")

    names: set[str] = set()
    for signal in profile["signals"]:
        _validate_name(signal, names, "signal")
        lsb = signal.get("lsb")
        width = signal.get("width")
        if not isinstance(lsb, int) or not isinstance(width, int):
            raise ProfileError(f"{signal['name']}: lsb and width must be integers")
        if lsb < 0 or width < 1 or lsb + width > 16:
            raise ProfileError(f"{signal['name']}: bit range must fit the 16-bit probe")
        if signal.get("radix", "unsigned") not in {"unsigned", "binary", "hex"}:
            raise ProfileError(f"{signal['name']}: unsupported radix")

    for assertion in profile.get("assertions", []):
        _validate_name(assertion, names, "assertion")
        expression = assertion.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ProfileError(f"{assertion['name']}: expression is required")
        tree = ast.parse(expression, mode="eval")
        referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        missing = referenced - names
        missing -= {"index", "word", "trigger"}
        if missing:
            raise ProfileError(
                f"{assertion['name']}: unknown names: {', '.join(sorted(missing))}"
            )
        validation_values = {name: 0 for name in names}
        validation_values.update({"index": 0, "word": 0, "trigger": 0})
        _evaluate_expression(tree, validation_values)

    expected_words = profile.get("expected_words")
    if expected_words is not None:
        if not isinstance(expected_words, list) or len(expected_words) != sample_count:
            raise ProfileError("expected_words must contain one word per sample")
        for index, value in enumerate(expected_words):
            _parse_word(value, f"expected_words[{index}]")
        _parse_word(profile.get("expected_word_mask", 0xFFFF), "expected_word_mask")

    bitstream = (PROJECT_ROOT / profile["bitstream"]).resolve()
    try:
        bitstream.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ProfileError("bitstream must remain inside the project") from exc


def _validate_name(item: dict[str, Any], names: set[str], kind: str) -> None:
    name = item.get("name")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise ProfileError(f"invalid {kind} name: {name!r}")
    if name in names or name in {"index", "word", "trigger", "expected_word_ok"}:
        raise ProfileError(f"duplicate or reserved name: {name}")
    names.add(name)


def decode_word(profile: dict[str, Any], index: int, word: int) -> dict[str, int]:
    row: dict[str, int] = {"index": index, "word": word}
    for signal in profile["signals"]:
        mask = (1 << signal["width"]) - 1
        row[signal["name"]] = (word >> signal["lsb"]) & mask
    row["trigger"] = int(index == profile.get("trigger_index", 8))
    if "expected_words" in profile:
        expected = _parse_word(profile["expected_words"][index], f"expected_words[{index}]")
        mask = _parse_word(profile.get("expected_word_mask", 0xFFFF), "expected_word_mask")
        row["expected_word_ok"] = int((word & mask) == (expected & mask))
    for assertion in profile.get("assertions", []):
        tree = ast.parse(assertion["expression"], mode="eval")
        row[assertion["name"]] = int(bool(_evaluate_expression(tree, row)))
    return row


def vcd_signals(profile: dict[str, Any]) -> list[tuple[str, int]]:
    result = [(item["name"], item["width"]) for item in profile["signals"]]
    result.append(("trigger", 1))
    if "expected_words" in profile:
        result.append(("expected_word_ok", 1))
    result.extend((item["name"], 1) for item in profile.get("assertions", []))
    if len(result) > 90:
        raise ProfileError("too many VCD signals")
    return result


def assertion_failures(
    profile: dict[str, Any], rows: list[dict[str, int]]
) -> list[tuple[int, str, int, int]]:
    failures: list[tuple[int, str, int, int]] = []
    for row in rows:
        if "expected_words" in profile and row["expected_word_ok"] != 1:
            failures.append((row["index"], "expected_word_ok", row["expected_word_ok"], 1))
        for assertion in profile.get("assertions", []):
            expected = int(assertion.get("expect", 1))
            actual = row[assertion["name"]]
            if actual != expected:
                failures.append((row["index"], assertion["name"], actual, expected))
    return failures


def _parse_word(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ProfileError(f"{field} must be a 16-bit integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value, 0)
        except ValueError as exc:
            raise ProfileError(f"{field} is not an integer") from exc
    else:
        raise ProfileError(f"{field} must be an integer or base-prefixed string")
    if not 0 <= parsed <= 0xFFFF:
        raise ProfileError(f"{field} must fit 16 bits")
    return parsed


def _evaluate_expression(tree: ast.AST, values: dict[str, int]) -> int | bool:
    node = tree.body if isinstance(tree, ast.Expression) else tree
    if isinstance(node, ast.Constant) and isinstance(node.value, (bool, int)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise ProfileError(f"unknown expression name: {node.id}")
        return values[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
        left = int(_evaluate_expression(node.left, values))
        right = int(_evaluate_expression(node.right, values))
        if isinstance(node.op, ast.BitAnd):
            return left & right
        if isinstance(node.op, ast.BitOr):
            return left | right
        return left ^ right
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        results = [bool(_evaluate_expression(value, values)) for value in node.values]
        return all(results) if isinstance(node.op, ast.And) else any(results)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.Invert)):
        value = _evaluate_expression(node.operand, values)
        return not bool(value) if isinstance(node.op, ast.Not) else ~int(value)
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left = _evaluate_expression(node.left, values)
        right = _evaluate_expression(node.comparators[0], values)
        if isinstance(node.ops[0], ast.Eq):
            return left == right
        if isinstance(node.ops[0], ast.NotEq):
            return left != right
        if isinstance(node.ops[0], ast.Lt):
            return left < right
        if isinstance(node.ops[0], ast.LtE):
            return left <= right
        if isinstance(node.ops[0], ast.Gt):
            return left > right
        if isinstance(node.ops[0], ast.GtE):
            return left >= right
    raise ProfileError(f"unsupported expression element: {type(node).__name__}")
