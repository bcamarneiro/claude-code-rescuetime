import fnmatch
from typing import Optional

def format_description(template: str, project: str, branch: Optional[str], max_len: int = 255) -> str:
    desc = template.format(project=project, branch=branch or "").strip()
    desc = desc.strip(" ·-").strip()  # tidy dangling separator when branch is empty
    return desc[:max_len]

def is_excluded(project: str, exclude_projects: list) -> bool:
    return any(project == pat or fnmatch.fnmatch(project, pat) for pat in exclude_projects)

def decide(event: str, session: dict, context: dict, config: dict, now: float):
    project = context["project"]
    branch = context["branch"]
    new_session = dict(session)
    new_session["project"] = project
    new_session["branch"] = branch
    new_session["last_activity_at"] = now

    if not config.get("enabled", True):
        return None, new_session
    if is_excluded(project, config.get("exclude_projects", [])):
        return None, new_session
    if event == "SessionEnd":
        return None, new_session

    context_key = "{}@{}".format(project, branch)
    last_context = session.get("last_context")
    last_emit_at = session.get("last_emit_at", 0)
    heartbeat_min = config.get("heartbeat_minutes", 0) or 0

    if context_key != last_context:
        should = True
    elif event != "SessionStart" and heartbeat_min > 0 and (now - last_emit_at) >= heartbeat_min * 60:
        should = True
    else:
        should = False

    if not should:
        return None, new_session

    new_session["last_context"] = context_key
    new_session["last_emit_at"] = now
    desc = format_description(config.get("description_template", "{project} · {branch}"), project, branch)
    return {"description": desc, "source": config.get("source_label", "claude-code")}, new_session
