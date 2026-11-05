"""
Management command to compare environment variable names against .env.production.example.

Audits configuration readiness without ever printing, logging, or exposing variable values.

Usage:
    python manage.py check_env
    python manage.py check_env --file /path/to/.env
"""

import os
import re
from pathlib import Path
from typing import List, Set

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Compare variable names in the active environment or .env file with "
        ".env.production.example. Never prints or logs values."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            "-f",
            dest="env_file",
            default=None,
            help="Path to the .env file to inspect. Defaults to .env in repository root.",
        )
        parser.add_argument(
            "--template",
            "-t",
            dest="template_file",
            default=None,
            help="Path to .env.production.example template file.",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR).resolve()
        # Determine template location
        template_opt = options.get("template_file")
        if template_opt:
            template_path = Path(template_opt).resolve()
        else:
            candidates = [
                base_dir / ".env.production.example",
                base_dir.parent / ".env.production.example",
                Path.cwd() / ".env.production.example",
            ]
            template_path = next((p for p in candidates if p.exists()), None)

        if not template_path or not template_path.exists():
            self.stderr.write(
                self.style.ERROR(
                    "Template file .env.production.example not found. "
                    "Specify location using --template <path>."
                )
            )
            return

        # Determine target file
        env_file_opt = options.get("env_file")
        if env_file_opt:
            target_env_file = Path(env_file_opt)
        else:
            env_candidates = [
                base_dir / ".env",
                base_dir.parent / ".env",
                Path("/home") / os.environ.get("USER", "") / "fitgate_env" / ".env",
                Path.cwd() / ".env",
            ]
            target_env_file = next((p for p in env_candidates if p.exists()), None)

        template_vars = self._parse_variable_names(template_path)
        configured_vars: Set[str] = set()

        if target_env_file and target_env_file.exists():
            configured_vars.update(self._parse_variable_names(target_env_file))
            source_desc = f"file: {target_env_file.name}"
        else:
            # Fall back to inspecting os.environ for template keys
            configured_vars.update(
                var
                for var in template_vars
                if var in os.environ and os.environ[var] != ""
            )
            source_desc = "active os.environ"

        self.stdout.write("=" * 70)
        self.stdout.write("  FitGate Environment Variable Names Audit")
        self.stdout.write("=" * 70)
        self.stdout.write(
            f"Template : {template_path.name} ({len(template_vars)} variables)"
        )
        self.stdout.write(f"Inspected: {source_desc}\n")
        self.stdout.write(
            "Auditing variable names (values are never inspected or printed):\n"
        )

        missing_vars: List[str] = []
        present_vars: List[str] = []

        for var_name in sorted(template_vars):
            # Check either target env file or os.environ
            is_present = var_name in configured_vars or (
                var_name in os.environ and os.environ[var_name] != ""
            )
            if is_present:
                present_vars.append(var_name)
                self.stdout.write(f"  [PRESENT] {var_name}")
            else:
                missing_vars.append(var_name)
                self.stdout.write(self.style.WARNING(f"  [MISSING] {var_name}"))

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            f"Summary: {len(present_vars)} present, {len(missing_vars)} missing."
        )

        if missing_vars:
            self.stdout.write(
                self.style.WARNING(
                    f"Warning: {len(missing_vars)} variable(s) from .env.production.example "
                    "are missing in the target configuration."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "All template variables are defined in the environment configuration."
                )
            )

    def _parse_variable_names(self, file_path: Path) -> Set[str]:
        """Extract variable names from a .env file, ignoring comments and blank lines."""
        var_names = set()
        pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    match = pattern.match(line)
                    if match:
                        var_names.add(match.group(1))
        except Exception:
            pass
        return var_names
