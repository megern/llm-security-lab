"""Strict case validation keeps attack text inside the untrusted user role."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Case:
    id: str
    language: str
    kind: str
    goal: str
    prompt: str
    untrusted_text: str | None = None
    expected_exact: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def parse_case(value: object) -> Case:
    if not isinstance(value, dict):
        raise ValueError("Each case must be a JSON object")
    required = {"id", "language", "kind", "goal", "prompt"}
    allowed = required | {"untrusted_text", "expected_exact"}
    if missing := required - value.keys():
        raise ValueError(f"Missing case fields: {sorted(missing)}")
    if extra := value.keys() - allowed:
        raise ValueError(f"Unknown case fields: {sorted(extra)}")
    for key, item in value.items():
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} must be a non-empty string")
        if len(item) > 8_000:
            raise ValueError(f"{key} exceeds the 8000-character case limit")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", value["id"]):
        raise ValueError("Case id must use lowercase ASCII letters, numbers and hyphens")
    if value["language"] not in {"ar", "en"}:
        raise ValueError("language must be ar or en")
    if value["kind"] not in {"direct", "indirect", "benign"}:
        raise ValueError("kind must be direct, indirect or benign")
    if value["goal"] not in {"canary", "tool_marker", "benign"}:
        raise ValueError("goal must be canary, tool_marker or benign")
    benign = value["kind"] == "benign"
    if benign != (value["goal"] == "benign"):
        raise ValueError("Only benign cases can have the benign goal")
    if benign != ("expected_exact" in value):
        raise ValueError("expected_exact is required only for benign cases")
    if (value["kind"] == "indirect") != ("untrusted_text" in value):
        raise ValueError("untrusted_text is required only for indirect cases")
    return Case(**value)


def load_cases(path: str | Path) -> list[Case]:
    cases = []
    seen = set()
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                case = parse_case(json.loads(line))
            except (ValueError, TypeError) as error:
                raise ValueError(f"{path}:{line_number}: {error}") from error
            if case.id in seen:
                raise ValueError(f"{path}:{line_number}: duplicate id {case.id}")
            seen.add(case.id)
            cases.append(case)
    if not cases:
        raise ValueError("The case file is empty")
    return cases

