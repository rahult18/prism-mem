import html as _html
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from prism_mem.config import UI_HOST, UI_PORT

_project_path: str = "."

app = FastAPI(title="Prism Graph UI")


# ── helpers ──────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return _html.escape(str(s))


def _nav(active: str) -> str:
    items = [("Constitution", "/constitution"), ("Graph", "/graph"), ("Memory", "/memory")]
    links = []
    for name, href in items:
        if name == active:
            style = "color:#fff;font-weight:bold;text-decoration:none;"
        else:
            style = "color:#888;text-decoration:none;"
        links.append(f'<a href="{href}" style="{style}">{name}</a>')
    return (
        '<nav style="background:#1a1a2e;padding:10px 20px;font-family:sans-serif;'
        'font-size:14px;display:flex;gap:20px;align-items:center;">'
        '<span style="color:#e94560;font-weight:bold;margin-right:8px;">&#9670; prism</span>'
        + "".join(f'<span>{l}</span>' for l in links)
        + f'<span style="margin-left:auto;color:#444;font-size:12px;">{Path(_project_path).name}</span>'
        + "</nav>"
    )


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/constitution")


@app.get("/graph", response_class=HTMLResponse)
def graph():
    import networkx as nx
    from pyvis.network import Network

    from prism_mem.storage.db import get_all_triples, open_db

    try:
        conn = open_db(_project_path)
        triples = [t for t in get_all_triples(conn) if not t.stale]
        conn.close()
    except Exception as e:
        return HTMLResponse(_empty_page("Graph", f"Could not load graph: {e}"))

    if not triples:
        return HTMLResponse(_empty_page("Graph", "No triples yet. Run <code>prism crystallize</code> first."))

    G = nx.DiGraph()
    seen_edges: dict[tuple, list[str]] = {}
    for t in triples:
        G.add_node(t.subject)
        G.add_node(t.object)
        key = (t.subject, t.object)
        seen_edges.setdefault(key, []).append(t.predicate)

    for (src, dst), preds in seen_edges.items():
        label = " / ".join(dict.fromkeys(preds))  # deduplicate preserving order
        G.add_edge(src, dst, label=label, title=label)

    net = Network(
        height="calc(100vh - 46px)",
        width="100%",
        directed=True,
        bgcolor="#0f0f1a",
        font_color="#cccccc",
    )
    for node in G.nodes():
        net.add_node(str(node), label=str(node), title=str(node))
    for src, dst, data in G.edges(data=True):
        net.add_edge(str(src), str(dst), label=data.get("label", ""), title=data.get("title", ""))

    net.set_options("""{
      "physics": {
        "barnesHut": {"gravitationalConstant": -8000, "springLength": 120},
        "stabilization": {"iterations": 150}
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
        "color": {"color": "#3a3a6a", "highlight": "#e94560"},
        "font": {"size": 9, "color": "#666", "align": "middle"},
        "smooth": {"type": "curvedCW", "roundness": 0.2}
      },
      "nodes": {
        "shape": "dot",
        "size": 14,
        "color": {"background": "#e94560", "border": "#c73652", "highlight": {"background": "#ff6b6b"}},
        "font": {"size": 12, "color": "#fff"}
      },
      "interaction": {"hover": true, "navigationButtons": true}
    }""")

    pyvis_html = net.generate_html()
    nav_html = _nav("Graph")
    pyvis_html = pyvis_html.replace("<body>", f"<body style='margin:0;padding:0;'>{nav_html}", 1)
    return HTMLResponse(content=pyvis_html)


@app.get("/memory", response_class=HTMLResponse)
def memory():
    from prism_mem.storage.db import get_all_triples, open_db

    try:
        conn = open_db(_project_path)
        triples = get_all_triples(conn)
        conn.close()
    except Exception as e:
        return HTMLResponse(_empty_page("Memory", f"Could not load triples: {e}"))

    rows = ""
    for t in sorted(triples, key=lambda x: x.id, reverse=True):
        fade = "opacity:0.35;" if t.stale else ""
        strike = "text-decoration:line-through;" if t.stale else ""
        ts = t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else ""
        badge = (
            '<span style="color:#e94560;font-size:11px;">stale</span>'
            if t.stale
            else '<span style="color:#4caf50;font-size:11px;">active</span>'
        )
        rows += (
            f'<tr style="{fade}{strike}">'
            f"<td>{t.id}</td>"
            f"<td>{_esc(t.subject)}</td>"
            f'<td><span style="color:#7ec8e3;">{_esc(t.predicate)}</span></td>'
            f"<td>{_esc(t.object)}</td>"
            f"<td>{t.confidence:.2f}</td>"
            f"<td>{ts}</td>"
            f"<td>{badge}</td>"
            f"</tr>"
        )

    active = sum(1 for t in triples if not t.stale)

    return HTMLResponse(f"""<!DOCTYPE html><html>
<head><meta charset="utf-8"><title>Prism — Memory</title>
<style>
  body{{margin:0;background:#0f0f1a;color:#ccc;font-family:sans-serif;font-size:13px;}}
  .bar{{background:#0f0f1a;padding:8px 20px;display:flex;align-items:center;gap:12px;
        border-bottom:1px solid #1e1e3a;position:sticky;top:46px;z-index:5;}}
  #q{{background:#1a1a2e;border:1px solid #2a2a4a;color:#fff;padding:5px 10px;
      border-radius:4px;font-size:13px;width:280px;outline:none;}}
  .stat{{color:#444;font-size:12px;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{background:#1a1a2e;color:#e94560;padding:7px 12px;text-align:left;
      position:sticky;top:92px;font-weight:600;font-size:12px;letter-spacing:.05em;}}
  td{{padding:6px 12px;border-bottom:1px solid #111;vertical-align:top;}}
  tr:hover td{{background:#1a1a2e;}}
</style></head>
<body>
{_nav("Memory")}
<div class="bar">
  <input id="q" type="text" placeholder="Filter triples…" oninput="filter(this.value)" autofocus>
  <span class="stat">{len(triples)} total · {active} active</span>
</div>
<table id="t">
  <thead><tr>
    <th>#</th><th>Subject</th><th>Predicate</th><th>Object</th>
    <th>Conf</th><th>Timestamp</th><th>Status</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
<script>
function filter(q){{
  q=q.toLowerCase();
  document.querySelectorAll('#t tbody tr').forEach(r=>{{
    r.style.display=r.textContent.toLowerCase().includes(q)?'':'none';
  }});
}}
</script>
</body></html>""")


@app.get("/constitution", response_class=HTMLResponse)
def constitution():
    p = Path(_project_path) / "CLAUDE.md"
    if p.exists():
        raw = _esc(p.read_text(encoding="utf-8"))
        note = ""
    else:
        raw = "(No CLAUDE.md found — run crystallize first.)"
        note = "color:#555;"

    return HTMLResponse(f"""<!DOCTYPE html><html>
<head><meta charset="utf-8"><title>Prism — Constitution</title>
<style>
  body{{margin:0;background:#0f0f1a;color:#ccc;font-family:sans-serif;font-size:13px;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 20px;}}
  .btn{{background:#e94560;color:#fff;border:none;padding:7px 16px;border-radius:4px;
        cursor:pointer;font-size:13px;margin-bottom:18px;}}
  .btn:hover{{background:#c73652;}}
  pre{{background:#1a1a2e;border:1px solid #1e1e3a;padding:20px 24px;border-radius:6px;
       white-space:pre-wrap;word-wrap:break-word;line-height:1.65;font-size:13px;
       color:#c9d1d9;{note}}}
</style></head>
<body>
{_nav("Constitution")}
<div class="wrap">
  <form method="post" action="/constitution/regenerate">
    <button class="btn" type="submit">&#9654;&nbsp; Regenerate</button>
  </form>
  <pre>{raw}</pre>
</div>
</body></html>""")


@app.post("/constitution/regenerate")
def regenerate():
    from prism_mem.constitution.generator import write_constitution
    from prism_mem.config import is_config_complete
    if not is_config_complete():
        return HTMLResponse(_empty_page("Constitution",
            "LLM not configured. Run <code>prism config set provider/model/api-key</code> then restart."))
    try:
        write_constitution(_project_path)
    except ValueError as e:
        return HTMLResponse(_empty_page("Constitution", f"Cannot regenerate: {_esc(str(e))}"))
    except Exception as e:
        return HTMLResponse(_empty_page("Constitution", f"Error during regeneration: {_esc(str(e))}"))
    return RedirectResponse("/constitution", status_code=303)


# ── empty state helper ────────────────────────────────────────────────────────

def _empty_page(tab: str, msg: str) -> str:
    return f"""<!DOCTYPE html><html>
<head><meta charset="utf-8"><title>Prism — {tab}</title>
<style>body{{margin:0;background:#0f0f1a;color:#888;font-family:sans-serif;font-size:13px;}}
.c{{display:flex;align-items:center;justify-content:center;height:60vh;}}</style></head>
<body>{_nav(tab)}<div class="c">{msg}</div></body></html>"""


# ── entry point ───────────────────────────────────────────────────────────────

def start_ui_server(
    project_path: str = ".",
    host: str = UI_HOST,
    port: int = UI_PORT,
    open_browser: bool = True,
) -> None:
    import webbrowser

    global _project_path
    _project_path = str(Path(project_path).resolve())

    if open_browser:
        @app.on_event("startup")
        async def _open_browser():
            webbrowser.open(f"http://{host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="error")
