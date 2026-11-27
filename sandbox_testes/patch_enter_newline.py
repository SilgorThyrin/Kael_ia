import os

p = os.path.expanduser("~/Kael_ia/templates/kael_chat.html")
html = open(p, encoding="utf-8").read()

patch_teclado = """
<script id="kaelEnterNewlineScript">
(function() {
  function configurarEnterQuebraLinha() {
    var promptEl = document.getElementById("prompt");
    if (!promptEl || promptEl.dataset.enterNewlineOk === "1") return;

    promptEl.addEventListener("keydown", function(e) {
      if (e.key === "Enter" && !e.ctrlKey && !e.metaKey) {
        e.stopImmediatePropagation();
        setTimeout(function() {
          promptEl.style.height = "auto";
          promptEl.style.height = Math.min(promptEl.scrollHeight, 130) + "px";
        }, 0);
      }
    }, true);

    promptEl.dataset.enterNewlineOk = "1";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", configurarEnterQuebraLinha);
  } else {
    configurarEnterQuebraLinha();
  }
  window.addEventListener("load", configurarEnterQuebraLinha);
})();
</script>
"""

assert "</body>" in html
if 'id="kaelEnterNewlineScript"' not in html:
    html = html.replace("</body>", patch_teclado + "\n</body>", 1)

cand = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/kael_chat_enter.html")
open(cand, "w", encoding="utf-8").write(html)
print("Candidato HTML limpo gerado:", cand)
