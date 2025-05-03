"""
leetcodex.fetch
-------------------------------------------------
Fetch LeetCode problem metadata and example tests.

• fetch_problem(slug) -> (title, slug, examples)
      * examples is a list of (input_str, output_str | None)
      * Falls back to GraphQL's sampleTestCase when HTML lacks
        explicit "Input: … / Output: …" blocks.

• save_examples(slug, examples)
• load_cached_examples(slug)  -> examples | None
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

GRAPHQL_URL = "https://leetcode.com/graphql"



# Public helpers
def fetch_problem(title_slug: str) -> Tuple[str, str, List[Tuple[str, str | None]]]:
    """Return (title, slug, examples) for a LeetCode problem."""
    query = """
    query getQuestion($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        title
        content          # HTML body
        sampleTestCase   # fallback block
      }
    }
    """
    resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": {"titleSlug": title_slug}})
    resp.raise_for_status()

    data = resp.json()
    if data.get("errors") or not data.get("data", {}).get("question"):
        raise RuntimeError(f"Problem '{title_slug}' not found or API error.")

    q = data["data"]["question"]
    title = q["title"]
    content_html = q["content"] or ""

    # 1  Primary strategy — parse explicit Input/Output in <pre> tags
    examples: list[tuple[str, str | None]] = []
    soup = BeautifulSoup(content_html, "html.parser")

    for pre in soup.find_all("pre"):
        block = pre.get_text(separator="\n")  # keep line breaks
        if "Input:" in block and "Output:" in block:
            try:
                inp_idx = block.index("Input:")
                out_idx = block.index("Output:")
            except ValueError:
                continue

            input_str = block[inp_idx + len("Input:") : out_idx].strip()
            # Stop at Explanation: if present
            exp_idx = block.find("Explanation:")
            output_str = (
                block[out_idx + len("Output:") : exp_idx].strip() if exp_idx != -1 else block[out_idx + len("Output:") :].strip()
            )

            # Trim trailing dots so diffs are cleaner
            if input_str.endswith("."):
                input_str = input_str[:-1].strip()
            if output_str.endswith("."):
                output_str = output_str[:-1].strip()

            examples.append((input_str, output_str))

    # 2 Fallback — sampleTestCase field (inputs only)
    if not examples and q.get("sampleTestCase"):
        # sampleTestCase is a newline-joined block; split on blank lines
        raw_cases = [c.strip() for c in q["sampleTestCase"].strip().split("\n\n") if c.strip()]
        # expected output unknown -> None
        examples = [(c, None) for c in raw_cases]

    return title, title_slug, examples


def save_examples(slug: str, examples: List[Tuple[str, str | None]]) -> None:
    """Persist examples under .leetcodex/<slug>/input_N.txt / output_N.txt."""
    dir_path = Path(".leetcodex") / slug
    dir_path.mkdir(parents=True, exist_ok=True)

    for idx, (inp, out) in enumerate(examples, start=1):
        (dir_path / f"input_{idx}.txt").write_text(inp.strip() + "\n", encoding="utf-8")
        # Only save output file if we have an expected value
        if out is not None:
            (dir_path / f"output_{idx}.txt").write_text(out.strip() + "\n", encoding="utf-8")


def load_cached_examples(slug: str) -> List[Tuple[str, str | None]] | None:
    """Return cached examples or None if not present."""
    dir_path = Path(".leetcodex") / slug
    if not dir_path.is_dir():
        return None

    inputs = sorted(dir_path.glob("input_*.txt"), key=lambda p: int(p.stem.split("_")[1]))
    outputs = sorted(dir_path.glob("output_*.txt"), key=lambda p: int(p.stem.split("_")[1]))

    examples: list[tuple[str, str | None]] = []
    for inp_path in inputs:
        idx = inp_path.stem.split("_")[1]
        out_path = dir_path / f"output_{idx}.txt"
        inp_txt = inp_path.read_text(encoding="utf-8").strip()
        if out_path.exists():
            out_txt = out_path.read_text(encoding="utf-8").strip()
            examples.append((inp_txt, out_txt))
        else:
            examples.append((inp_txt, None))
    return examples
