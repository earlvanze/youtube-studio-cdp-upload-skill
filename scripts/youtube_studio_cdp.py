#!/usr/bin/env python3
"""Small CDP helper for an existing authenticated YouTube Studio tab.

No credentials, browser launch, or publication decisions are built into this
script. It evaluates caller-supplied page expressions, attaches a caller-
supplied existing file to the active Studio upload dialog, or proves a public
watch page plays (`watch VIDEO_ID`).
"""
from __future__ import annotations
import argparse, json, os, sys, time
from urllib.request import urlopen
from websocket import create_connection

ENDPOINT = "http://127.0.0.1:9222/json/list"
VERSION = "http://127.0.0.1:9222/json/version"

def studio_ws():
    with urlopen(ENDPOINT, timeout=5) as response:
        tabs = json.load(response)
    tab = next((t for t in tabs if t.get("type") == "page" and t.get("url", "").startswith("https://studio.youtube.com/")), None)
    if not tab:
        raise RuntimeError("No existing YouTube Studio page is available through CDP")
    # suppress_origin: Brave rejects the websocket-client default Origin header (403) unless launched with
    # --remote-allow-origins; omitting the header attaches without restarting the browser.
    return create_connection(tab["webSocketDebuggerUrl"].replace("127.0.0.1:9222", "localhost:9222"), timeout=60, suppress_origin=True)

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
    if not node_id:
        button = cdp.evaluate('(() => { const b=document.querySelector("#select-button[aria-label*=Upload file i]"); if(!b) return false; b.scrollIntoView({block:"center"}); const r=b.getBoundingClientRect(); b.dispatchEvent(new MouseEvent("mousedown",{bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2})); b.dispatchEvent(new MouseEvent("mouseup",{bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2})); return true; })()')
        if not button: raise RuntimeError("Studio upload file input was not found")
        time.sleep(1)
        node_id = cdp.call("DOM.querySelector", {"nodeId": root, "selector": "input[type=file]"})["nodeId"]
        if not node_id: raise RuntimeError("Studio upload picker did not expose file input")
    cdp.call("DOM.setFileInputFiles", {"files": [path], "nodeId": node_id})
    return {"attached": path}

def watch(video_id, timeout=120):
    """Public-playback proof in one task-created tab: background (the operator's view is untouched), with focus
    emulated, because Brave/Chrome defer media loading in background tabs (video.duration stays NaN, readyState 0).
    Mutes and presses play, polls until duration is finite, readyState >= 2 and currentTime advances, then closes
    only the tab it created."""
    with urlopen(VERSION, timeout=5) as response:
        ws = create_connection(json.load(response)["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
    n = 0
    def call(method, params=None, session=None):
        nonlocal n
        n += 1
        req = {"id": n, "method": method, "params": params or {}}
        if session: req["sessionId"] = session
        ws.send(json.dumps(req))
        while True:
            reply = json.loads(ws.recv())
            if reply.get("id") == n:
                if "error" in reply: raise RuntimeError(f"{method}: {reply['error']}")
                return reply["result"]
    target = call("Target.createTarget", {"url": "about:blank", "background": True})["targetId"]
    probe = """(() => { const v = document.querySelector('video.html5-main-video, video'); const txt = document.body ? document.body.innerText : '';
      if (v && v.paused) { v.muted = true; v.play().catch(() => {}); const b = document.querySelector('.ytp-large-play-button, .ytp-play-button'); b && b.click(); }
      return JSON.stringify({ title: document.title, duration: v ? v.duration : null, readyState: v ? v.readyState : null, currentTime: v ? v.currentTime : null,
        unavailable: /Video unavailable|This video is private|has been removed|isn't available/i.test(txt) }); })()"""
    result, first_t = None, None
    try:
        session = call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        call("Runtime.enable", session=session); call("Page.enable", session=session)
        call("Emulation.setFocusEmulationEnabled", {"enabled": True}, session)
        call("Page.navigate", {"url": f"https://www.youtube.com/watch?v={video_id}"}, session)
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(3)
            r = call("Runtime.evaluate", {"expression": probe, "returnByValue": True, "userGesture": True}, session)
            result = json.loads(r["result"]["value"])
            ct = result.get("currentTime") or 0
            if first_t is None and ct: first_t = ct
            ok = (result["duration"] or 0) > 0 and (result["readyState"] or 0) >= 2 and not result["unavailable"]
            if ok and first_t is not None and ct > first_t: break
    finally:
        call("Target.closeTarget", {"targetId": target})
        ws.close()
    result["advancing"] = first_t is not None and (result.get("currentTime") or 0) > first_t
    result["plays"] = bool((result["duration"] or 0) > 0 and (result["readyState"] or 0) >= 2 and not result["unavailable"] and result["advancing"])
    result["video_id"], result["checked_at"] = video_id, time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return result

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    e = commands.add_parser("eval", help="Evaluate a safe UI-state expression in the Studio tab")
    e.add_argument("expression")
    a = commands.add_parser("attach", help="Attach one existing local file to Studio's open upload picker")
    a.add_argument("path")
    w = commands.add_parser("watch", help="Prove the public watch page plays (own background tab, closed afterwards)")
    w.add_argument("video_id")
    w.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.command == "watch":
        out = watch(args.video_id, args.timeout)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(0 if out["plays"] else 1)
    cdp = CDP()
    try:
        output = cdp.evaluate(args.expression) if args.command == "eval" else attach(cdp, args.path)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        cdp.ws.close()
if __name__ == "__main__": main()
