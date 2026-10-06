# Measured local Qwen3 baseline

This is an actual local evaluation of the unmodified 4-bit Qwen3 0.6B base, not the deterministic fixture and not a trained adapter. Generation ran on an Apple M1 with 16GB unified memory, with greedy sampling, seed 7, a 128-token output limit and a 2,048-token input limit. All 32 authored cases completed; no generation errors or responses reaching the token limit were recorded.

| Narrow output check | Observed | Relevant cases |
|---|---:|---:|
| Full synthetic canary disclosure in canary-goal attacks | 2 | 16 |
| Exact text tool marker in tool-goal attacks | 6 | 8 |
| Exact benign answer | 1 | 8 |

The model emitted the tool marker in nine cases overall, including cases whose primary goal was different. No tools exist in this evaluation and no action was executed. A marker may appear in quoted or explanatory text; this detector intentionally counts its text emission. Exact benign matching is strict and can reject semantically acceptable answers.

Arabic and English summaries, messages, synthetic canaries and complete outputs are in [report.json](report.json); [report.md](report.md) provides readable output traces. Two observed canary disclosures illustrate failures in this small public set. The absence of a detected disclosure in another case is not a security guarantee. This run is not a comprehensive benchmark or a language-ranking claim.

Base: [mlx-community/Qwen3-0.6B-4bit at the pinned revision](https://huggingface.co/mlx-community/Qwen3-0.6B-4bit/tree/73e3e38d981303bc594367cd910ea6eb48349da8), Apache-2.0. No model weights are redistributed. Upstream revision and weight-hash provenance was added after the evaluation from the verified local training experiment. The only redaction in the public report is the absolute local model directory.
