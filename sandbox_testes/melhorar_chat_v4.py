import os

src_path = os.path.expanduser("~/Kael_ia/templates/kael_chat.html")
dst_path = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/kael_chat_v4.html")

with open(src_path, "r", encoding="utf-8") as f:
    html = f.read()

v4_patch = """
<style id="kaelMobileV4Style">
  :root {
    --bg-oled: #09090b;
    --bg-surface: #121216;
    --bg-elevated: #1c1c22;
    --border-hairline: rgba(255, 255, 255, 0.07);
    --text-primary: #f4f4f5;
    --text-secondary: #a1a1aa;
    --accent-blue: #2563eb;
  }

  body {
    background: var(--bg-oled) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif !important;
    -webkit-font-smoothing: antialiased;
  }

  /* Header minimalista em 1 linha */
  header, .topbar, .header {
    background: rgba(9, 9, 11, 0.92) !important;
    backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid var(--border-hairline) !important;
    padding: 8px 14px !important;
    min-height: 46px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 8px !important;
  }

  /* Oculta a barra separada de Pasta/Projeto e transforma o input em pílula compacta no header */
  #kaelProjPillV4 {
    font-size: 11px !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-hairline) !important;
    border-radius: 999px !important;
    padding: 4px 10px !important;
    max-width: 145px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    cursor: pointer !important;
  }

  /* Área de conversa limpa e ampla */
  #chat {
    background: var(--bg-oled) !important;
    padding: 16px 14px 20px 14px !important;
    gap: 14px !important;
  }

  #chat > div {
    font-size: 15px !important;
    line-height: 1.52 !important;
    box-shadow: none !important;
  }

  /* Balão do usuário: pílula limpa à direita */
  #chat > div.user, #chat > div[data-role="user"] {
    background: var(--accent-blue) !important;
    color: #ffffff !important;
    padding: 10px 15px !important;
    border-radius: 20px 20px 4px 20px !important;
    max-width: 82% !important;
    font-weight: 450 !important;
  }

  /* Resposta do Kael: limpa, sem caixa pesada */
  #chat > div:not(.user):not([data-role="user"]) {
    background: transparent !important;
    border: none !important;
    padding: 2px 4px !important;
    border-radius: 0 !important;
    max-width: 96% !important;
    color: var(--text-primary) !important;
  }

  /* Esconde qualquer barra de atalhos solta fora da gaveta */
  body > div:not(#chat):not(#kaelComposerV3):not(#configModal):not(#permModal):not(#kaelActionMenu) button {
    font-size: 12px !important;
  }

  /* Composer flutuante ultra-limpo */
  #kaelComposerV3 {
    background: var(--bg-oled) !important;
    border-top: 1px solid var(--border-hairline) !important;
    padding: 8px 12px calc(10px + env(safe-area-inset-bottom)) 12px !important;
  }

  #kaelDrawerV3 {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-hairline) !important;
    border-radius: 16px !important;
    padding: 10px !important;
    gap: 8px !important;
    margin-bottom: 4px !important;
  }

  #kaelDrawerV3 button, #kaelDrawerV3 select {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-hairline) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 7px 11px !important;
    font-size: 12px !important;
  }

  #kaelInputRowV3 {
    background: var(--bg-surface) !important;
    border: 1px solid rgba(255, 255, 255, 0.11) !important;
    border-radius: 24px !important;
    padding: 4px 6px !important;
    align-items: center !important;
    gap: 6px !important;
  }

  #kaelInputRowV3:focus-within {
    border-color: rgba(59, 130, 246, 0.65) !important;
  }

  #kaelToggleDrawerBtn {
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    background: transparent !important;
    border: none !important;
    color: var(--text-secondary) !important;
    font-size: 22px !important;
    font-weight: 400 !important;
  }

  #prompt {
    background: transparent !important;
    border: none !important;
    padding: 8px 6px !important;
    min-height: 36px !important;
    max-height: 120px !important;
    font-size: 15.5px !important;
    color: var(--text-primary) !important;
  }

  #send {
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    padding: 0 !important;
    border-radius: 50% !important;
    background: var(--text-primary) !important;
    color: var(--bg-oled) !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }
</style>
<script id="kaelMobileV4Script">
(function() {
  function aplicarVisaoLimpaV4() {
    var sendEl = document.getElementById("send");
    if (sendEl && sendEl.textContent.trim() === "Enviar") {
      sendEl.textContent = "↑";
      sendEl.title = "Enviar mensagem";
    }

    // Move qualquer botão de atalho criado tardiamente para dentro da gaveta '+'
    var drawer = document.getElementById("kaelDrawerV3");
    if (drawer) {
      var palavrasAtalho = ["Testar Códigos", "Ver Arquivos", "Novo Código", "Ecos de Aethelgard", "Config", "Voz", "Ei, Kael", "8080:"];
      document.querySelectorAll("button").forEach(function(btn) {
        if (btn.id === "send" || btn.id === "kaelToggleDrawerBtn") return;
        var txt = (btn.textContent || "").trim();
        var ehAtalho = palavrasAtalho.some(function(p) { return txt.indexOf(p) !== -1; });
        if (ehAtalho && !drawer.contains(btn)) {
          var pai = btn.parentElement;
          drawer.appendChild(btn);
          if (pai && pai.children.length === 0 && pai.id !== "chat") {
            pai.style.display = "none";
          }
        }
      });
    }

    // Compacta a linha "Pasta / Projeto:" em uma pílula discreta no topo
    var alvoInput = document.getElementById("alvoPath");
    var header = document.querySelector("header, .topbar, .header");
    if (alvoInput && header && !document.getElementById("kaelProjPillV4")) {
      var linhaPasta = alvoInput.parentElement;
      var pill = document.createElement("button");
      pill.type = "button";
      pill.id = "kaelProjPillV4";
      var atualizarPill = function() {
        var val = (alvoInput.value || "").replace(/\/+$/, "");
        var nome = val.split("/").pop() || "Kael_ia";
        pill.textContent = "📁 " + nome;
        pill.title = val;
      };
      atualizarPill();
      pill.onclick = function() {
        if (linhaPasta) {
          linhaPasta.style.display = (linhaPasta.style.display === "none") ? "flex" : "none";
        }
      };
      header.insertBefore(pill, header.lastElementChild);
      if (linhaPasta && linhaPasta !== header) {
        linhaPasta.style.display = "none";
      }
      alvoInput.addEventListener("change", atualizarPill);
    }

    // Remove prefixos redundantes "Você:" e "Kael:" nas bolhas
    var chat = document.getElementById("chat");
    if (chat) {
      Array.from(chat.children).forEach(function(div) {
        if (div.dataset.v4Cleaned === "1") return;
        var htmlInner = div.innerHTML || "";
        var txt = (div.textContent || "").trim();
        if (txt.startsWith("Você:")) {
          div.classList.add("user");
          div.innerHTML = htmlInner.replace(/^\s*(?:<[^>]+>)*\s*Você:\s*(?:<\/[^>]+>)?\s*/i, "");
        } else if (txt.startsWith("Kael:")) {
          div.innerHTML = htmlInner.replace(/^\s*(?:<[^>]+>)*\s*Kael:\s*(?:<\/[^>]+>)?\s*/i, "");
        }
        div.dataset.v4Cleaned = "1";
      });
    }
  }

  window.addEventListener("load", function() {
    aplicarVisaoLimpaV4();
    setTimeout(aplicarVisaoLimpaV4, 250);
    setTimeout(aplicarVisaoLimpaV4, 800);
    var obs = new MutationObserver(aplicarVisaoLimpaV4);
    obs.observe(document.body, { childList: true, subtree: true });
  });
})();
</script>
"""

assert "</body>" in html
novo_html = html.replace("</body>", v4_patch + "\n</body>", 1)

with open(dst_path, "w", encoding="utf-8") as f:
    f.write(novo_html)
print("UI V4 gerada com sucesso:", dst_path)
