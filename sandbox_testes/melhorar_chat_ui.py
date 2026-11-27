import os

src_path = os.path.expanduser("~/Kael_ia/templates/kael_chat.html")
dst_path = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/kael_chat_v3.html")

with open(src_path, "r", encoding="utf-8") as f:
    html = f.read()

# Remove estilos antigos conflitantes se existirem
if 'id="kaelMobileV3Style"' in html:
    print("Já aplicado.")
    raise SystemExit(0)

v3_patch = """
<style id="kaelMobileV3Style">
  :root {
    --bg-app: #0b0f17;
    --bg-panel: #111827;
    --bg-elevated: #1f2937;
    --border-subtle: rgba(255, 255, 255, 0.08);
    --text-main: #f3f4f6;
    --text-muted: #9ca3af;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
  }

  * { box-sizing: border-box; }

  body {
    background: var(--bg-app) !important;
    color: var(--text-main) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 100dvh !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
  }

  /* Header compacto */
  header, .topbar, .header {
    padding: 8px 12px !important;
    background: var(--bg-panel) !important;
    border-bottom: 1px solid var(--border-subtle) !important;
    flex-shrink: 0 !important;
  }

  /* Barra de pasta compacta e discreta */
  #alvoPath {
    font-size: 12px !important;
    padding: 5px 8px !important;
    background: var(--bg-app) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-muted) !important;
    max-width: 100% !important;
  }

  /* Área de mensagens respirada */
  #chat {
    flex: 1 1 auto !important;
    overflow-y: auto !important;
    padding: 14px 12px 18px 12px !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 10px !important;
    scroll-behavior: smooth !important;
  }

  #chat > div {
    max-width: 88% !important;
    padding: 10px 14px !important;
    border-radius: 16px !important;
    font-size: 15px !important;
    line-height: 1.48 !important;
    word-wrap: break-word !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.22) !important;
  }

  /* Mensagens do usuário à direita */
  #chat > div.user, #chat > div[data-role="user"] {
    align-self: flex-end !important;
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: #ffffff !important;
    border-bottom-right-radius: 4px !important;
    border: none !important;
  }

  /* Mensagens do Kael à esquerda */
  #chat > div.bot, #chat > div.assistant, #chat > div[data-role="assistant"], #chat > div:not(.user):not([data-role="user"]) {
    align-self: flex-start !important;
    background: var(--bg-panel) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--border-subtle) !important;
    border-bottom-left-radius: 4px !important;
    max-width: 94% !important;
  }

  /* Composer Moderno (Rodapé) */
  #kaelComposerV3 {
    background: var(--bg-panel) !important;
    border-top: 1px solid var(--border-subtle) !important;
    padding: 8px 10px calc(8px + env(safe-area-inset-bottom)) 10px !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
    flex-shrink: 0 !important;
    z-index: 50 !important;
  }

  #kaelDrawerV3 {
    display: none;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px;
    background: var(--bg-app);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
  }

  #kaelDrawerV3.aberto {
    display: flex !important;
  }

  #kaelDrawerV3 button, #kaelDrawerV3 select {
    font-size: 12px !important;
    padding: 6px 10px !important;
    border-radius: 8px !important;
    border: 1px solid var(--border-subtle) !important;
    background: var(--bg-elevated) !important;
    color: var(--text-main) !important;
    cursor: pointer !important;
  }

  #kaelInputRowV3 {
    display: flex !important;
    align-items: flex-end !important;
    gap: 8px !important;
    width: 100% !important;
  }

  #kaelToggleDrawerBtn {
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    border-radius: 50% !important;
    border: 1px solid var(--border-subtle) !important;
    background: var(--bg-elevated) !important;
    color: var(--text-main) !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    padding: 0 !important;
  }

  #prompt {
    flex: 1 1 auto !important;
    width: 100% !important;
    min-width: 0 !important;
    min-height: 42px !important;
    max-height: 130px !important;
    padding: 10px 14px !important;
    border-radius: 20px !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    background: var(--bg-app) !important;
    color: #ffffff !important;
    font-size: 16px !important;
    line-height: 1.35 !important;
    resize: none !important;
    outline: none !important;
  }

  #prompt:focus {
    border-color: var(--accent) !important;
  }

  #send {
    height: 42px !important;
    min-width: 68px !important;
    padding: 0 14px !important;
    border-radius: 20px !important;
    border: none !important;
    background: var(--accent) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
  }

  #send:active {
    background: var(--accent-hover) !important;
  }
</style>
<script id="kaelMobileV3Script">
(function() {
  function reorganizarComposerV3() {
    var promptEl = document.getElementById("prompt");
    var sendEl = document.getElementById("send");
    if (!promptEl || !sendEl || document.getElementById("kaelComposerV3")) return;

    var parentAntigo = promptEl.parentElement;
    var composer = document.createElement("div");
    composer.id = "kaelComposerV3";

    var drawer = document.createElement("div");
    drawer.id = "kaelDrawerV3";

    var row = document.createElement("div");
    row.id = "kaelInputRowV3";

    var toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.id = "kaelToggleDrawerBtn";
    toggleBtn.title = "Ferramentas, Voz e Atalhos";
    toggleBtn.textContent = "+";
    toggleBtn.onclick = function() {
      drawer.classList.toggle("aberto");
      toggleBtn.textContent = drawer.classList.contains("aberto") ? "×" : "+";
    };

    // Move botões auxiliares (micBtn, wakeBtn, sleepBtn, config, quickbar) para a gaveta retrátil
    ["micBtn", "wakeBtn", "sleepBtn"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) drawer.appendChild(el);
    });

    // Move outros botões soltos da barra antiga e pílulas de atalho para a gaveta
    if (parentAntigo) {
      var extras = Array.from(parentAntigo.querySelectorAll("button"));
      extras.forEach(function(b) {
        if (b !== sendEl && b !== toggleBtn && !drawer.contains(b)) {
          drawer.appendChild(b);
        }
      });
    }

    document.querySelectorAll("button").forEach(function(b) {
      var txt = (b.textContent || "").trim();
      if (["Testar Códigos", "Ver Arquivos", "Novo Código na Sandbox", "Ecos de Aethelgard", "Config"].some(function(k) { return txt.indexOf(k) !== -1; })) {
        if (!drawer.contains(b)) drawer.appendChild(b);
      }
    });

    promptEl.placeholder = "Escreva para o Kael...";
    row.appendChild(toggleBtn);
    row.appendChild(promptEl);
    row.appendChild(sendEl);

    composer.appendChild(drawer);
    composer.appendChild(row);

    document.body.appendChild(composer);
    if (parentAntigo && parentAntigo.children.length === 0) {
      parentAntigo.style.display = "none";
    }
  }

  function limparPrefixosBolhas() {
    var chat = document.getElementById("chat");
    if (!chat) return;
    Array.from(chat.children).forEach(function(div) {
      var txt = (div.textContent || "").trim();
      if (txt.startsWith("Você:")) {
        div.classList.add("user");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function() {
      reorganizarComposerV3();
      limparPrefixosBolhas();
    });
  } else {
    reorganizarComposerV3();
    limparPrefixosBolhas();
  }

  var obs = new MutationObserver(function() { limparPrefixosBolhas(); });
  window.addEventListener("load", function() {
    var chat = document.getElementById("chat");
    if (chat) obs.observe(chat, { childList: true });
  });
})();
</script>
"""

assert "</body>" in html, "Tag </body> não encontrada"
novo_html = html.replace("</body>", v3_patch + "\n</body>", 1)

with open(dst_path, "w", encoding="utf-8") as f:
    f.write(novo_html)
print("UI V3 gerada em:", dst_path)
