"""Read a project's package.json and group its scripts into actions: dev, migrations, deploys, wrangler, others."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Action:
    key: str
    label: str
    command: str
    target: str = ""      # migration: local/staging/remote/production, deploy: preview/production
    danger: bool = False  # ask for confirmation before running


@dataclass
class ProjectInfo:
    path: str
    name: str
    version: str = ""
    dev: Action | None = None
    migrations: list[Action] = field(default_factory=list)
    deploys: list[Action] = field(default_factory=list)
    scripts: list[Action] = field(default_factory=list)
    wrangler: bool = False
    error: str = ""


TARGETS = {"local": "Local", "staging": "Staging", "remote": "Remote", "production": "Production"}
DEPLOY_TARGETS = {"preview": "Preview", "production": "Production"}
ALIAS = re.compile(r"^npm run ([\w:.\-]+)$")
DEPLOY_COMMAND = re.compile(r"wrangler (deploy|preview)(?!\s+(delete|secret|base-config))")
DEV_COMMAND = re.compile(r"^(vite|wrangler dev|next dev|nuxt dev|astro dev)(\s|$)")

WRANGLER = {
    "whoami": Action("wrangler:whoami", "wrangler whoami", "npx wrangler whoami"),
    "login": Action("wrangler:login", "wrangler login", "npx wrangler login"),
    "logout": Action("wrangler:logout", "wrangler logout", "npx wrangler logout"),
}


def _script(name: str, label: str | None = None, **kw) -> Action:
    return Action(f"script:{name}", label or name, f"npm run {name}", **kw)


def _migration_target(name: str, command: str) -> str:
    if "--local" in command:
        return "local"
    lower = name.lower()
    if "prod" in lower:
        return "production"
    if "stag" in lower or "preview" in lower:
        return "staging"
    return "remote"


def _deploy_target(name: str, command: str) -> str:
    lower = name.lower()
    if "wrangler preview" in command or "preview" in lower or "stag" in lower:
        return "preview"
    return "production"


def _grouped(scripts: dict[str, str], names: list[str], target_of, labels: dict[str, str],
             danger) -> list[Action]:
    targets = {n: target_of(n, scripts[n]) for n in names}
    order = list(labels)
    actions = []
    for name in sorted(names, key=lambda n: (order.index(targets[n]), n)):
        target = targets[name]
        label = labels[target]
        if list(targets.values()).count(target) > 1:
            label = f"{label} · {name}"
        actions.append(_script(name, label, target=target, danger=danger(target)))
    return actions


def _dev_script(scripts: dict[str, str]) -> str | None:
    if "dev" in scripts:
        return "dev"
    return next((n for n, c in scripts.items() if DEV_COMMAND.match(c.strip())), None)


def detect(path: str) -> ProjectInfo:
    root = Path(path)
    info = ProjectInfo(path=str(root), name=root.name)
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        info.error = "package.json not found."
        return info
    except (OSError, ValueError) as e:
        info.error = f"Cannot read package.json: {e}"
        return info

    info.name = pkg.get("name") or root.name
    info.version = pkg.get("version", "")
    scripts: dict[str, str] = pkg.get("scripts") or {}
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    info.wrangler = "wrangler" in deps or any("wrangler" in c for c in scripts.values())

    dev = _dev_script(scripts)
    if dev:
        info.dev = _script(dev)

    migration_names = [n for n, c in scripts.items() if "migrations apply" in c]
    deploy_names = [n for n, c in scripts.items() if DEPLOY_COMMAND.search(c)]
    # Scripts like "db:remote": "npm run db:production" are just aliases; don't show duplicate buttons.
    grouped = {*migration_names, *deploy_names}
    aliases = {n for n, c in scripts.items() if (m := ALIAS.match(c.strip())) and m.group(1) in grouped}

    info.migrations = _grouped(scripts, migration_names, _migration_target, TARGETS,
                               lambda t: t in ("remote", "production"))
    info.deploys = _grouped(scripts, deploy_names, _deploy_target, DEPLOY_TARGETS, lambda _t: True)

    skip = {dev, *grouped, *aliases}
    info.scripts = [_script(name) for name in scripts if name not in skip]
    return info
