<!-- # Leetcodex

**Leetcodex** is a Python library and CLI that lets you run your LeetCode solutions locally, using just your solution file. It automatically detects the language (Python, C++, Java, JavaScript, Go, or Rust), fetches sample test cases from LeetCode if you don’t provide any, and executes your code securely (optionally inside Docker) with resource limits. It then compares your output with the expected output and shows diffs for each test case.

## Installation

```bash
pip install leetcodex
 -->


# Leetcodex — Comprehensive User Guide

> **Version** 0.1.0   |   **Last updated:** May 2025   |   © 2025 Anupam Kumar. MIT License

---

## 1  Introduction

**Leetcodex** is a cross‑platform command‑line helper that lets you run LeetCode® problems **locally** against the official example test‑cases (and any custom cases you supply) in six languages:

| Language          | Extensions            | Runtime / Compiler    |
| ----------------- | --------------------- | --------------------- |
| Python            | `.py`                 | CPython ≥ 3.7         |
| C++               | `.cpp`, `.cc`, `.cxx` | GCC ≥ 9 or Clang ≥ 11 |
| Java              | `.java`               | OpenJDK ≥ 17          |
| JavaScript (Node) | `.js`                 | Node ≥ 14             |
| Go                | `.go`                 | Go ≥ 1.18             |
| Rust              | `.rs`                 | Rust ≥ 1.70           |

The tool relies on **direct execution** when the required compiler/interpreter is already installed. When that is unsafe or unavailable it transparently falls back to a **Docker® sandbox** to keep your host clean and secure.

---

## 2  Installation

### 2.1  Prerequisites

| Requirement          | Recommended Version | Notes                                         |
| -------------------- | ------------------- | --------------------------------------------- |
| Python 3             | 3.8 – 3.12          | Needed only to install & run Leetcodex itself |
| pip / pipx           | latest              | `pipx install leetcodex` keeps it isolated    |
| Docker (optional)    | 24.x+               | Required for sandbox fallback                 |
| Compilers / Runtimes | see table above     | Only if you prefer native execution           |

### 2.2  Install from PyPI (stable)

```bash
pip install leetcodex            # system‑wide / venv
# ‑‑or‑‑
pipx install leetcodex           # isolated user install (recommended)
```

### 2.3  Install from Source (development)

```bash
git clone https://github.com/YOUR‑ORG/leetcodex.git
cd leetcodex
pip install -e .[dev]            # editable + dev deps (pytest, ruff, black)
```

---

## 3  Quick Start

```bash
# 1.  Fetch the sample tests for a problem (using its slug)
leet fetch two-sum

# 2.  Solve the problem in your language of choice
vim my_solutions/two_sum.py

# 3.  Run the solution against the fetched tests
leet test my_solutions/two_sum.py
```

**Output example**

```
Fetched 1 sample test case(s) for "Two Sum" (slug: two-sum).
Test case 1: PASSED ✅
----------
```

---

## 4  Command Reference

| Command             | Description                                                                                                      |                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| \`leet fetch \<slug | URL>\`                                                                                                           | Download the example inputs/outputs and store them under `.leetcodex/<slug>/` |
| `leet test <file>`  | Compile/interpret the **local** source file, then run all test‑cases (sample or custom) and show a coloured diff |                                                                               |
| `leet run <file>`   | Execute the program once, streaming stdin/stdout/stderr (no verdict)                                             |                                                                               |

### 4.1  Common Options

| Option                   | Default | Meaning                                      |
| ------------------------ | ------- | -------------------------------------------- |
| `--docker / --no-docker` | auto    | Force (or forbid) Docker sandboxing          |
| `--timeout <sec>`        | 2       | CPU time limit per run                       |
| `--memory  <MB>`         | 256     | Memory limit per run                         |
| `-i / --input`           |  —      | Custom stdin (repeatable)                    |
| `-o / --output`          |  —      | Expected stdout for each `-i` (repeatable)   |
| `-p / --problem <slug>`  |  —      | Explicit slug when the filename is ambiguous |

---

## 5  Language‑Specific Examples

### 5.1  Python Example

`two_sum.py`:

```python
class Solution:
    def twoSum(self, nums, target):
        lookup = {}
        for i, n in enumerate(nums):
            if target - n in lookup:
                return [lookup[target - n], i]
            lookup[n] = i
# Driver for local execution
a = eval(input())   # "[2,7,11,15]"
b = int(input())    # "9"
print(Solution().twoSum(a, b))
```

Run it:

```bash
leet test two_sum.py          # uses cached sample tests
```

### 5.2  C++ Example

`two_sum.cpp`:

```cpp
#include <bits/stdc++.h>
using namespace std;
class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int,int> mp;
        for(int i=0;i<nums.size();++i){
            if(mp.count(target-nums[i])) return {mp[target-nums[i]], i};
            mp[nums[i]] = i;
        }
        return {};
    }
};
int main(){
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    vector<int> nums;
    char ch;
    if(!(cin>>ch) || ch!='[') return 0; // crude parser
    int x;
    while(cin>>x){ nums.push_back(x); if(cin.peek()==',') cin.get(); else break; }
    cin>>ch; // ]
    int target; cin>>target;
    auto res = Solution().twoSum(nums,target);
    cout << "[" << res[0] << "," << res[1] << "]\n";
}
```

Compile‑and‑run natively (if `g++` is present):

```bash
leet test two_sum.cpp
```

If `g++` is **missing**, Leetcodex will attempt Docker:

```bash
leet test two_sum.cpp --docker
```

---

## 6  Sandboxing & Security Model

1. **Local mode** (default) – Leetcodex spawns a subprocess, optionally applying RLIMITs (Linux/macOS) for CPU & memory.
2. **Docker mode** – The solution file is bind‑mounted **read‑only** as `/code/<file>`; no other host files are exposed. Container flags:

   * `--network none`          (no internet)
   * `--memory <MB>`           (limit RAM)
   * `--ulimit cpu=<sec>`      (limit CPU time)
   * `--pids‑limit 64`         (curtail fork bombs)
   * `--security-opt no-new-privileges`

If Docker is unavailable on Windows Home or CI, you can point the tool to a **Judge0** micro‑service via the forthcoming `LEETCODEX_JUDGE0_URL` env var (experimental).

---

## 7  Configuration File (`~/.config/leetcodex/config.yml`)

```yaml
sandbox: auto        # auto | docker | local
cpu_limit: 2         # seconds
memory_limit: 256    # MB
default_timeout: 10  # compilation / network fetch
judge0_url: ""       # URL to a Judge0 CE instance (optional)
```

Any CLI flag overrides the file.

---

## 8  Integrating with Continuous Integration (GitHub Actions)

```yaml
name: leetcodex‑tests
on: [push, pull_request]

jobs:
  lint‑and‑test:
    runs-on: ubuntu‑latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup‑python@v5
        with:
          python-version: '3.12'
      - run: pip install leetcodex pytest ruff
      - run: pytest -q
```

Add a matrix job with `docker` service if you need container runs.

---

## 9  Troubleshooting

| Symptom                            | Resolution                                                          |
| ---------------------------------- | ------------------------------------------------------------------- |
| `Unsupported language`             | Check file extension & `languages.yaml`                             |
| `Compilation Failed`               | View the error shown; ensure compiler exists or run with `--docker` |
| `Timed out after Xs`               | Optimise your algorithm or raise `--timeout`                        |
| Docker permission error (`EACCES`) | Add your user to the `docker` group or use `sudo`                   |
| `Problem slug not found`           | Verify the slug/URL and your internet connectivity                  |

---

## 10  Contributing

* Fork, create a feature branch, run `ruff --fix` & `black .`.
* Add/modify unit tests in `tests/`.
* Submit a pull request with a clear description.

### Adding a New Language

1. Edit `leetcodex/languages.yaml` and append a block with:

   ```yaml
   <lang>:
     extensions: [".<ext>"]
     compile: [<host compile cmd>]
     run: [<host run cmd>]
     docker_image: "<image>:tag"
     docker_compile: [<container compile cmd>]
     docker_run: [<container run cmd>]
   ```
2. Add an example solution & unit test.
3. Update `README.md` table.

---

## 11  License

Leetcodex is released under the MIT License (see `LICENSE`).

---

## 12  FAQ

**Q 1. Does Leetcodex retrieve hidden tests?** No. Hidden tests are proprietary to LeetCode and remain on their servers.

**Q 2. Can I submit my solution to LeetCode from Leetcodex?** Not yet. A future `leet submit` command is planned once a stable API workflow is agreed.

**Q 3. Why do I get a Docker error on Windows?** Ensure Docker Desktop is running and the WSL kernel is up‑to‑date. Use `--no-docker` to force native execution if you have compilers installed.

---

> *Happy coding & debugging!*  — The Leetcodex team
