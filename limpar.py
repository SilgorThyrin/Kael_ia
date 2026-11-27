import subprocess
import sys

def run_git_command(args):
    """Executa comandos git de forma segura, sem shell=True."""
    try:
        result = subprocess.run(["git"] + args, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"✅ {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar 'git {' '.join(args)}':")
        print(f"   {e.stderr.strip()}")
        return False

def main():
    print("🔄 1. Atualizando repositório local para evitar conflitos...")
    run_git_command(["pull", "origin", "main"])

    # Lista de arquivos e pastas obsoletos identificados na análise
    items_to_remove = [
        "game_architect.py",
        "game_director.py",
        "game_integrator.py",
        "world_builder.py",
        "kael_creative.py",
        "kael_assets.py",
        "kael_loader.py",
        "kael_persona.py",
        "refactor_agent.py",      # Script experimental/temporário
        "kael_websearch.py",      # Conflita com RAG local / sem internet
        "kael_modules.json",      # Substituído por sqlite-vec
        "api_server.py",          # Substituído por Túnel WebSocket
        "api",                    # Pasta antiga de API HTTP
        "start_kael.bat"          # Redundante com a pasta scripts/
    ]

    print("\n🧹 2. Removendo arquivos obsoletos do Git e do disco...")
    for item in items_to_remove:
        print(f"   Removendo: {item}")
        # -r para recursivo (pastas), -f para forçar a remoção do disco
        run_git_command(["rm", "-r", "-f", item])

    print("\n🔄 3. Renomeando kael_system_tools.py para system_tools.py (Alinhamento com Memória 15)...")
    run_git_command(["mv", "kael_system_tools.py", "system_tools.py"])

    print("\n💾 4. Salvando alterações no histórico Git...")
    commit_msg = (
        "chore: limpeza de arquitetura - remoção de arquivos obsoletos e fragmentados\n\n"
        "- Removidos módulos de jogo fragmentados (consolidados em game_manager/kael_engine)\n"
        "- Removido kael_websearch.py (foco em RAG local e sem dependência de internet)\n"
        "- Removidos api/ e api_server.py (substituídos por Túnel WebSocket Mobile-PC)\n"
        "- Removido kael_modules.json (substituído por sqlite-vec)\n"
        "- Renomeado kael_system_tools.py para system_tools.py"
    )
    run_git_command(["commit", "-m", commit_msg])

    print("\n🚀 5. Enviando alterações para o GitHub...")
    run_git_command(["push", "origin", "main"])

    print("\n✅ Limpeza concluída com sucesso!")
    print("💡 Dica: Lembre-se de que dados sensíveis devem permanecer apenas no repositório privado 'arquivos-de-inteligencia' (Memória 12).")

if __name__ == "__main__":
    # Verifica se está em um repositório git
    if not run_git_command(["rev-parse", "--is-inside-work-tree"]):
        print("❌ Erro: Este script deve ser executado na raiz do repositório Git local do Kael.")
        sys.exit(1)
    
    main()