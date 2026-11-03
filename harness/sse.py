"""OpenAI-compatible SSE reconstruction, including reasoning and final usage."""
import json
import urllib.error


def parse_sse(response, on_progress=None):
    model = None
    content, reasoning = [], []
    tools = {}
    usage = None
    finish = None
    done = False
    seen = 0

    def consume(raw):
        nonlocal model, usage, finish, done, seen
        if raw.strip() == "[DONE]":
            done = True
            return
        try:
            chunk = json.loads(raw)
        except (TypeError, ValueError):
            raise urllib.error.URLError("Malformed/incomplete SSE JSON") from None
        if chunk.get("error"):
            error = chunk["error"]
            try:
                code = int(error.get("code", 500)) if isinstance(error, dict) else 500
            except (TypeError, ValueError):
                code = 500
            raise urllib.error.HTTPError("https://ai.nube-api.com/v1/chat/completions", code,
                                         "Provider SSE error", None, None)
        model = chunk.get("model") or model
        if chunk.get("usage") is not None:
            usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            if choice.get("index", 0) != 0:
                continue
            delta = choice.get("delta") or {}
            if isinstance(delta.get("content"), str):
                content.append(delta["content"])
            thought = delta.get("reasoning_content", delta.get("reasoning"))
            if isinstance(thought, str):
                reasoning.append(thought)
            for call in delta.get("tool_calls") or []:
                index = call.get("index", 0)
                target = tools.setdefault(index, {"id": [], "name": [], "arguments": [], "type": "function"})
                if call.get("id"):
                    target["id"].append(call["id"])
                if call.get("type"):
                    target["type"] = call["type"]
                function = call.get("function") or {}
                if function.get("name"):
                    target["name"].append(function["name"])
                if function.get("arguments") is not None:
                    target["arguments"].append(function["arguments"])
            if choice.get("finish_reason") is not None:
                finish = choice["finish_reason"]
        seen += 1
        if on_progress:
            on_progress(seen)

    lines = []
    for raw_line in response:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line = line.rstrip("\r\n")
        if line == "":
            if lines:
                consume("\n".join(lines))
                lines = []
            if done:
                break
        elif line.startswith("data:"):
            lines.append(line[5:].lstrip(" "))
        # Comments/heartbeats/event/id fields deliberately do not enter content.
    if lines and not done:
        consume("\n".join(lines))
    if not done and (finish is None or usage is None):
        raise urllib.error.URLError("SSE stream disconnected before complete response")
    message = {"role": "assistant", "content": "".join(content) or None}
    if reasoning:
        message["reasoning_content"] = "".join(reasoning)
    if tools:
        message["tool_calls"] = [{"id": "".join(value["id"]), "type": value["type"],
            "function": {"name": "".join(value["name"]), "arguments": "".join(value["arguments"])}}
            for index, value in sorted(tools.items())]
    return {"model": model, "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage}
