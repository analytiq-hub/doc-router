"""Registry of org routes and required capabilities (phase 3 regression guard)."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_DIR = REPO_ROOT / "packages" / "python" / "app" / "routes"

ALLOWED_ORG_DEPS = {
    "require_org_documents_read",
    "require_org_documents_write",
    "require_org_runs_execute",
    "require_org_config_read",
    "require_org_config_write",
    "require_org_admin_capability",
    "get_org_admin_user",
    "get_org_user",  # membership-only (e.g. permissions/me, org API tokens)
    "get_admin_user",  # platform sysadmin-only org routes (e.g. org LLM test chat)
    "get_org_billing_read_user",  # org.admin or platform sysadmin (billing read)
}

DEP_PATTERN = re.compile(
    r"Depends\((require_org_[a-z_]+|get_org_user|get_org_admin_user|get_org_billing_read_user|get_admin_user)\)"
)

ORG_ROUTE_PATTERN = re.compile(
    r"@\w+_router\.(get|post|put|delete|patch)\([^)]*/v0/orgs/\{organization_id\}"
)

FORBIDDEN_ORG_AUTH = ("get_admin_or_org_user",)


def test_org_routes_declare_capability_dependencies():
    """Org-scoped handlers must not use bare get_org_user except where listed."""
    violations: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        text = path.read_text()
        if "/v0/orgs/" not in text and "organization_id" not in text:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if "Depends(get_org_user)" in line and path.name not in {
                "org_permissions.py",
                "token.py",
            }:
                violations.append(f"{path.name}:{i}: {line.strip()}")
            m = DEP_PATTERN.search(line)
            if m and m.group(1) not in ALLOWED_ORG_DEPS:
                violations.append(f"{path.name}:{i}: unknown dep {m.group(1)}")
            for forbidden in FORBIDDEN_ORG_AUTH:
                if forbidden in line and ORG_ROUTE_PATTERN.search(
                    "\n".join(text.splitlines()[max(0, i - 5) : i])
                ):
                    violations.append(f"{path.name}:{i}: {forbidden} on org route")
    assert not violations, "Org routes missing capability deps:\n" + "\n".join(violations)


def test_org_scoped_handlers_use_capability_dependency():
    """Each /v0/orgs/{organization_id} handler should declare a capability dep on the signature."""
    violations: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if not ORG_ROUTE_PATTERN.search(line):
                continue
            window = "\n".join(lines[i : min(i + 25, len(lines))])
            if "async def" not in window:
                continue
            if not DEP_PATTERN.search(window):
                violations.append(f"{path.name}:{i + 1}: org route handler missing capability Depends")
    assert not violations, "Org handlers without capability deps:\n" + "\n".join(violations)
