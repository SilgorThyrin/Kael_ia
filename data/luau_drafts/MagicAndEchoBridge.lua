-- ServerScriptService/MagicAndEchoBridge.lua
local Players = game:GetService("Players")

local MagicAndEchoBridge = {}

function MagicAndEchoBridge.HandleSpellRequest(magicService, player: Player, spellName: string, targetModel: Model?)
local targetHumanoid: Humanoid? = nil
if targetModel and targetModel:IsA("Model") then
local hum = targetModel:FindFirstChildOfClass("Humanoid")
if hum and hum.Health > 0 then
targetHumanoid = hum
end
end

local ok, data = magicService.CastSpell(player, spellName, targetHumanoid)
return ok, data
end

function MagicAndEchoBridge.HandleIncomingEchoHit(magicService, player: Player, rawDamage: number): number
local finalDamage = magicService.AbsorbDamage(player, rawDamage)
local char = player.Character
local hum = char and char:FindFirstChildOfClass("Humanoid")
if hum and hum.Health > 0 and finalDamage > 0 then
hum:TakeDamage(finalDamage)
end
return finalDamage
end

function MagicAndEchoBridge.BindEcoMenorDefeat(magicService, echoModel: Model, baseDrop: number?, zoneMultiplier: number?, onReward: ((Player, number) -> ())?)
if not echoModel or not echoModel:IsA("Model") then
return
end
local humanoid = echoModel:FindFirstChildOfClass("Humanoid")
if not humanoid then
return
end

humanoid.Died:Connect(function()
local creatorTag = humanoid:FindFirstChild("creator")
local killerPlayer: Player? = nil
if creatorTag and creatorTag:IsA("ObjectValue") and creatorTag.Value and creatorTag.Value:IsA("Player") then
killerPlayer = creatorTag.Value
end

local dropped = magicService.OnCorruptedEchoDefeated(echoModel, killerPlayer, baseDrop, zoneMultiplier)
if killerPlayer and dropped > 0 and onReward then
onReward(killerPlayer, dropped)
end

task.delay(4, function()
if echoModel and echoModel.Parent then
echoModel:Destroy()
end
end)
end)
end

return MagicAndEchoBridge
