#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File Manager - Gerenciador seguro de arquivos para o Kael."""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional

class FileManager:
    """Gerenciador de arquivos com controle de autorização."""
    
    ALLOWED_DIRS = ["C:\\PortableAI"]
    PROTECTED_FILES = ["api_server.py", "tool_registry.py", "kael_context.py", "ceo_ai.py", "file_manager.py"]
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pending_actions = {}
        self.action_id = 0
    
    def is_path_allowed(self, file_path: str) -> bool:
        path = Path(file_path).resolve()
        for allowed in self.ALLOWED_DIRS:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
    
    def is_file_protected(self, file_path: str) -> bool:
        filename = Path(file_path).name
        return filename in self.PROTECTED_FILES

    def list_files(self, directory: str = "", recursive: bool = False, 
                   max_depth: int = 3) -> Dict[str, Any]:
        try:
            target_dir = self.base_dir / directory if directory else self.base_dir
            if not target_dir.exists():
                return {"response": f"❌ Diretório não encontrado: {directory}", "thinking": "Diretório não existe.", "status": "error"}
            files = []
            dirs = []
            if recursive:
                for item in target_dir.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(self.base_dir)
                        if len(rel_path.parts) <= max_depth:
                            files.append(str(rel_path))
                    elif item.is_dir():
                        rel_path = item.relative_to(self.base_dir)
                        if len(rel_path.parts) < max_depth:
                            dirs.append(str(rel_path))
            else:
                for item in target_dir.iterdir():
                    if item.is_file():
                        files.append(item.name)
                    elif item.is_dir():
                        dirs.append(item.name)
            response = f"📁 **Conteúdo de:** `{directory or '.'}`\n\n"
            if dirs:
                response += "**📂 Pastas:**\n"
                for d in sorted(dirs):
                    response += f"  📁 {d}/\n"
                response += "\n"
            if files:
                response += "**📄 Arquivos:**\n"
                for f in sorted(files):
                    response += f"  📄 {f}\n"
            if not dirs and not files:
                response += "Vazio.\n"
            return {"response": response, "thinking": f"Listou {len(dirs)} pastas e {len(files)} arquivos.", "status": "success", "data": {"files": files, "dirs": dirs}}
        except Exception as e:
            return {"response": f"❌ Erro ao listar arquivos: {str(e)[:200]}", "thinking": "Erro na listagem.", "status": "error"}

    def read_file(self, file_path: str) -> Dict[str, Any]:
        try:
            full_path = self.base_dir / file_path
            if not full_path.exists():
                return {"response": f"❌ Arquivo não encontrado: {file_path}", "thinking": "Arquivo não existe.", "status": "error"}
            if not self.is_path_allowed(str(full_path)):
                return {"response": f"❌ Caminho não permitido: {file_path}", "thinking": "Caminho fora da área autorizada.", "status": "error"}
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.count('\n') + 1
            size = len(content)
            response = f"📄 **Arquivo:** `{file_path}`\n📊 Tamanho: {size} bytes | Linhas: {lines}\n\n```\n" + content + "\n```"
            return {"response": response, "thinking": f"Leu arquivo {file_path} ({lines} linhas).", "status": "success", "data": {"content": content, "path": file_path}}
        except Exception as e:
            return {"response": f"❌ Erro ao ler arquivo: {str(e)[:200]}", "thinking": "Erro na leitura.", "status": "error"}

    def create_file(self, file_path: str, content: str, auto_authorize: bool = False) -> Dict[str, Any]:
        try:
            full_path = self.base_dir / file_path
            if full_path.exists():
                return {"response": f"⚠️ Arquivo já existe: {file_path}\nUse /modificar_arquivo para alterá-lo.", "thinking": "Arquivo já existe.", "status": "warning"}
            if not self.is_path_allowed(str(full_path)):
                return {"response": f"❌ Caminho não permitido: {file_path}", "thinking": "Caminho fora da área autorizada.", "status": "error"}
            self.action_id += 1
            action_id = self.action_id
            self.pending_actions[action_id] = {"type": "create", "file_path": file_path, "content": content, "authorized": False}
            response = (f"📝 **Novo Arquivo Pendente (ID: {action_id})**\n\n"
                        f"📁 Caminho: `{file_path}`\n"
                        f"📊 Tamanho: {len(content)} bytes\n\n"
                        f"⏳ **Aguardando sua autorização para criar.**\n\n"
                        f"Responda com: `/autorizar_acao {action_id}` para aprovar")
            return {"response": response, "thinking": f"Ação de criação pendente (ID: {action_id}).", "status": "pending", "data": {"action_id": action_id, "file_path": file_path}}
        except Exception as e:
            return {"response": f"❌ Erro ao criar arquivo: {str(e)[:200]}", "thinking": "Erro na criação.", "status": "error"}

    def modify_file(self, file_path: str, new_content: str, auto_authorize: bool = False) -> Dict[str, Any]:
        try:
            full_path = self.base_dir / file_path
            if not full_path.exists():
                return {"response": f"❌ Arquivo não encontrado: {file_path}", "thinking": "Arquivo não existe.", "status": "error"}
            if self.is_file_protected(file_path):
                return {"response": f"🔒 Arquivo protegido: {file_path}\nNão pode ser modificado automaticamente.", "thinking": "Arquivo protegido do sistema.", "status": "error"}
            if not self.is_path_allowed(str(full_path)):
                return {"response": f"❌ Caminho não permitido: {file_path}", "thinking": "Caminho fora da área autorizada.", "status": "error"}
            self.action_id += 1
            action_id = self.action_id
            self.pending_actions[action_id] = {"type": "modify", "file_path": file_path, "content": new_content, "authorized": False}
            response = (f"📝 **Modificação Pendente (ID: {action_id})**\n\n"
                        f"📁 Arquivo: `{file_path}`\n"
                        f"📊 Novo tamanho: {len(new_content)} bytes\n\n"
                        f"⏳ **Aguardando sua autorização para modificar.**\n\n"
                        f"Responda com: `/autorizar_acao {action_id}` para aprovar")
            return {"response": response, "thinking": f"Ação de modificação pendente (ID: {action_id}).", "status": "pending", "data": {"action_id": action_id, "file_path": file_path}}
        except Exception as e:
            return {"response": f"❌ Erro ao modificar arquivo: {str(e)[:200]}", "thinking": "Erro na modificação.", "status": "error"}

    def authorize_action(self, action_id: int) -> Dict[str, Any]:
        if action_id not in self.pending_actions:
            return {"response": f"❌ Ação não encontrada: {action_id}", "thinking": "Ação não existe.", "status": "error"}
        action = self.pending_actions[action_id]
        if action["authorized"]:
            return {"response": f"✅ Ação {action_id} já foi autorizada e executada.", "thinking": "Ação já autorizada.", "status": "success"}
        try:
            file_path = action["file_path"]
            content = action["content"]
            full_path = self.base_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            action["authorized"] = True
            response = f"✅ **Ação {action_id} Autorizada e Executada!**\n\n📁 Arquivo: `{file_path}`\n📊 Operação: {action['type']}\n📊 Tamanho: {len(content)} bytes\n\nArquivo criado/modificado com sucesso."
            return {"response": response, "thinking": f"Ação {action_id} executada com sucesso.", "status": "success"}
        except Exception as e:
            return {"response": f"❌ Erro ao executar ação {action_id}: {str(e)[:200]}", "thinking": "Erro na execução.", "status": "error"}

    def list_pending_actions(self) -> Dict[str, Any]:
        if not self.pending_actions:
            return {"response": "✅ Nenhuma ação pendente de autorização.", "thinking": "Sem ações pendentes.", "status": "success"}
        response = "⏳ **Ações Pendentes de Autorização:**\n\n"
        for aid, action in self.pending_actions.items():
            status = "✅ Autorizada" if action["authorized"] else "⏳ Aguardando"
            response += f"**ID {aid}:** {action['type']} - `{action['file_path']}`\n  Status: {status}\n\n"
        response += "Use `/autorizar_acao <ID>` para aprovar uma ação."
        return {"response": response, "thinking": f"Listou {len(self.pending_actions)} ações pendentes.", "status": "success", "data": {"pending_count": len(self.pending_actions)}}

    def cancel_action(self, action_id: int) -> Dict[str, Any]:
        if action_id not in self.pending_actions:
            return {"response": f"❌ Ação não encontrada: {action_id}", "thinking": "Ação não existe.", "status": "error"}
        del self.pending_actions[action_id]
        return {"response": f"❌ Ação {action_id} cancelada.", "thinking": f"Ação {action_id} removida.", "status": "success"}


file_manager = None

def init_file_manager(base_dir: Path):
    global file_manager
    file_manager = FileManager(base_dir)
    return file_manager

def get_file_manager():
    return file_manager