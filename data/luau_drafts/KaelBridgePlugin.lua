-- Kael Roblox Studio Bridge protocol v1.1
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local ServerStorage = game:GetService("ServerStorage")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")

local API = "http://127.0.0.1:8000"
local PROTOCOL_VERSION = 1
local MAX_INSTANCES = 250
local MAX_SCRIPT_COUNT = 100
local MAX_SCRIPT_CHARS = 50000
local MAX_TOTAL_SCRIPT_CHARS = 500000
local TERRAIN_SAMPLE_INTERVAL = 45
local STATE_HEARTBEAT_INTERVAL = 45

local polling = false
local busy = false
local lastStateSent = 0
local pollBackoff = 2
local cachedTerrainSummary = nil
local lastTerrainSample = 0

local clientId = plugin:GetSetting("KaelClientId")
if type(clientId) ~= "string" or #clientId < 8 then
clientId = HttpService:GenerateGUID(false)
plugin:SetSetting("KaelClientId", clientId)
end

local function log(message)
print("[Kael Bridge] " .. tostring(message))
end

local function postJson(path, payload)
payload.protocol_version = PROTOCOL_VERSION
payload.client_id = clientId
local ok, response = pcall(function()
return HttpService:RequestAsync({
Url = API .. path,
Method = "POST",
Headers = { ["Content-Type"] = "application/json" },
Body = HttpService:JSONEncode(payload),
})
end)
if not ok then
return false, tostring(response)
end
if not response.Success then
return false, "HTTP " .. tostring(response.StatusCode) .. ": " .. response.Body
end
return true, response.Body
end

local function getJson(path)
local ok, response = pcall(function()
return HttpService:RequestAsync({
Url = API .. path,
Method = "GET",
})
end)
if not ok then
return nil, tostring(response)
end
if not response.Success then
return nil, "HTTP " .. tostring(response.StatusCode) .. ": " .. response.Body
end
local decodedOk, decoded = pcall(function()
return HttpService:JSONDecode(response.Body)
end)
if not decodedOk then
return nil, "Resposta JSON inválida."
end
return decoded
end

local function getBackupFolder(folderName)
local folder = ServerStorage:FindFirstChild(folderName)
if folder and not folder:IsA("Folder") then
error("Já existe um objeto incompatível chamado " .. folderName .. ".")
end
if not folder then
folder = Instance.new("Folder")
folder.Name = folderName
folder.Parent = ServerStorage
end
return folder
end

local function getOrCreateFolder(parent, folderName)
local folder = parent:FindFirstChild(folderName)
if folder and not folder:IsA("Folder") then
error("Já existe um objeto incompatível chamado " .. folderName .. ".")
end
if not folder then
folder = Instance.new("Folder")
folder.Name = folderName
folder.Parent = parent
end
return folder
end

local function isCharacterPart(part)
local ancestor = part.Parent
while ancestor and ancestor ~= Workspace do
if ancestor:IsA("Model") and Players:GetPlayerFromCharacter(ancestor) then
return true
end
ancestor = ancestor.Parent
end
return false
end

local function getSpawnPosition()
for _, item in ipairs(Workspace:GetDescendants()) do
if item:IsA("SpawnLocation") then
return item.Position
end
end
return Vector3.zero
end

local function collectTerrainSummary()
if cachedTerrainSummary and os.clock() - lastTerrainSample < TERRAIN_SAMPLE_INTERVAL then
return cachedTerrainSummary
end
local center = getSpawnPosition()
local region = Region3.new(
center - Vector3.new(32, 32, 32),
center + Vector3.new(32, 32, 32)
):ExpandToGrid(4)
local ok, summary = pcall(function()
local materials, occupancies = Workspace.Terrain:ReadVoxels(region, 4)
local dimensions = materials.Size
local minY = region.CFrame.Position.Y - region.Size.Y / 2
local heightmap = {}
local minHeight = nil
local maxHeight = nil
local emptyColumns = 0
for xIndex = 1, dimensions.X, 2 do
local row = {}
for zIndex = 1, dimensions.Z, 2 do
local height = false
for yIndex = dimensions.Y, 1, -1 do
if occupancies[xIndex][yIndex][zIndex] > 0.1
and materials[xIndex][yIndex][zIndex] ~= Enum.Material.Air then
height = minY + (yIndex - 1) * 4
break
end
end
if height == false then
emptyColumns += 1
else
minHeight = minHeight and math.min(minHeight, height) or height
maxHeight = maxHeight and math.max(maxHeight, height) or height
end
table.insert(row, height)
end
table.insert(heightmap, row)
end
return {
range = 64,
sample_step = 8,
heightmap = heightmap,
has_terrain = minHeight ~= nil,
min_height = minHeight or 0,
max_height = maxHeight or 0,
empty_columns = emptyColumns,
}
end)
if not ok then
cachedTerrainSummary = { error = string.sub(tostring(summary), 1, 160) }
else
cachedTerrainSummary = summary
end
lastTerrainSample = os.clock()
return cachedTerrainSummary
end

local function collectState(includeScriptContent)
local instances = {}
for _, item in ipairs(Workspace:GetDescendants()) do
if #instances >= MAX_INSTANCES then
break
end
if item:IsA("BasePart") then
local position = item.Position
table.insert(instances, {
nome = item.Name,
classe = item.ClassName,
y = position.Y,
posicao = string.format("%.1f, %.1f, %.1f", position.X, position.Y, position.Z),
})
end
end

local scriptNames = {}
local scriptsWithContent = {}
local totalScriptChars = 0
local scriptContentLimited = false
for _, item in ipairs(game:GetDescendants()) do
if item:IsA("Script") or item:IsA("LocalScript") or item:IsA("ModuleScript") then
local fullName = item:GetFullName()
if item:IsA("Script") and #scriptNames < MAX_INSTANCES then
if #fullName <= 256 then
table.insert(scriptNames, fullName)
end
end
if includeScriptContent and #scriptsWithContent >= MAX_SCRIPT_COUNT then
scriptContentLimited = true
break
elseif includeScriptContent then
local sourceOk, source = pcall(function()
return item.Source
end)
if sourceOk and type(source) == "string" then
local available = math.max(0, MAX_TOTAL_SCRIPT_CHARS - totalScriptChars)
if available == 0 then
scriptContentLimited = true
break
end
local bounded = string.sub(source, 1, math.min(MAX_SCRIPT_CHARS, available))
if #fullName <= 256 then
totalScriptChars += #bounded
table.insert(scriptsWithContent, {
nome = fullName,
tipo = item.ClassName,
codigo = bounded,
truncado = #bounded < #source,
})
else
scriptContentLimited = true
end
if #bounded < #source then
scriptContentLimited = true
end
else
scriptContentLimited = true
end
end
end
end

return {
motor = "RobloxStudio",
place_id = game.PlaceId,
total_instancias = #instances,
instancias = instances,
scripts_servidor = scriptNames,
scripts_com_conteudo = scriptsWithContent,
scripts_com_conteudo_limitado = scriptContentLimited,
pedir_analise = includeScriptContent,
terreno = collectTerrainSummary(),
}
end

local function sendState(includeScriptContent)
local ok, err = postJson("/estado_jogo", collectState(includeScriptContent == true))
if not ok then
log("Falha ao enviar estado: " .. err)
return false
end
lastStateSent = os.clock()
log("Estado enviado ao Kael.")
return true
end

local function createDraftScript(taskData)
local name = type(taskData.nome) == "string" and string.gsub(taskData.nome, "[^%w_%-]", "") or ""
if #name < 2 or #name > 64 then
error("Nome de script inválido.")
end
local source = type(taskData.codigo) == "string" and taskData.codigo or ""
if #source == 0 or #source > MAX_SCRIPT_CHARS then
error("Código vazio ou acima do limite permitido.")
end
if string.find(source, "loadstring", 1, true) or string.find(source, "getfenv", 1, true) or string.find(source, "setfenv", 1, true) then
error("Código bloqueado por conter chamadas dinâmicas inseguras.")
end

local className = "ModuleScript"
if taskData.tipo_script == "Script" or taskData.tipo_script == "LocalScript" or taskData.tipo_script == "ModuleScript" then
className = taskData.tipo_script
end

local parentContainer = taskData.destino == "shared"
and getOrCreateFolder(ReplicatedStorage, "Kael_DraftScripts")
or getOrCreateFolder(ServerStorage, "Kael_DraftScripts")

local existing = parentContainer:FindFirstChild(name)
if existing then
existing:Destroy()
end

local inst = Instance.new(className)
inst.Name = name
inst.Source = source
inst.Parent = parentContainer
return { nome = name, tipo = className, caminho = inst:GetFullName() }
end

local function executeTask(taskData)
if taskData.tipo == "ping" then
log("PONG!")
return { mensagem = "PONG" }
elseif taskData.tipo == "pedir_visao" then
if not sendState(false) then
error("Não foi possível enviar o estado ao Kael.")
end
return { estado_enviado = true }
elseif taskData.tipo == "enviar_todos_scripts" then
local includeContent = taskData.incluir_conteudo == true
if not sendState(includeContent) then
error("Não foi possível enviar os scripts ao Kael.")
end
return { scripts_enviados = true, conteudo_incluido = includeContent }
elseif taskData.tipo == "criar_script" then
return createDraftScript(taskData)
end
error("Tipo de tarefa não suportado.")
end

local function processTask(taskData)
local success, result = pcall(executeTask, taskData)
local completion = {
task_id = taskData.task_id,
tipo = taskData.tipo,
sucesso = success,
resultado = success and result or {},
erro = success and "" or tostring(result),
}
local posted, postError = postJson("/tarefa_concluida", completion)
if not posted then
log("Falha ao confirmar tarefa " .. tostring(taskData.task_id) .. ": " .. postError)
return
end
if success then
log("Tarefa concluída: " .. tostring(taskData.tipo) .. " (" .. tostring(taskData.task_id) .. ")")
else
log("Tarefa falhou: " .. tostring(result))
end
end

local toolbar = plugin:CreateToolbar("Kael")
local mapButton = toolbar:CreateButton("KaelMap", "Enviar mapa da cena", "")
local pingButton = toolbar:CreateButton("KaelPing", "Testar conexão com Kael", "")
local pollingButton = toolbar:CreateButton("KaelPolling", "Iniciar/parar tarefas do Kael", "")
pollingButton:SetActive(false)

mapButton.Click:Connect(function()
sendState(false)
end)

pingButton.Click:Connect(function()
local response, err = getJson("/studio_status")
if err then
log("Falha de conexão: " .. err)
else
log("Conexão com Kael ativa (protocolo " .. tostring(response.protocol_version) .. ").")
end
end)

pollingButton.Click:Connect(function()
polling = not polling
pollingButton:SetActive(polling)
pollBackoff = 2
log(polling and "Polling iniciado." or "Polling pausado.")
if polling then
task.spawn(function()
while polling do
if not busy then
busy = true
local url = "/proxima_tarefa?protocol_version=1&client_id="
.. HttpService:UrlEncode(clientId)
local response, err = getJson(url)
if err then
log("Falha de polling: " .. err)
postJson("/reportar_erro", {
origem = "polling",
erro = string.sub(err, 1, 2000),
})
pollBackoff = math.min(15, pollBackoff * 2)
else
pollBackoff = 2
if response.status == "ok" and response.tarefa then
processTask(response.tarefa)
elseif response.status == "incompatible" then
log("A versão do protocolo do Kael não é compatível.")
polling = false
pollingButton:SetActive(false)
end
end
if polling and (os.clock() - lastStateSent >= STATE_HEARTBEAT_INTERVAL) then
sendState(false)
end
busy = false
end
task.wait(pollBackoff)
end
end)
end
end)

log("Plugin carregado. Use o botão de polling para conectar ao Kael.")
