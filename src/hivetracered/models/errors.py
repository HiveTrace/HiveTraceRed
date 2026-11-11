"""Structured transport errors, including explicit response-format rejection."""

import re


def request_error(exc):
    """Preserve machine-readable SDK details alongside the legacy error string."""
    result = {"content": "", "error": str(exc), "error_type": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            # SDK .body can unwrap "error" and lose sibling fields (Venice
            # details/issues). Preserve the complete HTTP envelope when present.
            body = response.json()
        except (ValueError, RuntimeError):
            pass
    if status is not None:
        result["status_code"] = status
    if isinstance(body, dict):
        result["error_body"] = body
    return result


def _error_nodes(value):
    if isinstance(value, dict):
        yield value
        children = value.values()
    elif isinstance(value, list):
        children = value
    else:
        yield value
        return
    for item in children:
        if isinstance(value, list) or isinstance(item, (dict, list)):
            yield from _error_nodes(item)


def _invalid_error(node):
    code = str(node.get("code") or "").lower()
    if any(word in code for word in ("schema", "quota", "billing", "credit", "context", "token", "auth", "permission")):
        return True
    param = node.get("param")
    path = node.get("path")
    if isinstance(path, list) and path:
        param = ".".join(map(str, path))
    return bool(param) and param not in ("response_format", "response_format.type", "response_format.json_schema")


def _error_messages(value):
    """Collect explicit messages; schema and unrelated parameter errors veto fallback."""
    messages = []
    invalid = False
    for node in _error_nodes(value):
        if isinstance(node, dict):
            invalid = invalid or _invalid_error(node)
            messages.extend(node.get(key) for key in ("message", "error") if isinstance(node.get(key), str))
        elif isinstance(node, str):
            messages.append(node)
    return messages, invalid


def is_response_format_unsupported(error) -> bool:
    """Conservative full-message matching; unrelated errors always stay fatal.

    Code/param metadata wins over a generic message. Unknown provider phrasing
    deliberately does not trigger fallback.
    """
    if not isinstance(error, dict):
        error = request_error(error)
    kind = str(error.get("error_type", ""))
    status = error.get("status_code")
    payload = error
    if status is not None and status not in (400, 422):
        return False
    if kind not in ("BadRequestError", "UnprocessableEntityError", "UnsupportedResponseFormat"):
        return False
    messages, invalid = _error_messages(payload)
    if invalid:
        return False
    target = (
        r"[\"']?(?:response_format[\"']?(?:(?:\s+of\s+type\s+|\s+)[\"']?json_schema[\"']?)?"
        r"|json_schema[\"']?|structured outputs?[\"']?)"
    )
    suffix = r"(?:\s+(?:with|for|by|on)\s+(?:(?:this|the|selected)\s+)?(?:model|endpoint))?"
    patterns = (
        rf"(?:invalid parameter:\s*)?(?:the\s+)?{target}(?:\s+format)?\s+(?:(?:is|are)\s+)?"
        rf"(?:not supported|unsupported|not available|not permitted|not allowed){suffix}",
        rf"(?:(?:this|the|selected)\s+)?model(?:\s+[\"']?[\w/.:_-]+[\"']?)?\s+"
        rf"(?:does not support|doesn't support)\s+{target}",
        r"(?:unsupported|unknown|unrecognized)\s+(?:request\s+)?(?:argument|parameter)"
        r"\s*[:=]?\s*[\"']?response_format[\"']?",
        r"unsupported\s+[\"']?response_format[\"']?(?:\s+type:\s*[\"']?json_schema[\"']?)?",
    )
    return any(re.fullmatch(pattern, message.strip().lower().rstrip(".!"))
               for message in messages for pattern in patterns)
