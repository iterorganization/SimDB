"""Render the CLI reference page.

Reads ``cli.md.in`` and replaces every ``{{ command }}`` placeholder with the
captured ``simdb <command> --help`` output (recursing into sub-commands). The
result is written to ``reference/cli.md``.

This runs automatically at documentation build time (see ``conf.py``), so the
CLI reference always matches the installed version of SimDB. It can also be run
by hand from the ``docs/`` directory:

    python generate_cli_docs.py
"""

import subprocess
from pathlib import Path

DOCS_DIR = Path(__file__).parent.resolve()
TEMPLATE = DOCS_DIR / "cli.md.in"
OUTPUT = DOCS_DIR / "reference" / "cli.md"


def run_command(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"`{' '.join(args)}` failed with exit status {exc.returncode}:\n"
            f"{exc.stderr.strip()}"
        ) from exc
    return result.stdout


def extract_command(line: str) -> str:
    return line.strip().removeprefix("{{").removesuffix("}}").strip()


def extract_sub_commands(output: str) -> list[str]:
    in_commands = False
    sub_commands = []
    for line in output.split("\n"):
        if in_commands:
            # Lines indented further than the command column are continuations
            # of the previous command's help text.
            if line and not line.startswith("   "):
                sub_commands.append(line.split()[0])
        if line == "Commands:":
            in_commands = True
    return sub_commands


def generate_block(output: str) -> str:
    return f"\n```text\n{output.strip()}\n```\n"


def process_cmd(cmd: str) -> str:
    output = run_command(["simdb", *cmd.split(), "--help"])
    sub_commands = extract_sub_commands(output) if cmd else []

    text = generate_block(output)
    for sub_command in sub_commands:
        text += "\n" + process_cmd(f"{cmd} {sub_command}")
    return text


def process_line(line: str) -> str:
    return process_cmd(extract_command(line))


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATE) as f_in, open(OUTPUT, "w") as f_out:
        for line in f_in:
            if line.startswith("{{"):
                f_out.write(process_line(line))
            else:
                f_out.write(line)


if __name__ == "__main__":
    main()
