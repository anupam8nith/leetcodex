<!-- # Leetcodex

**Leetcodex** is a Python library and CLI that lets you run your LeetCode solutions locally, using just your solution file. It automatically detects the language (Python, C++, Java, JavaScript, Go, or Rust), fetches sample test cases from LeetCode if you don’t provide any, and executes your code securely (optionally inside Docker) with resource limits. It then compares your output with the expected output and shows diffs for each test case.

## Installation

```bash
pip install leetcodex
 -->

# Leetcodex — Comprehensive User Guide

> **Version** 0.1.0   |   **Last updated:** May 2025   |   © 2025 Anupam Kumar  
> Licensed under the MIT License

---

## 1  Introduction

**Leetcodex** is a cross‑platform command‑line helper that lets you run
LeetCode® problems **locally** against the official example tests *and* any
custom cases you supply, in six languages:

| Language          | Extensions            | Runtime / Compiler    |
| ----------------- | --------------------- | --------------------- |
| Python            | `.py`                 | CPython ≥ 3.7         |
| C++               | `.cpp`, `.cc`, `.cxx` | GCC ≥ 9 or Clang ≥ 11 |
| Java              | `.java`               | OpenJDK ≥ 17          |
| JavaScript (Node) | `.js`                 | Node ≥ 14             |
| Go                | `.go`                 | Go ≥ 1.18             |
| Rust              | `.rs`                 | Rust ≥ 1.70           |

The tool prefers **native execution** when a compiler is on your `PATH`.
Otherwise it transparently falls back to a **Docker® sandbox**.

---

## 2  Installation

### 2.1 Prerequisites

| Requirement          | Recommended Version | Notes                                   |
| -------------------- | ------------------- | --------------------------------------- |
| Python               | 3.8 – 3.12          | Needed only for the CLI itself          |
| pip / pipx           | latest              | `pipx install leetcodex` isolates deps  |
| Docker (optional)    | 24.x+               | Required for sandbox fallback           |
| Compilers / Runtimes | see table above     | Only if you prefer native execution     |

### 2.2 Install from PyPI (stable)

```bash
pip install leetcodex          # or: pipx install leetcodex
````

\### 2.3 Install from Source (development)

```bash
git clone https://github.com/YOUR‑ORG/leetcodex.git
cd leetcodex
pip install -e .[dev]          # editable + dev deps
```

---

\## 3  Quick Start

```bash
# 1   Fetch sample tests
leet fetch two-sum

# 2   Write your solution
vim two_sum.py          # or .cpp / .java / …

# 3   Run locally
leet test two_sum.py
```

Example output:

```
Fetched 1 sample test case(s) for "Two Sum" (slug: two-sum).
Test case 1: PASSED ✅
----------
```

*Whitespace differences like `[0,1]` vs `[0, 1]` are ignored by default.*

---

\## 4  Command Reference

| Command              | Purpose                                                                 |                                                           |
| -------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------- |
| \`leet fetch \<slug  |  URL>\`                                                                 | Download example inputs/outputs into `.leetcodex/<slug>/` |
| `leet test  <file>`  | Compile/interpret the file, run all tests, show coloured diff & verdict |                                                           |
| `leet run   <file>`  | Run once, stream stdin / stdout / stderr (no verdict)                   |                                                           |

\### 4.1 Common Options

| Flag / Option            | Default | Meaning                                    |
| ------------------------ | ------- | ------------------------------------------ |
| `--docker / --no-docker` | auto    | Force (or forbid) container execution      |
| `--timeout  <sec>`       | 2       | CPU‑time limit per test case               |
| `--memory   <MB>`        | 256     | Memory limit per test case                 |
| `-i / --input` (str)     | —       | Custom stdin (repeatable)                  |
| `-o / --output` (str)    | —       | Expected stdout for each `-i` (repeatable) |
| `-p / --problem <slug>`  | —       | Explicit slug when filename is ambiguous   |

---

\## 5  Language‑Specific Examples

\### 5.1 Python

```python
class Solution:
    def productExceptSelf(self, nums):
        n = len(nums)
        left = [1]*n; right = [1]*n
        for i in range(1,n):          left[i]  = left[i-1]  * nums[i-1]
        for i in range(n-2,-1,-1):    right[i] = right[i+1] * nums[i+1]
        return [l*r for l,r in zip(left,right)]
```
*You dont need to define a driver for your code in Python. It will evaluate the examples by itself.*

Run:

```bash
leet test product_except_self.py --problem product-of-array-except-self
```

\### 5.2 C++ — two workflows

\#### A. Macro (no `main()`)

```cpp
#include <bits/stdc++.h>
using namespace std;

#define LEE_METHOD solve      // wrapper calls Solution().solve(raw)

class Solution {
public:
    long long solve(const string& raw){
        /* parse raw → n, vector<vector<int>> */
        /* compute & return answer */
    }
};
```

\#### B. Own `main()`

```cpp
#include <bits/stdc++.h>
using namespace std;
class Solution { /* … */ };
int main(){
    int n; cin >> n;
    string json; getline(cin,json); getline(cin,json);
    /* parse… */
    cout << Solution().countCoveredBuildings(n, parsed) << '\n';
}
```
*main() or #def LEE_METHOD is required for evaluation whether test cases passed.*

---

\## 6  Whitespace‑Insensitive Comparison

Leetcodex normalises answers with:

```python
import ast, re
def norm(s):
    try:  return ast.literal_eval(s.strip())
    except Exception:
        return re.sub(r"\s+", "", s.strip())
```

Thus `[1,2]` ≡ `[1, 2]`, `{ "a":1 }` ≡ `{"a":1}`, and `YES NO` ≡ `YES  NO`.

---

\## 7  Sandbox & Resource Limits

* **Local mode**: subprocess + RLIMITS (Linux/macOS).
* **Docker mode**: read‑only bind mount, `--network=none`, memory/CPU caps,
  `no-new-privileges`, `pids‑limit 64`.
* The compilation phase has **no timeout**; limits apply only to execution.

---

\## 8  Configuration (`~/.config/leetcodex/config.yml`)

```yaml
sandbox: auto        # auto | docker | local
cpu_limit: 2         # seconds per test
memory_limit: 256    # MB per test
judge0_url: ""       # optional fallback
```

---

\## 9  CI Integration (GitHub Actions)

```yaml
jobs:
  judge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install leetcodex
      - run: leet test solutions/two_sum.cpp --problem two-sum --no-docker
```

---

\## 10  Contributing

1. Fork → feature branch.
2. `ruff --fix` & `black .`
3. Add/adjust tests under `tests/`.
4. PR with a clear description.

Adding a language? Update `leetcodex/languages.yaml`, add example + test, and
extend this README table.

---

\## 11  License

MIT License — see `LICENSE`.

LeetCode® is a trademark of LeetCode Inc.; this project is not affiliated.

---

> *Happy coding & debugging — The Leetcodex team* 🚀

````