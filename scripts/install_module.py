#!/usr/bin/env python3
"""Cross-platform automation for installing or updating this Odoo module."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODULE = MODULE_ROOT.name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install, update, or validate an Odoo module in a repeatable way.",
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Target PostgreSQL database name.",
    )
    parser.add_argument(
        "--action",
        choices=("install", "update"),
        default="install",
        help="Use install for a fresh database and update for an existing one.",
    )
    parser.add_argument(
        "--module",
        default=DEFAULT_MODULE,
        help=f"Module to process. Defaults to {DEFAULT_MODULE}.",
    )
    parser.add_argument(
        "--odoo-root",
        help="Odoo installation root that contains the server directory.",
    )
    parser.add_argument(
        "--odoo-python",
        help="Python executable used to launch odoo-bin.",
    )
    parser.add_argument(
        "--odoo-bin",
        help="Path to odoo-bin.",
    )
    parser.add_argument(
        "--config",
        help="Path to odoo.conf.",
    )
    parser.add_argument(
        "--test-enable",
        action="store_true",
        help="Run the Odoo test suite while installing or updating the module.",
    )
    parser.add_argument(
        "--log-level",
        help="Override the Odoo log level. Defaults to test when --test-enable is used.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Pass an extra argument through to Odoo. Repeat as needed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved Odoo command without executing it.",
    )
    parser.set_defaults(no_http=True, without_demo=True)
    parser.add_argument(
        "--no-http",
        dest="no_http",
        action="store_true",
        help="Disable the HTTP server during automated runs (default).",
    )
    parser.add_argument(
        "--with-http",
        dest="no_http",
        action="store_false",
        help="Keep the HTTP server enabled.",
    )
    parser.add_argument(
        "--without-demo",
        dest="without_demo",
        action="store_true",
        help="Skip demo data during automated runs (default).",
    )
    parser.add_argument(
        "--with-demo",
        dest="without_demo",
        action="store_false",
        help="Allow demo data to be loaded.",
    )
    return parser.parse_args()


def resolve_optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def find_odoo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "server" / "odoo-bin").exists():
            return candidate
    return None


def discover_paths(args: argparse.Namespace) -> tuple[Path | None, Path, Path | None, Path]:
    odoo_root = resolve_optional_path(args.odoo_root) or find_odoo_root(MODULE_ROOT)
    odoo_bin = resolve_optional_path(args.odoo_bin)
    config = resolve_optional_path(args.config)
    odoo_python = resolve_optional_path(args.odoo_python)

    if odoo_root:
        if not odoo_bin:
            candidate = odoo_root / "server" / "odoo-bin"
            if candidate.exists():
                odoo_bin = candidate
        if not config:
            candidate = odoo_root / "server" / "odoo.conf"
            if candidate.exists():
                config = candidate
        if not odoo_python and os.name == "nt":
            candidate = odoo_root / "python" / "python.exe"
            if candidate.exists():
                odoo_python = candidate

    if not odoo_bin:
        env_bin = os.getenv("ODOO_BIN")
        if env_bin:
            odoo_bin = Path(env_bin).expanduser().resolve()
    if not config:
        env_config = os.getenv("ODOO_CONFIG")
        if env_config:
            config = Path(env_config).expanduser().resolve()
    if not odoo_python:
        env_python = os.getenv("ODOO_PYTHON")
        if env_python:
            odoo_python = Path(env_python).expanduser().resolve()

    if not odoo_bin:
        raise SystemExit(
            "Could not find odoo-bin automatically. Pass --odoo-bin or set ODOO_BIN."
        )

    if not odoo_bin.exists():
        raise SystemExit(f"odoo-bin was not found: {odoo_bin}")

    if config and not config.exists():
        raise SystemExit(f"Config file was not found: {config}")

    resolved_python = odoo_python or Path(sys.executable).resolve()
    if not resolved_python.exists():
        raise SystemExit(
            f"Python executable was not found: {resolved_python}. Pass --odoo-python."
        )

    return odoo_root, odoo_bin, config, resolved_python


def build_command(
    args: argparse.Namespace,
    odoo_bin: Path,
    config: Path | None,
    odoo_python: Path,
) -> list[str]:
    install_flag = "-i" if args.action == "install" else "-u"
    command = [str(odoo_python), str(odoo_bin)]

    if config:
        command.extend(["-c", str(config)])

    command.extend([
        "-d",
        args.database,
        install_flag,
        args.module,
        "--stop-after-init",
    ])

    if args.no_http:
        command.append("--no-http")
    if args.without_demo:
        command.append("--without-demo=all")
    if args.test_enable:
        command.append("--test-enable")

    log_level = args.log_level or ("test" if args.test_enable else None)
    if log_level:
        command.extend(["--log-level", log_level])

    command.extend(args.extra_arg)
    return command


def format_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(shlex.quote(part) for part in command)


def main() -> int:
    args = parse_args()
    odoo_root, odoo_bin, config, odoo_python = discover_paths(args)
    command = build_command(args, odoo_bin, config, odoo_python)

    print(f"Module root : {MODULE_ROOT}")
    print(f"Odoo root   : {odoo_root or 'not auto-detected'}")
    print(f"odoo-bin    : {odoo_bin}")
    print(f"Python      : {odoo_python}")
    print(f"Config      : {config or 'not provided'}")
    print(f"Database    : {args.database}")
    print(f"Action      : {args.action}")
    print(f"Module      : {args.module}")
    print(f"Command     : {format_command(command)}")

    if args.dry_run:
        return 0

    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())