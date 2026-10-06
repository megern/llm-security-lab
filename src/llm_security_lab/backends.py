"""The model backend accepts existing local directories exclusively."""

from dataclasses import dataclass, field
import hashlib
import importlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path

from .cases import Case
from .checks import TOOL_MARKER

FIXTURE_LABEL = "deterministic fixture, not LLM security evidence"


@dataclass
class Generation:
    text: str
    metadata: dict = field(default_factory=dict)


def require_local_directory(value: str, *, adapter: bool = False) -> Path:
    if "://" in value or value.startswith(("hf:", "file:", "git@")):
        raise ValueError("A local filesystem directory is required; URLs are rejected")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Local directory does not exist: {path}")
    config = path / ("adapter_config.json" if adapter else "config.json")
    if not config.is_file():
        raise ValueError(f"Missing local configuration: {config}")
    try:
        content = json.loads(config.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise ValueError(f"Unreadable JSON configuration: {config}") from error
    if not isinstance(content, dict):
        raise ValueError("Local model configuration must be a JSON object")
    if adapter:
        if not (path / "adapters.safetensors").is_file():
            raise ValueError("Local adapter needs adapters.safetensors")
    elif not any(path.glob("*.safetensors")):
        raise ValueError("Local model needs safetensors weights in its directory")
    return path


class FixtureBackend:
    name = "fixture"
    evidence_label = FIXTURE_LABEL
    provenance = {"description": FIXTURE_LABEL}

    def generate(self, messages: list[dict], case: Case, canary: str) -> Generation:
        if case.kind == "benign":
            output = case.expected_exact
            if case.id.endswith("-03"):
                output = "لا أستطيع تنفيذ ذلك." if case.language == "ar" else "I cannot comply."
        elif case.kind == "direct":
            output = canary if case.goal == "canary" else TOOL_MARKER
        else:
            output = "تم تجاهل التعليمات غير الموثوقة." if case.language == "ar" else "Untrusted instructions ignored."
        return Generation(output, {"source": FIXTURE_LABEL, "finish_reason": "fixture"})


def enforce_offline() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"


class LocalMLXBackend:
    name = "mlx"
    evidence_label = "measured local LLM outputs; narrow heuristic checks only"

    def __init__(self, model_path: str, *, adapter_path: str | None = None,
                 max_tokens: int = 128, max_input_tokens: int = 2048,
                 temperature: float = 0.0, seed: int = 7):
        path = require_local_directory(model_path)
        adapter = require_local_directory(adapter_path, adapter=True) if adapter_path else None
        enforce_offline()
        try:
            mlx_lm = importlib.import_module("mlx_lm")
            mx = importlib.import_module("mlx.core")
            sampler_module = importlib.import_module("mlx_lm.sample_utils")
        except ImportError as error:
            raise RuntimeError("Install the local extra on Apple Silicon to use MLX") from error
        mx.random.seed(seed)
        self.model, self.tokenizer = mlx_lm.load(
            str(path),
            tokenizer_config={"local_files_only": True, "trust_remote_code": False},
            adapter_path=str(adapter) if adapter else None,
            trust_remote_code=False,
        )
        if not getattr(self.tokenizer, "chat_template", None):
            raise ValueError("This evaluation requires a local tokenizer with a chat template")
        self._stream_generate = mlx_lm.stream_generate
        self._sampler = sampler_module.make_sampler(temp=temperature)
        self.max_tokens = max_tokens
        self.max_input_tokens = max_input_tokens
        runtime_versions = {}
        for package in ("mlx-lm", "mlx", "transformers"):
            try:
                runtime_versions[package] = version(package)
            except PackageNotFoundError:
                runtime_versions[package] = None
        self.provenance = {
            "model_path": str(path),
            "adapter_path": str(adapter) if adapter else None,
            "adapter_weights_sha256": hashlib.sha256(
                (adapter / "adapters.safetensors").read_bytes()
            ).hexdigest() if adapter else None,
            "model_config_sha256": hashlib.sha256((path / "config.json").read_bytes()).hexdigest(),
            "weight_files": [{"name": p.name, "bytes": p.stat().st_size}
                             for p in sorted(path.glob("*.safetensors"))],
            "weight_hashes_recorded": False,
            "runtime_versions": runtime_versions,
            "seed": seed,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "max_input_tokens": max_input_tokens,
            "enable_thinking": False,
            "network_mode": "offline, no remote model identifiers",
        }

    def local_generate(self, messages: list[dict]) -> Generation:
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=False,
        )
        if len(prompt) > self.max_input_tokens:
            raise ValueError(
                f"Prompt has {len(prompt)} tokens; limit is {self.max_input_tokens}. "
                "Prompt is not silently truncated."
            )
        text = []
        last = None
        for chunk in self._stream_generate(
            self.model, self.tokenizer, prompt=prompt,
            max_tokens=self.max_tokens, sampler=self._sampler,
        ):
            text.append(chunk.text)
            last = chunk
        if last is None:
            raise RuntimeError("Local generation returned no response metadata")
        return Generation("".join(text), {
            "source": self.evidence_label,
            "prompt_tokens": last.prompt_tokens,
            "generation_tokens": last.generation_tokens,
            "finish_reason": last.finish_reason,
            "generation_tokens_per_second": last.generation_tps,
            "mlx_peak_memory_gb": last.peak_memory,
        })

    def generate(self, messages: list[dict], case: Case, canary: str) -> Generation:
        return self.local_generate(messages)
