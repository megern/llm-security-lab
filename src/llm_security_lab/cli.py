import argparse
import hashlib
from pathlib import Path
import sys

from .backends import FixtureBackend, LocalMLXBackend
from .cases import load_cases
from .evaluate import evaluate, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline local LLM behavioral checks")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("evaluate", help="Evaluate local model outputs")
    command.add_argument("--backend", choices=("mlx", "fixture"), default="mlx")
    command.add_argument("--model", help="Existing local model directory; no Hub IDs or URLs")
    command.add_argument("--adapter", help="Existing local MLX adapter directory")
    command.add_argument("--cases", type=Path, required=True, help="Validated JSONL case file")
    command.add_argument("--output", type=Path, required=True, help="Report directory")
    command.add_argument("--max-tokens", type=int, default=128)
    command.add_argument("--max-input-tokens", type=int, default=2048)
    command.add_argument("--temperature", type=float, default=0.0)
    command.add_argument("--seed", type=int, default=7)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_tokens < 1 or args.max_input_tokens < 1:
        parser.error("Token limits must be positive")
    if not 0 <= args.temperature <= 2:
        parser.error("Temperature must be between 0 and 2")
    if args.backend == "mlx" and not args.model:
        parser.error("--model is required for the local MLX backend")
    if args.backend == "fixture" and (args.model or args.adapter):
        parser.error("Fixture does not accept a model or adapter")
    try:
        input_path = args.cases.resolve()
        output_directory = args.output.expanduser().resolve()
        report_paths = {
            (output_directory / filename).resolve()
            for filename in ("report.json", "report.md")
        }
        if input_path in report_paths:
            parser.error("Report output must not overwrite the input cases file, including symlink aliases.")
        cases = load_cases(args.cases)
        digest = hashlib.sha256(args.cases.read_bytes()).hexdigest()
        backend = FixtureBackend() if args.backend == "fixture" else LocalMLXBackend(
            args.model, adapter_path=args.adapter, max_tokens=args.max_tokens,
            max_input_tokens=args.max_input_tokens,
            temperature=args.temperature, seed=args.seed,
        )
        report = evaluate(backend, cases, dataset_sha256=digest, seed=args.seed)
        json_path, md_path = write_report(report, args.output)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2
    print(backend.evidence_label)
    print(f"Completed {report['summary']['cases_completed']}/{len(cases)} cases")
    print(f"JSON: {json_path}\nMarkdown: {md_path}")
    return 1 if report["summary"]["cases_failed"] else 0
