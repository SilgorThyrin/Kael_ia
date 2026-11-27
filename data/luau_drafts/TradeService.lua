-- ServerScriptService/TradeService.lua
local TradeService = {}

local activeTrades: { [string]: table } = {}

local function getTradeKey(p1: Player, p2: Player): string
local a, b = math.min(p1.UserId, p2.UserId), math.max(p1.UserId, p2.UserId)
return string.format("%d_%d", a, b)
end

function TradeService.StartTrade(p1: Player, p2: Player): (boolean, string?)
if p1 == p2 then
return false, "Não é possível negociar consigo mesmo"
end
local key = getTradeKey(p1, p2)
if activeTrades[key] then
return false, "Troca já em andamento"
end

activeTrades[key] = {
offers = { [p1.UserId] = 0, [p2.UserId] = 0 },
confirmed = { [p1.UserId] = false, [p2.UserId] = false },
}
return true, key
end

function TradeService.SetAetheriumOffer(key: string, player: Player, amount: number): (boolean, string?)
local trade = activeTrades[key]
if not trade then
return false, "Troca não encontrada"
end
local cleanAmount = math.max(0, math.floor(tonumber(amount) or 0))
local balance = player:GetAttribute("Aetherium") or 0
if cleanAmount > balance then
return false, "Saldo de Aetherium insuficiente"
end

trade.offers[player.UserId] = cleanAmount
-- Zera confirmações sempre que qualquer oferta muda
for uid in pairs(trade.confirmed) do
trade.confirmed[uid] = false
end
return true, nil
end

function TradeService.ConfirmTrade(key: string, p1: Player, p2: Player, actor: Player): (boolean, string?)
local trade = activeTrades[key]
if not trade then
return false, "Troca não encontrada"
end
trade.confirmed[actor.UserId] = true

if not (trade.confirmed[p1.UserId] and trade.confirmed[p2.UserId]) then
return true, "Aguardando confirmação do outro jogador"
end

local offer1 = trade.offers[p1.UserId] or 0
local offer2 = trade.offers[p2.UserId] or 0
local bal1 = p1:GetAttribute("Aetherium") or 0
local bal2 = p2:GetAttribute("Aetherium") or 0

if offer1 > bal1 or offer2 > bal2 then
activeTrades[key] = nil
return false, "Saldo insuficiente no fechamento; troca cancelada"
end

p1:SetAttribute("Aetherium", bal1 - offer1 + offer2)
p2:SetAttribute("Aetherium", bal2 - offer2 + offer1)
activeTrades[key] = nil
return true, "Troca concluída"
end

function TradeService.CancelTrade(key: string)
activeTrades[key] = nil
end

return TradeService
