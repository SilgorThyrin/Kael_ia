-- ServerScriptService/FastTravelService.lua
local FastTravelService = {}

local COOLDOWN_SECONDS = 8
local unlockedSanctuaries: { [number]: { [string]: boolean } } = {}
local lastTravelAt: { [number]: number } = {}

function FastTravelService.UnlockSanctuary(player: Player, sanctuaryId: string)
local uid = player.UserId
if not unlockedSanctuaries[uid] then
unlockedSanctuaries[uid] = {}
end
unlockedSanctuaries[uid][sanctuaryId] = true
end

function FastTravelService.CanTravel(player: Player, sanctuaryId: string): (boolean, string?)
if player:GetAttribute("InCombat") == true then
return false, "Bloqueado em combate"
end
local uid = player.UserId
if not unlockedSanctuaries[uid] or not unlockedSanctuaries[uid][sanctuaryId] then
return false, "Santuário não desbloqueado"
end
local prev = lastTravelAt[uid] or -math.huge
if (os.clock() - prev) < COOLDOWN_SECONDS then
return false, "Aguarde a recarga do teleporte"
end
return true, nil
end

function FastTravelService.TravelTo(player: Player, sanctuaryId: string, targetCFrame: CFrame, mountService: table?): (boolean, string?)
local ok, reason = FastTravelService.CanTravel(player, sanctuaryId)
if not ok then
return false, reason
end

local char = player.Character
local root = char and char:FindFirstChild("HumanoidRootPart")
if not root or not root:IsA("BasePart") then
return false, "Personagem indisponível"
end

if mountService and mountService.Dismount then
mountService.Dismount(player)
end

lastTravelAt[player.UserId] = os.clock()
root.CFrame = targetCFrame + Vector3.new(0, 3, 0)
return true, nil
end

return FastTravelService
