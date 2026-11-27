"""
============================================================
KAEL FLOATING DETECTOR - Blocos flutuantes em LOTES
============================================================
Modo 1 (Estático): parseia .rbxlx (XML) e detecta partes sem apoio
Modo 2 (Vivo): gera script Lua com raycast + remoção em lotes
============================================================
"""
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_PART_CLASSES = {
    'Part', 'MeshPart', 'Block', 'Wedge', 'CornerWedge',
    'Cylinder', 'Sphere', 'TrussPart', 'UnionOperation'
}


class FloatingDetector:
    def __init__(self, project_path, gap=0.5, ground=0.5):
        self.project_path = Path(project_path)
        self.gap = gap        # tolerância de contato (studs)
        self.ground = ground  # altura do chão

    # ---------- Localizar o place exportado ----------
    def find_place_file(self):
        arquivos = list(self.project_path.rglob('*.rbxlx'))
        return arquivos[0] if arquivos else None

    # ---------- Parse do XML (.rbxlx) ----------
    def parse_rbxlx(self, path):
        parts = []
        try:
            tree = ET.parse(path)
        except Exception as e:
            print(f"[FLUTUANTES] Erro ao parsear {path}: {e}")
            return parts

        for item in tree.getroot().iter('Item'):
            classe = item.get('class', '')
            if classe not in BASE_PART_CLASSES:
                continue

            nome = classe
            pos = [0.0, 0.0, 0.0]
            size = [4.0, 1.2, 2.0]

            props = item.find('Properties')
            if props is not None:
                for child in props:
                    tag = child.get('name', '')
                    if tag == 'Name' and child.text:
                        nome = child.text
                    elif tag == 'Position':
                        pos = [float(child.find('X').text or 0),
                               float(child.find('Y').text or 0),
                               float(child.find('Z').text or 0)]
                    elif tag == 'size' or tag == 'Size':
                        size = [float(child.find('X').text or 4),
                                float(child.find('Y').text or 1.2),
                                float(child.find('Z').text or 2)]

            parts.append({
                "referent": item.get('referent', ''),
                "name": nome,
                "class": classe,
                "pos": tuple(pos),
                "size": tuple(size),
            })
        return parts

    # ---------- Detecção geométrica (raycast estático) ----------
    def _tem_apoio(self, p, parts):
        px, py, pz = p['pos']
        sx, sy, sz = p['size']
        bottom = py - sy / 2

        # Apoiado no chão
        if bottom <= self.ground:
            return True

        for q in parts:
            if q is p:
                continue
            qx, qy, qz = q['pos']
            qsx, qsy, qsz = q['size']
            # Sobreposição em XZ (sombra embaixo)
            if abs(px - qx) < (sx + qsx) / 2 and abs(pz - qz) < (sz + qsz) / 2:
                qtop = qy + qsy / 2
                qbottom = qy - qsy / 2
                # Q está embaixo e encosta (ou intersecta) a base de P
                if qbottom < bottom - 0.01 and qtop >= bottom - self.gap:
                    return True
        return False

    def detect_floating(self, parts):
        return [p for p in parts if not self._tem_apoio(p, parts)]

    # ---------- Gera script Lua de remoção em LOTES ----------
    def generate_lua_batch(self, batch=50, names=None, dry_run=False):
        if names:
            # MODO DIRECIONADO: remove exatamente o que o Kael viu no .rbxlx
            lista = ',\n    '.join([f'"{n}"' for n in names])
            return f'''-- [KAEL] Removedor de Blocos Flutuantes (MODO DIRECIONADO)
-- Detectados estaticamente no .rbxlx. Cole no Command Bar do Roblox Studio.
local DRY_RUN = {'true' if dry_run else 'false'}
local BATCH = {batch}
local NOMES = {{
    {lista}
}}

local ws = game:GetService("Workspace")
local total = 0
for i = 1, #NOMES, BATCH do
    local lote = 0
    for j = i, math.min(i + BATCH - 1, #NOMES) do
        local p = ws:FindFirstChild(NOMES[j], true)
        if p then
            if DRY_RUN then
                print("[KAEL] Flutuante: " .. p:GetFullName())
            else
                p:Destroy()
            end
            lote += 1; total += 1
        end
    end
    print("[KAEL] Lote processado: " .. lote .. " | Total: " .. total .. "/" .. #NOMES)
    task.wait(0.05)
end
print("[KAEL] Concluído: " .. total .. " blocos em lotes de " .. BATCH .. ".")
'''
        else:
            # MODO RAYCAST AO VIVO: detecta e remove na hora, em lotes
            return f'''-- [KAEL] Removedor de Blocos Flutuantes (MODO RAYCAST AO VIVO)
-- Cole no Command Bar do Roblox Studio.
local DRY_RUN = {'true' if dry_run else 'false'}  -- true = só lista, não remove
local BATCH = {batch}
local ALTURA_MIN = 3   -- ignora blocos perto do chão
local GAP = 20         -- alcance do raycast para baixo

local ws = game:GetService("Workspace")
local flutuantes = {{}}

for _, obj in ipairs(ws:GetDescendants()) do
    if obj:IsA("BasePart") then
        local params = RaycastParams.new()
        params.FilterType = Enum.RaycastFilterType.Exclude
        params.FilterDescendantsInstances = {{obj}}
        local dir = Vector3.new(0, -(obj.Size.Y / 2 + GAP), 0)
        local hit = ws:Raycast(obj.Position, dir, params)
        if not hit and (obj.Position.Y - obj.Size.Y / 2) > ALTURA_MIN then
            table.insert(flutuantes, obj)
        end
    end
end

print("[KAEL] Detectados " .. #flutuantes .. " blocos flutuantes.")
local total = 0
for i = 1, #flutuantes, BATCH do
    local lote = 0
    for j = i, math.min(i + BATCH - 1, #flutuantes) do
        if DRY_RUN then
            print("  - " .. flutuantes[j]:GetFullName())
        else
            flutuantes[j]:Destroy()
        end
        lote += 1; total += 1
    end
    print("[KAEL] Lote processado: " .. lote .. " | Total: " .. total .. "/" .. #flutuantes)
    task.wait(0.05)
end
print("[KAEL] Concluído: " .. total .. " blocos em lotes de " .. BATCH .. ".")
'''

    # ---------- Cria cópia limpa do .rbxlx ----------
    def clean_rbxlx(self, path, referents, out_path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            removidos = 0
            for item in list(root.iter('Item')):
                if item.get('referent', '') in referents:
                    parent = self._parent_map(tree, root).get(item)
                    if parent is not None:
                        parent.remove(item)
                        removidos += 1
            tree.write(out_path, encoding='utf-8', xml_declaration=True)
            return removidos
        except Exception as e:
            print(f"[FLUTUANTES] Erro ao limpar rbxlx: {e}")
            return 0

    @staticmethod
    def _parent_map(tree, root):
        return {c: p for p in root.iter() for c in p}