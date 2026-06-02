"""Minimal, dependency-free human review dashboard (Module 7).

The human is a quality gate only: watch the QA-passed video, read the QA report,
and Approve or Reject (with an optional note). Approve triggers the publishing
queue; Reject sends the episode back to the agents. Built on ``http.server`` so
it runs with no extra packages; swap for the suggested Next.js front end in
production by pointing it at the same JSON endpoints.

Endpoints:
  GET  /                      dashboard HTML (review queue)
  GET  /api/queue             review queue refs
  GET  /api/episode/<ref>     episode summary + QA report
  POST /api/episode/<ref>/approve
  POST /api/episode/<ref>/reject   body: {"note": "..."}
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>VGEN-SWARM Review</title>
<style>
 body{font:15px/1.5 system-ui;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:16px 20px;background:#171a21;font-weight:600}
 .wrap{max-width:760px;margin:0 auto;padding:16px}
 .card{background:#171a21;border:1px solid #2a2f3a;border-radius:10px;padding:16px;margin:12px 0}
 .ref{font-weight:600;font-size:18px}
 .ok{color:#5fd08a}.fail{color:#ff7a7a}
 button{font:inherit;border:0;border-radius:8px;padding:10px 16px;margin-right:8px;cursor:pointer}
 .approve{background:#2e7d52;color:#fff}.reject{background:#7d2e2e;color:#fff}
 .video{width:100%;aspect-ratio:9/16;max-height:60vh;background:#000;border-radius:8px}
 ul{margin:8px 0;padding-left:18px}small{color:#9aa4b2}
 input{font:inherit;padding:8px;width:60%;border-radius:6px;border:1px solid #2a2f3a;background:#0f1115;color:#e6e6e6}
</style></head><body>
<header>VGEN-SWARM — Human Review Queue</header>
<div class=wrap id=app>loading…</div>
<script>
async function j(u,o){const r=await fetch(u,o);return r.json()}
async function load(){
 const q=await j('/api/queue');const app=document.getElementById('app');
 if(!q.queue.length){app.innerHTML='<div class=card>No episodes awaiting review. 🎬</div>';return}
 app.innerHTML='';
 for(const ref of q.queue){
  const e=await j('/api/episode/'+ref);
  const qa=e.qa||{checks:[]};
  const checks=qa.checks.map(c=>`<li class=${c.passed?'ok':'fail'}>${c.passed?'✓':'✗'} ${c.name} <small>${c.detail||''}</small></li>`).join('');
  const d=document.createElement('div');d.className='card';
  d.innerHTML=`<div class=ref>${ref} — ${e.title||''}</div>
   <video class=video controls poster=""><source src="">(mock video — ${ref})</video>
   <div>QA: <b class=${qa.passed?'ok':'fail'}>${qa.passed?'PASS':'FAIL'}</b></div>
   <ul>${checks}</ul>
   <div>Platforms: <small>${(e.platforms||[]).join(', ')}</small></div>
   <div style=margin-top:12px>
     <button class=approve onclick="act('${ref}','approve')">Approve</button>
     <button class=reject onclick="act('${ref}','reject')">Reject</button>
     <input id="note_${ref}" placeholder="optional rejection note">
   </div>`;
  app.appendChild(d);
 }
}
async function act(ref,kind){
 const note=(document.getElementById('note_'+ref)||{}).value||'';
 await j('/api/episode/'+ref+'/'+kind,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({note})});
 load();
}
load();
</script></body></html>"""


def build_app(orchestrator):
    """Build a request handler class bound to an orchestrator."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._send(200, _PAGE, "text/html; charset=utf-8")
            if path == "/api/queue":
                return self._send(200, json.dumps({"queue": orchestrator.review_queue()}))
            if path.startswith("/api/episode/"):
                ref = path.split("/")[3]
                return self._send(200, json.dumps(orchestrator.episode_summary(ref)))
            return self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            path = urlparse(self.path).path
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "episode":
                ref, action = parts[2], parts[3]
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                try:
                    if action == "approve":
                        records = orchestrator.approve(ref)
                        return self._send(200, json.dumps({"published": records}))
                    if action == "reject":
                        orchestrator.reject(ref, body.get("note", ""))
                        return self._send(200, json.dumps({"rejected": ref}))
                except Exception as exc:  # noqa: BLE001
                    return self._send(400, json.dumps({"error": str(exc)}))
            return self._send(404, json.dumps({"error": "not found"}))

    return Handler


class ReviewServer:
    def __init__(self, orchestrator, host: str = "127.0.0.1", port: int = 8765):
        self.httpd = ThreadingHTTPServer((host, port), build_app(orchestrator))
        self.host, self.port = host, port

    def serve_forever(self):
        print(f"Review dashboard: http://{self.host}:{self.port}/")
        self.httpd.serve_forever()

    def shutdown(self):
        self.httpd.shutdown()
