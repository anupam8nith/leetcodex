""" leetcodex.fetch — Fetch LeetCode problem metadata, statement & examples. """

from __future__ import annotations
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import html2text
import requests
from bs4 import BeautifulSoup

GRAPHQL_URL = "https://leetcode.com/graphql"


@dataclass
class _Problem:
    title: str
    slug: str
    examples: List[Tuple[str, Optional[str]]]
    markdown: str
    code_defs: List[dict]

    # allow unpacking into (title, slug, examples)
    def __iter__(self):
        yield self.title
        yield self.slug
        yield self.examples


def fetch_problem(title_slug: str) -> _Problem:
    """
    Return a _Problem containing:
      • title
      • slug
      • examples [(input_str, output_str|None), …]
      • markdown statement
      • code_defs list (starter-code templates)
    """
    query = """
    query getQuestion($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        title
        content
        sampleTestCase
        codeDefinition
      }
    }"""
    resp = requests.post(GRAPHQL_URL,
                         json={"query": query,
                               "variables": {"titleSlug": title_slug}})
    resp.raise_for_status()
    data = resp.json().get("data", {}).get("question")
    if not data:
        raise RuntimeError(f"Problem '{title_slug}' not found.")

    title      = data["title"]
    html_body  = data["content"] or ""

    # 1) parse sample I/O from <pre> tags
    soup = BeautifulSoup(html_body, "html.parser")
    examples: List[Tuple[str, Optional[str]]] = []
    for pre in soup.find_all("pre"):
        txt = pre.get_text("\n")
        if "Input:" in txt and "Output:" in txt:
            inp = txt.split("Input:",1)[1].split("Output:",1)[0].strip().rstrip(".")
            out = txt.split("Output:",1)[1].split("Explanation:",1)[0].strip().rstrip(".")
            examples.append((inp, out))

    # 2) fallback to sampleTestCase if none found
    if not examples and data.get("sampleTestCase"):
        for block in data["sampleTestCase"].strip().split("\n\n"):
            s = block.strip()
            if s:
                examples.append((s, None))

    # 3) full problem statement → markdown
    markdown = html2text.html2text(html_body).strip()

    # 4) parse starter-code JSON
    code_defs = json.loads(data.get("codeDefinition") or "[]")

    return _Problem(title, title_slug, examples, markdown, code_defs)


def load_cached_examples(slug: str) -> Optional[List[Tuple[str, Optional[str]]]]:
    """
    Return cached sample I/O under .leetcodex/<slug>/, or None if none exists.
    """
    root = Path(".leetcodex") / slug
    if not root.is_dir():
        return None

    ins  = sorted(root.glob("input_*.txt"),  key=lambda p: int(p.stem.split("_")[1]))
    outs = sorted(root.glob("output_*.txt"), key=lambda p: int(p.stem.split("_")[1]))
    examples: List[Tuple[str, Optional[str]]] = []
    for inp_path in ins:
        idx    = inp_path.stem.split("_")[1]
        out_path = root / f"output_{idx}.txt"
        inp_txt  = inp_path.read_text(encoding="utf-8").strip()
        out_txt  = out_path.read_text(encoding="utf-8").strip() if out_path.exists() else None
        examples.append((inp_txt, out_txt))
    return examples


def save_problem_assets(
    slug: str,
    examples: List[Tuple[str, Optional[str]]],
    markdown: str,
    code_defs: List[dict],
) -> None:
    """
    Write under .leetcodex/<slug>/:
      - input_*.txt / output_*.txt
      - problem.md
      - <slug>.<ext> for each starter template
    """
    root = Path(".leetcodex") / slug
    root.mkdir(parents=True, exist_ok=True)

    # a) I/O files
    for i, (inp, out) in enumerate(examples, start=1):
        (root / f"input_{i}.txt").write_text(inp.rstrip() + "\n", encoding="utf-8")
        if out is not None:
            (root / f"output_{i}.txt").write_text(out.rstrip() + "\n", encoding="utf-8")

    # b) statement
    (root / "problem.md").write_text(markdown + "\n", encoding="utf-8")

    # c) starter code templates
    ext_map = {
        "python":    "py",
        "python3":   "py",
        "cpp":       "cpp",
        "java":      "java",
        "javascript":"js",
        "go":        "go",
        "rust":      "rs",
    }
    for entry in code_defs:
        lang = entry.get("value")
        ext  = ext_map.get(lang)
        if not ext:
            continue
        fname = root / f"{slug}.{ext}"
        code  = textwrap.dedent(entry.get("defaultCode", "")) + "\n"
        fname.write_text(code, encoding="utf-8")
