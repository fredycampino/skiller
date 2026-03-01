from typing import Any


class InternalTools:
    def call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "internal.notify":
            return {"ok": True, "notified": True, "message": args.get("message", "")}
        if tool_name == "internal.set_context":
            return {"ok": True, "key": args.get("key"), "value": args.get("value")}
        if tool_name == "internal.wait_webhook":
            return {"ok": True, "wait_key": args.get("wait_key"), "match": args.get("match", {})}
        raise ValueError(f"Unknown internal tool: {tool_name}")
