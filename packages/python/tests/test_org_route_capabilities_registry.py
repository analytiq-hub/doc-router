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
    "get_org_user",  # membership-only (e.g. permissions/me)
}

DEP_PATTERN = re.compile(r"Depends\((require_org_[a-z_]+|get_org_user|get_org_admin_user)\)")


def test_org_routes_declare_capability_dependencies():
    """Org-scoped handlers must not use bare get_org_user except where listed."""
    violations: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        text = path.read_text()
        if "/v0/orgs/" not in text and "organization_id" not in text:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if "Depends(get_org_user)" in line and path.name != "org_permissions.py":
                violations.append(f"{path.name}:{i}: {line.strip()}")
            m = DEP_PATTERN.search(line)
            if m and m.group(1) not in ALLOWED_ORG_DEPS:
                violations.append(f"{path.name}:{i}: unknown dep {m.group(1)}")
    assert not violations, "Org routes missing capability deps:\n" + "\n".join(violations)
