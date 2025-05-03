import os
import requests
from bs4 import BeautifulSoup

# GraphQL endpoint for LeetCode problem data
GRAPHQL_URL = "https://leetcode.com/graphql"

def fetch_problem(title_slug):
    """Fetch problem details and example test cases by LeetCode slug."""
    # GraphQL query to get problem content and sample test
    query = '''
    query getQuestion($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionId
        title
        content
        sampleTestCase
      }
    }
    '''
    try:
        resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": {"titleSlug": title_slug}})
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch problem data: {e}")
    data = resp.json()
    # Check for errors or missing data
    if data.get("errors") or not data.get("data", {}).get("question"):
        raise RuntimeError(f"Problem '{title_slug}' not found or API error.")
    q = data["data"]["question"]
    title = q["title"]
    content_html = q["content"]
    # Parse HTML content to extract sample Input/Output pairs
    soup = BeautifulSoup(content_html, "html.parser")
    examples = []
    for pre in soup.find_all("pre"):
        text = pre.get_text(separator="\n")  # get text with line breaks if any
        if "Input:" in text and "Output:" in text:
            try:
                inp_idx = text.index("Input:")
                out_idx = text.index("Output:")
            except ValueError:
                continue
            # Extract text between "Input:" and "Output:" for input, and between "Output:" and "Explanation:" (or end) for output
            input_str = text[inp_idx + len("Input:"): out_idx].strip()
            # Handle optional Explanation
            exp_idx = text.find("Explanation:")
            if exp_idx != -1:
                output_str = text[out_idx + len("Output:"): exp_idx].strip()
            else:
                output_str = text[out_idx + len("Output:"):].strip()
            # Remove trailing punctuation (e.g., ending period) if present
            if input_str.endswith("."):
                input_str = input_str[:-1].strip()
            if output_str.endswith("."):
                output_str = output_str[:-1].strip()
            examples.append((input_str, output_str))
    return title, title_slug, examples

def save_examples(slug, examples):
    """Save fetched example test cases to .leetcodex/<slug>/ files."""
    dir_path = f".leetcodex/{slug}"
    os.makedirs(dir_path, exist_ok=True)
    for i, (inp, out) in enumerate(examples, start=1):
        with open(os.path.join(dir_path, f"input_{i}.txt"), "w") as f_in:
            f_in.write(inp.strip() + "\n")
        with open(os.path.join(dir_path, f"output_{i}.txt"), "w") as f_out:
            f_out.write(out.strip() + "\n")

def load_cached_examples(slug):
    """Load previously fetched test cases from .leetcodex/<slug>/ if available."""
    dir_path = f".leetcodex/{slug}"
    if not os.path.isdir(dir_path):
        return None
    inputs = sorted([fn for fn in os.listdir(dir_path) if fn.startswith("input_")],
                    key=lambda x: int(x.split('_')[1].split('.')[0]))
    outputs = sorted([fn for fn in os.listdir(dir_path) if fn.startswith("output_")],
                     key=lambda x: int(x.split('_')[1].split('.')[0]))
    examples = []
    for inp_file, out_file in zip(inputs, outputs):
        with open(os.path.join(dir_path, inp_file)) as f_in:
            inp = f_in.read().strip()
        with open(os.path.join(dir_path, out_file)) as f_out:
            out = f_out.read().strip()
        examples.append((inp, out))
    return examples
