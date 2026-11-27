-- ServerScriptService/MountService.lua
local MountService = {}

MountService.Mounts = {
CorcelAether = { speed = 42, jumpPower = 55 },
LoboSombrio = { speed = 48, jumpPower = 60 },
}

local activeMounts: { [number]: string } = {}
local baseStats: { [number]: { speed: number, jump: number } } = {}

function MountService.Mount(player: Player, mountId: string): (boolean, string?)
local spec = MountService.Mounts[mountId]
if not spec then
return false, "Montaria inválida"
end
if player:GetAttribute("InCombat") == true then
return false, "Não é possível montar em combate"
end

local char = player.Character
local hum = char and char:FindFirstChildOfClass("Humanoid")
if not hum or hum.Health <= 0 then
return false, "Personagem indisponível"
end

local uid = player.UserId
if not baseStats[uid] then
baseStats[uid] = { speed = hum.WalkSpeed, jump = hum.JumpPower }
end

activeMounts[uid] = mountId
hum.WalkSpeed = spec.speed
hum.JumpPower = spec.jumpPower
player:SetAttribute("Mounted", true)
return true, nil
end

function MountService.Dismount(player: Player)
local uid = player.UserId
if not activeMounts[uid] then
return
end
activeMounts[uid] = nil
player:SetAttribute("Mounted", false)

local char = player.Character
local hum = char and char:FindFirstChildOfClass("Humanoid")
local saved = baseStats[uid]
if hum and saved then
hum.WalkSpeed = saved.speed
hum.JumpPower = saved.jump
end
baseStats[uid] = nil
end

return MountService
