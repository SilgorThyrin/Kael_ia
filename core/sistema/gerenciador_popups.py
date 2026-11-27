"""
Gerenciador de Pop-ups e Notificações Visuais para o Kael
"""
import json
from pathlib import Path

class GerenciadorPopups:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.notificacoes_pendentes = []

    def adicionar_alerta(self, titulo: str, mensagem: str, tipo: str = "info"):
        alerta = {
            "titulo": titulo,
            "mensagem": mensagem,
            "tipo": tipo
        }
        self.notificacoes_pendentes.append(alerta)
        return alerta

    def listar_alertas(self):
        pendentes = self.notificacoes_pendentes
        self.notificacoes_pendentes = []
        return pendentes

def init_gerenciador_popups(base_dir: Path):
    return GerenciadorPopups(base_dir)
