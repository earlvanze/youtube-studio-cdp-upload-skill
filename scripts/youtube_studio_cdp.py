#!/usr/bin/env python3
"""Small CDP helper for an existing authenticated YouTube Studio tab.

No credentials, browser launch, or publication decisions are built into this
script. It evaluates caller-supplied page expressions or attaches a caller-
supplied existing file to the active Studio upload dialog.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from urllib.request import urlopen
from websocket import create_connection

ENDPOINT = "http://127.0.0.1:9222/json/list"

def studio_ws():
    with urlopen(ENDPOINT, timeout=5) as response:
        tabs = json.load(response)
    tab = next((t for t in tabs if t.get("type") == "page" and t.get("url", "").startswith("https://studio.youtube.com/")), None)
    if not tab:
        raise RuntimeError("No existing YouTube Studio page is available through CDP")
    return create_connection(tab["webSocketDebuggerUrl"].replace("127.0.0.1:9222", "localhost:9222"), timeout=60)

class CDP:
    def __init__(self): self.ws, self.id = studio_ws(), 0
    def call(self, method, params=None):
        self.id += 1
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.id:
                if "error" in reply: raise RuntimeError(f"{method}: {reply['error']}")
                return reply["result"]
    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True, "userGesture": True})
        if "exceptionDetails" in result: raise RuntimeError(result["exceptionDetails"].get("text", "Page evaluation failed"))
        return result.get("result", {}).get("value")

def attach(cdp, path):
    path = os.path.abspath(path)
    if not os.path.isfile(path): raise RuntimeError(f"Not a file: {path}")
    cdp.call("DOM.enable")
    root = cdp.call("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
    node_id = cdp.call("DOM.querySelector", {"nodeId": root, "selector": "input[type=file]"})["nodeId"]
    if not node_id: raise RuntimeError("Studio upload file input was not found")
    cdp.call("DOM.setFileInputFiles", {"files": [path], "nodeId": node_id})
    return {"attached": path}

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    e = commands.add_parser("eval", help="Evaluate a safe UI-state expression in the Studio tab")
    e.add_argument("expression")
    a = commands.add_parser("attach", help="Attach one existing local file to Studio's open upload picker")
    a.add_argument("path")
    args = parser.parse_args()
    cdp = CDP()
    try:
        output = cdp.evaluate(args.expression) if args.command == "eval" else attach(cdp, args.path)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        cdp.ws.close()
if __name__ == "__main__": main()
