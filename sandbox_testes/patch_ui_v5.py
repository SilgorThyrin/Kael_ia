import os

p = os.path.expanduser("~/Kael_ia/templates/kael_chat.html")
src = open(p, encoding="utf-8").read()

css_v5 = """
<style id="kael-ui-v5-style">
  .kael-msg-actions {
    display: flex;
    gap: 6px;
    margin-top: 6px;
    flex-wrap: wrap;
  }
  .kael-act-btn {
    background: rgba(255, 255, 255, 0.06);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    cursor: pointer;
    line-height: 1.3;
  }
  .kael-act-btn:hover {
    background: rgba(59, 130, 246, 0.22);
    color: #fff;
  }
  .kael-code-box {
    background: #0b1120;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    margin: 8px 0;
    overflow: hidden;
  }
  .kael-code-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(15, 23, 42, 0.95);
    padding: 4px 10px;
    font-size: 11px;
    color: #94a3b8;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  }
  .kael-code-box pre {
    margin: 0;
    padding: 10px;
    overflow-x: auto;
    font-size: 12px;
    color: #e2e8f0;
  }
  .kael-inline-code {
    background: rgba(148, 163, 184, 0.16);
    padding: 1px 5px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.92em;
  }
</style>
"""

js_v5 = """
<script id="kael-ui-v5-script">
(function() {
  function escHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  window.kaelCopiarTexto = async function(txt, btnEl) {
    const raw = String(txt || "");
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(raw);
      } else {
        throw new Error("no clipboard");
      }
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = raw;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    if (btnEl) {
      const orig = btnEl.textContent;
      btnEl.textContent = "Copiado";
      setTimeout(() => { btnEl.textContent = orig; }, 1400);
    }
  };

  window.kaelFormatarHtml = function(texto) {
    const srcTxt = String(texto || "");
    const blocos = [];
    const comPlaceholders = srcTxt.replace(/```([a-zA-Z0-9_-]*)\\n([\\s\\S]*?)```/g, function(_, lang, cod) {
      const idx = blocos.length;
      const nomeLang = (lang || "codigo").trim();
      const codLimpo = cod.replace(/\\n$/, "");
      blocos.push(
        `<div class="kael-code-box"><div class="kael-code-head"><span>${escHtml(nomeLang)}</span><button type="button" class="kael-act-btn" data-copy-idx="${idx}">Copiar código</button></div><pre><code>${escHtml(codLimpo)}</code></pre></div>` ); return `@@KAELBLOCK_${idx}@@`;
    });

    let html = escHtml(comPlaceholders)
      .replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>")
      .replace(/`([^`\\n]+)`/g, '<code class="kael-inline-code">$1</code>')
      .replace(/\\n/g, "<br>");

    html = html.replace(/@@KAELBLOCK_(\\d+)@@/g, function(_, i) {
      return blocos[Number(i)] || "";
    });
    return html;
  };

  function atualizarBotoesEditar() {
    const box = document.querySelector("#chat, #messages, .chat-messages, .messages");
    if (!box) return;
    box.querySelectorAll(".kael-btn-editar-ultima").forEach(b => b.remove());
    const userBtns = box.querySelectorAll("[data-kael-role=\\"user\\"] .kael-msg-actions");
    if (!userBtns.length) return;
    const ultimaBarra = userBtns[userBtns.length - 1];
    const btnEdit = document.createElement("button");
    btnEdit.type = "button";
    btnEdit.className = "kael-act-btn kael-btn-editar-ultima";
    btnEdit.textContent = "Editar";
    btnEdit.onclick = function() {
      const msgEl = ultimaBarra.closest("[data-kael-raw]");
      const textoAntigo = msgEl ? (msgEl.getAttribute("data-kael-raw") || "") : "";
      const input = document.querySelector("textarea, #prompt, #input, input[type=\\"text\\"]");
      if (input) {
        input.value = textoAntigo;
        input.focus();
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (msgEl) {
        const prox = msgEl.nextElementSibling;
        if (prox && prox.getAttribute("data-kael-role") === "assistant") {
          prox.remove();
        }
        msgEl.remove();
        atualizarBotoesEditar();
      }
    };
    ultimaBarra.prepend(btnEdit);
  }

  function enriquecerMensagens() {
    const box = document.querySelector("#chat, #messages, .chat-messages, .messages");
    if (!box) return;
    const filhos = Array.from(box.children);
    filhos.forEach(el => {
      if (el.getAttribute("data-kael-v5") === "1") return;
      const txt = (el.innerText || "").trim();
      if (!txt) return;
      const isUser = /user|usuario|eu/i.test(el.className || "") || el.style.marginLeft === "auto";
      const role = isUser ? "user" : "assistant";
      el.setAttribute("data-kael-v5", "1");
      el.setAttribute("data-kael-role", role);
      el.setAttribute("data-kael-raw", txt);

      if (!isUser && (txt.includes("**") || txt.includes("```") || txt.includes("`"))) {
        el.innerHTML = window.kaelFormatarHtml(txt);
        el.querySelectorAll("[data-copy-idx]").forEach(btnCode => {
          const idx = Number(btnCode.getAttribute("data-copy-idx"));
          const matchCod = txt.match(/```[a-zA-Z0-9_-]*\\n([\\s\\S]*?)```/g);
          const blocoStr = matchCod && matchCod[idx] ? matchCod[idx].replace(/^```[^\\n]*\\n|\\n```$/g, "") : txt;
          btnCode.onclick = function(ev) {
            ev.stopPropagation();
            window.kaelCopiarTexto(blocoStr, btnCode);
          };
        });
      }

      const bar = document.createElement("div");
      bar.className = "kael-msg-actions";
      const btnCopy = document.createElement("button");
      btnCopy.type = "button";
      btnCopy.className = "kael-act-btn";
      btnCopy.textContent = "Copiar";
      btnCopy.onclick = function(ev) {
        ev.stopPropagation();
        window.kaelCopiarTexto(el.getAttribute("data-kael-raw") || txt, btnCopy);
      };
      bar.appendChild(btnCopy);
      el.appendChild(bar);
    });
    atualizarBotoesEditar();
  }

  const obs = new MutationObserver(() => {
    clearTimeout(window._kaelV5Timer);
    window._kaelV5Timer = setTimeout(enriquecerMensagens, 60);
  });
  window.addEventListener("DOMContentLoaded", () => {
    enriquecerMensagens();
    const box = document.querySelector("#chat, #messages, .chat-messages, .messages");
    if (box) obs.observe(box, { childList: true, subtree: true });
  });
  setInterval(enriquecerMensagens, 1500);
})();
</script>
"""

if "kael-ui-v5-style" not in src:
    if "</head>" in src:
        src = src.replace("</head>", css_v5 + "\n</head>", 1)
    else:
        src = css_v5 + "\n" + src

if "kael-ui-v5-script" not in src:
    if "</body>" in src:
        src = src.replace("</body>", js_v5 + "\n</body>", 1)
    else:
        src = src + "\n" + js_v5

cand = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/kael_chat.html")
open(cand, "w", encoding="utf-8").write(src)
print("Candidato UI V5 gerado:", cand)
