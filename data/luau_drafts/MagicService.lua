local MagicService = {}

MagicService.Spells = {
ProjAetherium = {
manaCost = 20,
cooldown = 1.2,
baseDamage = 28,
},
EscudoMana = {
manaCost = 25,
cooldown = 6.0,
duration = 8.0,
shieldAmount = 45,
},
CuraAetherium = {
manaCost = 30,
cooldown = 5.0,
healAmount = 35,
},
}

local playerMana: { [number]: number } = {}
local playerMaxMana: { [number]: number } = {}
local lastCastAt: { [string]: number } = {}
local activeShields: { [number]: number } = {}

function MagicService.InitPlayer(player: Player, maxMana: number?)
local cap = math.max(50, tonumber(maxMana) or 100)
playerMaxMana[player.UserId] = cap
playerMana[player.UserId] = cap
end

function MagicService.ClearPlayer(player: Player)
playerMana[player.UserId] = nil
playerMaxMana[player.UserId] = nil
activeShields[player.UserId] = nil
local prefix = tostring(player.UserId) .. ":"
for key in pairs(lastCastAt) do
if string.sub(key, 1, #prefix) == prefix then
lastCastAt[key] = nil
end
end
end

function MagicService.RegenMana(player: Player, amount: number)
local uid = player.UserId
local maxM = playerMaxMana[uid] or 100
local curM = playerMana[uid] or maxM
playerMana[uid] = math.min(maxM, math.max(0, curM + math.max(0, amount)))
end

function MagicService.CanCast(player: Player, spellName: string, now: number?): (boolean, string?)
local spec = MagicService.Spells[spellName]
if not spec then
return false, "Feitiço inválido"
end

local t = now or os.clock()
local cdKey = string.format("%d:%s", player.UserId, spellName)
local prev = lastCastAt[cdKey] or -math.huge
if (t - prev) < spec.cooldown then
return false, "Em recarga"
end

local curMana = playerMana[player.UserId] or 0
if curMana < spec.manaCost then
return false, "Mana insuficiente"
end

return true, nil
end

function MagicService.CastSpell(player: Player, spellName: string, targetHumanoid: Humanoid?): (boolean, table?)
local ok, reason = MagicService.CanCast(player, spellName)
if not ok then
return false, { error = reason }
end

local spec = MagicService.Spells[spellName]
local uid = player.UserId
playerMana[uid] = math.max(0, (playerMana[uid] or 0) - spec.manaCost)
lastCastAt[string.format("%d:%s", uid, spellName)] = os.clock()

if spellName == "ProjAetherium" then
if targetHumanoid and targetHumanoid.Health > 0 then
targetHumanoid:TakeDamage(spec.baseDamage)
end
return true, { spell = spellName, damage = spec.baseDamage, manaRemaining = playerMana[uid] }
elseif spellName == "EscudoMana" then
activeShields[uid] = spec.shieldAmount
task.delay(spec.duration, function()
if activeShields[uid] ~= nil then
activeShields[uid] = nil
end
end)
return true, { spell = spellName, shield = spec.shieldAmount, duration = spec.duration, manaRemaining = playerMana[uid] }
elseif spellName == "CuraAetherium" then
local char = player.Character
local hum = char and char:FindFirstChildOfClass("Humanoid")
if hum and hum.Health > 0 then
hum.Health = math.min(hum.MaxHealth, hum.Health + spec.healAmount)
end
return true, { spell = spellName, healed = spec.healAmount, manaRemaining = playerMana[uid] }
end

return false, { error = "Execução não suportada" }
end

function MagicService.AbsorbDamage(player: Player, incomingDamage: number): number
local dmg = math.max(0, tonumber(incomingDamage) or 0)
local shield = activeShields[player.UserId] or 0
if shield <= 0 then
return dmg
end

local absorbed = math.min(shield, dmg)
local remainingShield = shield - absorbed
activeShields[player.UserId] = remainingShield > 0 and remainingShield or nil
return math.max(0, dmg - absorbed)
end

function MagicService.OnCorruptedEchoDefeated(echoModel: Model, killerPlayer: Player?, baseDrop: number?, zoneMultiplier: number?)
if not echoModel or echoModel:GetAttribute("RewardClaimed") == true then
return 0
end
echoModel:SetAttribute("RewardClaimed", true)

local base = math.max(0, tonumber(baseDrop) or 2)
local mult = math.max(1, tonumber(zoneMultiplier) or 1)
local amount = math.floor(base * mult + 0.5)

if killerPlayer and amount > 0 then
local curAetherium = killerPlayer:GetAttribute("Aetherium") or 0
killerPlayer:SetAttribute("Aetherium", curAetherium + amount)
end

return amount
end

return MagicService
