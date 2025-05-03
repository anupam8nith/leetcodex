import os
import click
from . import __version__, fetch, runner

@click.group()
@click.version_option(__version__, prog_name="leetcodex")
def cli():
    """Leetcodex CLI - Run LeetCode solutions locally."""
    pass

@cli.command()
@click.argument('problem', required=True)
def fetch(problem):
    """
    Fetch sample test cases for a LeetCode problem.
    Provide the problem slug (e.g. "two-sum") or full URL.
    """
    # Allow full URL or slug
    slug = problem
    if problem.startswith("http"):
        # Extract slug from URL
        import re
        match = re.search(r'/problems/([^/]+)/', problem)
        if match:
            slug = match.group(1)
        else:
            click.echo("Error: Invalid LeetCode problem URL.")
            return
    try:
        title, slug, examples = fetch.fetch_problem(slug)
    except Exception as e:
        click.echo(f"Error fetching problem data: {e}")
        return
    if not examples:
        click.echo(f"No example test cases found for problem '{slug}'.")
        return
    fetch.save_examples(slug, examples)
    click.echo(f"Fetched {len(examples)} sample test case(s) for \"{title}\" (slug: {slug}).")
    click.echo(f"Saved to .leetcodex/{slug}/")

@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('-p', '--problem', help="Problem slug (if fetching sample tests is required)")
@click.option('-i', '--input', 'inputs', multiple=True, help="Custom input case(s) (can use multiple).")
@click.option('-o', '--output', 'outputs', multiple=True, help="Expected output(s) for each custom input (order matters).")
@click.option('--docker/--no-docker', default=None, help="Force use (or not) of Docker sandbox for execution.")
@click.option('--timeout', default=2, help="CPU time limit per test (seconds).")
@click.option('--memory', default=256, help="Memory limit per test (MB).")
def test(file, problem, inputs, outputs, docker, timeout, memory):
    """
    Run the given solution file against test cases and check outputs.
    If no custom input/output provided, uses the LeetCode sample cases.
    """
    # Prepare test cases list
    test_cases = []
    if inputs and outputs:
        if len(inputs) != len(outputs):
            click.echo("Error: Number of inputs and outputs do not match.")
            return
        for inp, out in zip(inputs, outputs):
            test_cases.append((inp, out))
    elif inputs and not outputs:
        # Only inputs given (no expected outputs)
        for inp in inputs:
            test_cases.append((inp, None))
    else:
        # No custom tests provided, fetch or load sample test cases
        slug = problem
        if not slug:
            # Derive slug from file name heuristic (lowercase and hyphens)
            base_name = os.path.splitext(os.path.basename(file))[0]
            slug = base_name.lower().replace('_', '-')
        examples = fetch.load_cached_examples(slug)
        if examples is None:
            # Fetch from LeetCode if not cached
            try:
                title, slug, examples = fetch.fetch_problem(slug)
            except Exception as e:
                click.echo(f"Error fetching sample test cases: {e}")
                return
            if not examples:
                click.echo(f"No sample test cases available for problem slug '{slug}'.")
                return
            fetch.save_examples(slug, examples)
            click.echo(f"Fetched {len(examples)} sample test case(s) for \"{title}\".")
        test_cases = [(inp, out) for inp, out in (examples or [])]
    # Run the tests
    try:
        compile_err, results = runner.run_tests(file, test_cases, use_docker=docker, timeout=timeout, memory=memory)
    except Exception as e:
        click.echo(f"Error during execution: {e}")
        return
    if compile_err:
        click.echo("❌ Compilation Failed:")
        click.echo(compile_err)
        return
    # Display results for each test case
    for idx, res in enumerate(results, start=1):
        exp = res['expected']
        got = res['output']
        inp = res['input']
        passed = res['passed']
        err = res.get('error')
        if exp is None:
            click.echo(f"Test case {idx}: (no expected output provided)")
        else:
            status = "PASSED ✅" if passed else "FAILED ❌"
            click.echo(f"Test case {idx}: {status}")
        click.echo(f"Input: {inp}")
        if exp is not None:
            click.echo(f"Expected Output: {exp}")
        if err:
            click.echo(f"Runtime Error: {err}")
        else:
            click.echo(f"Your Output: {got}")
        # Show diff if output is wrong
        if exp is not None and not passed:
            diff_lines = runner.diff_outputs(exp, got)
            if diff_lines:
                click.echo("Difference (expected vs actual):")
                for line in diff_lines:
                    click.echo(line)
        click.echo("-" * 10)  # separator line


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('-i', '--input', 'input_data', help="Input to send to the program on stdin.")
@click.option('--docker/--no-docker', default=None, help="Use Docker sandbox for execution.")
@click.option('--timeout', default=None, type=int, help="CPU time limit (seconds).")
@click.option('--memory', default=None, type=int, help="Memory limit (MB).")
def run(file, input_data, docker, timeout, memory):
    """
    Run the given solution file as a standalone program and print its output.
    If --input is provided, it will be fed to the program's stdin.
    """
    # We can reuse runner.run_tests with a single test case (expected output unknown)
    try:
        _, results = runner.run_tests(file, [(input_data or "", None)], use_docker=docker, timeout=timeout, memory=memory)
    except Exception as e:
        click.echo(f"Error running the program: {e}")
        return
    if not results:
        click.echo("No output.")
        return
    res = results[0]
    if res.get('error'):
        click.echo(f"Error: {res['error']}")
    else:
        output = res['output']
        if output == "" and (input_data is None or input_data == ""):
            click.echo("Program finished with no output.")
        else:
            click.echo(output)
