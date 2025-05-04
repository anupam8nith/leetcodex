import os
import re
from pathlib import Path
import click
from . import __version__, fetch as fetch_mod, runner

@click.group()
@click.version_option(__version__, prog_name="leetcodex")
def cli():
    """Leetcodex CLI — run LeetCode solutions locally."""
    pass

@cli.command()
@click.argument('problem', required=True)
def fetch(problem):
    """
    Fetch sample I/O, statement, and starter templates for a LeetCode problem.
    """
    slug = problem
    if problem.startswith("http"):
        m = re.search(r'/problems/([^/]+)/', problem)
        if m:
            slug = m.group(1)
        else:
            click.echo("Error: Invalid LeetCode problem URL.")
            return

    try:
        prob = fetch_mod.fetch_problem(slug)
    except Exception as e:
        click.echo(f"Error fetching problem data: {e}")
        return

    if not prob.examples:
        click.echo(f"No example test cases found for problem '{prob.slug}'.")
        return

    fetch_mod.save_problem_assets(
        prob.slug,
        prob.examples,
        prob.markdown,
        prob.code_defs,
    )
    click.echo(
        f"Fetched {len(prob.examples)} sample test case(s) for "
        f"\"{prob.title}\" (slug: {prob.slug})."
    )
    click.echo(f"Saved to .leetcodex/{prob.slug}/")


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('-p', '--problem', help="Problem slug (if fetching sample tests).")
@click.option('-i', '--input', 'inputs', multiple=True, help="Custom input(s).")
@click.option('-o', '--output', 'outputs', multiple=True, help="Expected output(s).")
@click.option('--docker/--no-docker', default=None, help="Use Docker sandbox.")
@click.option('--timeout', default=2, help="Time limit per test (s).")
@click.option('--memory', default=256, help="Memory limit per test (MB).")
def test(file, problem, inputs, outputs, docker, timeout, memory):
    """
    Run the given solution file against test cases (sample or custom).
    """
    # 1) custom I/O
    if inputs and outputs:
        if len(inputs) != len(outputs):
            click.echo("Error: Number of inputs and outputs do not match.")
            return
        test_cases = list(zip(inputs, outputs))
    elif inputs:
        test_cases = [(i, None) for i in inputs]
    else:
        # 2) load or fetch sample tests
        slug = problem or Path(file).stem.lower().replace('_','-')
        examples = fetch_mod.load_cached_examples(slug)
        if examples is None:
            try:
                _, slug, examples = fetch_mod.fetch_problem(slug)
            except Exception as e:
                click.echo(f"Error fetching sample test cases: {e}")
                return
            if not examples:
                click.echo(f"No sample test cases for slug '{slug}'.")
                return
            fetch_mod.save_problem_assets(slug, examples, "", [])
            click.echo(f"Fetched {len(examples)} sample test case(s) for slug '{slug}'.")
        test_cases = examples

    # 3) run & compare
    compile_err, results = runner.run_tests(
        file, test_cases,
        use_docker=docker, timeout=timeout, memory=memory
    )
    if compile_err:
        click.echo("❌ Compilation/Execution Failed:")
        click.echo(compile_err)
        return

    for idx, res in enumerate(results, start=1):
        inp, exp, out, err, ok = res['input'], res['expected'], res['output'], res.get('error'), res['passed']
        status = "PASSED ✅" if exp is not None and ok else ("FAILED ❌" if exp is not None else "(no expected output)")
        click.echo(f"Test case {idx}: {status}")
        click.echo(f"Input: {inp}")
        if exp is not None:
            click.echo(f"Expected Output: {exp}")
        if err:
            click.echo(f"Runtime Error: {err}")
        else:
            click.echo(f"Your Output: {out}")
        if exp is not None and not ok:
            click.echo("Difference (expected vs actual):")
            for line in runner.diff_outputs(exp, out):
                click.echo(line)
        click.echo("-"*10)


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('-i', '--input', 'input_data', help="Custom stdin.")
@click.option('--docker/--no-docker', default=None, help="Use Docker sandbox.")
@click.option('--timeout', default=None, type=int, help="CPU time limit (s).")
@click.option('--memory', default=None, type=int, help="Memory limit (MB).")
def run(file, input_data, docker, timeout, memory):
    """
    Run the given solution file once and print its stdout.
    """
    _, results = runner.run_tests(
        file, [(input_data or "", None)],
        use_docker=docker, timeout=timeout, memory=memory
    )
    res = results[0] if results else {}
    if res.get('error'):
        click.echo(f"Error: {res['error']}")
    else:
        out = res.get('output') or ""
        click.echo(out)
