"""
CLARA-AGI Web UI — giao diện web nhẹ (Flask). Tự động mở trình duyệt.
Cần: pip install flask
"""
import json, time
from pathlib import Path


def _import_flask():
    try:
        from flask import Flask, request, jsonify, render_template_string
        return Flask, request, jsonify, render_template_string
    except ImportError:
        return None, None, None, None

Flask = request = jsonify = render_template_string = None


INDEX_HTML = r"""<!doctype html>
<html lang="vi"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🧬 CLARA-AGI</title>
<style>
:root{--bg:#0b1020;--panel:#121933;--me:#4f8cff;--ai:#1c294d;--text:#e7ecff;--muted:#8c98bf}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{padding:14px 18px;background:linear-gradient(90deg,#11205a,#0b1020);display:flex;align-items:center;gap:12px;border-bottom:1px solid #233058}
header .dot{width:10px;height:10px;border-radius:50%;background:#3cd67f;box-shadow:0 0 10px #3cd67f}
.status{margin-left:auto;font-size:13px;color:var(--muted)}
main{max-width:880px;margin:0 auto;padding:18px;display:flex;flex-direction:column;gap:10px;height:calc(100vh - 130px)}
#chat{flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:80%;padding:10px 14px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word;line-height:1.45}
.msg.me{align-self:flex-end;background:var(--me)}
.msg.ai{align-self:flex-start;background:var(--ai);border:1px solid #243563}
.meta{font-size:11px;color:var(--muted);margin-top:4px}
form{display:flex;gap:8px;padding:10px;background:var(--panel);border-radius:14px;border:1px solid #243563}
textarea{flex:1;background:#0a0f23;color:var(--text);border:none;border-radius:10px;padding:10px;resize:none;height:52px;font-size:15px;outline:none;font-family:inherit}
button{background:linear-gradient(135deg,#4f8cff,#8a5cff);border:none;color:white;border-radius:10px;padding:0 18px;font-weight:600;cursor:pointer;font-size:15px}
button:hover{opacity:.9}
button:disabled{opacity:.5}
.tools{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:12px;padding:4px 10px;border-radius:20px;background:#1c294d;color:var(--muted);border:1px solid #243563;cursor:pointer}
.chip:hover{background:#263663;color:#fff}
.thinking{opacity:.6;font-style:italic}
footer{text-align:center;color:var(--muted);font-size:12px;padding:8px}
</style></head><body>
<header>
  <div class="dot" id="dot"></div>
  <strong>🧬 CLARA-AGI v1.1</strong>
  <span class="status" id="status">đang tải…</span>
</header>
<main>
  <div class="tools">
    <span class="chip" onclick="send('commands')">/commands</span>
    <span class="chip" onclick="send('status')">/status</span>
    <span class="chip" onclick="send('dream')">/dream</span>
    <span class="chip" onclick="send('bạn là ai')">bạn là ai?</span>
    <span class="chip" onclick="send('tính 15!')">tính 15!</span>
  </div>
  <div id="chat"></div>
  <form onsubmit="submitMsg(event)">
    <textarea id="inp" placeholder="Nói gì đó với CLARA... (Enter gửi, Shift+Enter xuống dòng)" autofocus></textarea>
    <button id="btn">Gửi</button>
  </form>
</main>
<footer>Local-only · không gửi dữ liệu đi đâu · 100% chạy trên máy bạn</footer>
<script>
const chat=document.getElementById('chat');
const inp=document.getElementById('inp');
const btn=document.getElementById('btn');
const stat=document.getElementById('status');

function addMsg(role, text, meta){
  const d=document.createElement('div');
  d.className='msg '+role;
  d.textContent=text;
  if(meta){const m=document.createElement('div');m.className='meta';m.textContent=meta;d.appendChild(m)}
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
  return d;
}

async function submitMsg(e){
  e.preventDefault();
  const t=inp.value.trim();if(!t)return;
  inp.value='';btn.disabled=true;
  addMsg('me',t);
  const think=addMsg('ai','… đang suy nghĩ …','');think.classList.add('thinking');
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:t})});
    const j=await r.json();
    think.remove();
    addMsg('ai',j.reply||'(không có trả lời)', (j.elapsed_ms?('⏱️ '+j.elapsed_ms+'ms · '+j.backend):''));
    updateStatus(j.status);
  }catch(err){think.remove();addMsg('ai','❌ Lỗi: '+err)}
  btn.disabled=false;inp.focus();
}

function send(t){inp.value=t;submitMsg(new Event('submit'))}

async function refreshStatus(){
  try{
    const r=await fetch('/status');const j=await r.json();updateStatus(j);
  }catch(e){}
}
function updateStatus(s){
  if(!s)return;
  const m=s.memory||{};
  stat.textContent=`🧠 ${s.brain?.backend||''} · 💾 ${m.episodes||0}ep / ${m.semantics||0}facts / ${m.procedures||0}procs · ${s.turns||0} turns · ${s.age_hours||0}h`;
}
inp.addEventListener('keydown',e=>{
  if(e.key==='Enter' && !e.shiftKey){e.preventDefault();submitMsg(e)}
});
refreshStatus();setInterval(refreshStatus,5000);
</script></body></html>
"""


def create_app(agi):
    Flask, request, jsonify, render_template_string = _import_flask()
    if Flask is None:
        raise ImportError("Chưa cài flask. Hãy chạy: pip install flask")
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(INDEX_HTML)

    @app.route("/chat", methods=["POST"])
    def chat_route():
        data = request.get_json(force=True) or {}
        msg = (data.get("msg") or "").strip()
        t0 = time.time()
        reply = agi.chat(msg)
        elapsed = int((time.time() - t0) * 1000)
        return jsonify({"reply": reply, "elapsed_ms": elapsed,
                        "backend": agi.brain.status()["backend"],
                        "status": agi.status()})

    @app.route("/status")
    def status_route():
        return jsonify(agi.status())

    # tự mở trình duyệt
    import threading, webbrowser
    def _open():
        import time as _t; _t.sleep(1.0)
        try: webbrowser.open("http://127.0.0.1:5000/")
        except Exception: pass
    threading.Thread(target=_open, daemon=True).start()

    return app
