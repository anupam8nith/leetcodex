"""
leetcodex.fetch
------------------------------------------------------------------
Utilities to download & cache LeetCode problem metadata.

• fetch_problem(slug) -> dict(
      title        = "Two Sum",
      slug         = "two-sum",
      html         = "<p>Given an integer array...</p>",
      markdown     = "### Given an integer array ...",
      examples     = [("nums = [2,7,11,15], target = 9", "[0,1]"), ...]
  )

• save_problem(data)  - stores .md + sample IO files
• load_cached_examples(slug) -> list[(inp,out) ] | None
"""
from __future__ import annotations

import os, re, html
from pathlib import Path
from typing import List, Tuple, Dict

import requests
from bs4 import BeautifulSoup
import html2text        # tiny; converts HTML → GitHub‑flavoured Markdown

__all__ = ["fetch_problem", "save_problem", "load_cached_examples"]


GRAPHQL_URL = "https://leetcode.com/graphql"
# ---------------------------------------------------------------------------


def _markdown_from_html(html_src: str) -> str:
    """Convert the HTML statement to reasonably clean Markdown."""
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.body_width = 0
    md = h2t.handle(html_src)
    # the GraphQL response encodes “&lt;” etc. once more → unescape
    return html.unescape(md).strip()


def fetch_problem(title_slug: str) -> Dict:
    """
    Return structured problem data.  Raises RuntimeError on network / API issues.
    """
    query = """
    query getQuestion($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        title
        content          # HTML body
        sampleTestCase   # fallback inputs
      }
    }
    """
    resp = requests.post(GRAPHQL_URL,
                         json={"query": query, "variables": {"titleSlug": title_slug}},
                         timeout=10)
    resp.raise_for_status()

    data = resp.json()
    q = data.get("data", {}).get("question")
    if not q:
        raise RuntimeError(f"Problem '{title_slug}' not found or API error.")

    title, content_html = q["title"], q["content"] or ""
    md_body = _markdown_from_html(content_html)

    # -- scrape explicit Input/Output blocks ------------------------------
    examples: list[Tuple[str, str | None]] = []
    soup = BeautifulSoup(content_html, "html.parser")

    for pre in soup.find_all("pre"):
        block = pre.get_text(separator="\n")
        if "Input:" in block and "Output:" in block:
            inp = block.split("Input:", 1)[1].split("Output:", 1)[0].strip().rstrip(".")
            out = block.split("Output:", 1)[1].split("Explanation:", 1)[0].strip().rstrip(".")
            examples.append((inp, out))

    # Fallback – one big sampleTestCase string (inputs only)
    if not examples and q.get("sampleTestCase"):
        raw_cases = [c.strip() for c in q["sampleTestCase"].strip().split("\n\n") if c.strip()]
        examples = [(c, None) for c in raw_cases]

    return dict(title=title,
                slug=title_slug,
                html=content_html,
                markdown=md_body,
                examples=examples)


# ---------------------------------------------------------------------------


def save_problem(problem: Dict) -> None:
    """
    Persist statement + examples under .leetcodex/<slug>/
    """
    slug = problem["slug"]
    dir_path = Path(".leetcodex") / slug
    dir_path.mkdir(parents=True, exist_ok=True)

    # 1. write statement
    (dir_path / "problem.md").write_text(f"# {problem['title']}\n\n{problem['markdown']}\n",
                                         encoding="utf-8")

    # 2. write each sample
    for idx, (inp, out) in enumerate(problem["examples"], 1):
        (dir_path / f"input_{idx}.txt").write_text(inp.strip() + "\n", encoding="utf-8")
        if out is not None:
            (dir_path / f"output_{idx}.txt").write_text(out.strip() + "\n", encoding="utf-8")


def load_cached_examples(slug: str) -> List[Tuple[str, str | None]] | None:
    """Return cached examples if present (legacy helper for CLI)."""
    dir_path = Path(".leetcodex") / slug
    if not dir_path.is_dir():
        return None
    inputs = sorted(dir_path.glob("input_*.txt"), key=lambda p: int(p.stem.split("_")[1]))
    outputs = sorted(dir_path.glob("output_*.txt"), key=lambda p: int(p.stem.split("_")[1]))

    ex: list[tuple[str, str | None]] = []
    for inp_path in inputs:
        idx = inp_path.stem.split("_")[1]
        inp = inp_path.read_text(encoding="utf-8").strip()
        out_path = dir_path / f"output_{idx}.txt"
        ex.append((inp, out_path.read_text(encoding="utf-8").strip() if out_path.exists() else None))
    return ex
