# GDD — Ecos de Aethelgard (placeId: 105458200861912)

## 1. Visão Geral
- RPG de mundo aberto (64 km²) no Roblox Studio.
- Combate dinâmico em tempo real com leitura tática de padrões, cooldowns e posicionamento.

## 2. Loop Principal
- Explorar o mundo (montarias e fast travel) -> Minerar Aetherium -> Enfrentar Corrupted Echoes (R15) -> Evoluir/negociar via comércio P2P.

## 3. Arquitetura Luau Estruturada (`ServerScriptService`)
- **AetheriumService:** nós nas 4 raridades (Comum, Raro, Épico, Lendário), multiplicadores de coleta, respawn e validação de distância.
- **CorruptedEchoAI / EcoMenorIA:** máquina de estados (Idle, Patrol, Chase, Attack, Return) com escala de combate e drop único via `RewardClaimed`.
- **MagicService + MagicAndEchoBridge:** feitiços (`ProjAetherium`, `EscudoMana`, `CuraAetherium`), regeneração de mana, absorção de dano e entrega de Aetherium ao derrotar ecos.
- **MountService:** montarias (`CorcelAether`, `LoboSombrio`) com bloqueio/desmontagem automática em combate e restauração de atributos.
- **FastTravelService:** santuários desbloqueáveis por jogador, cooldown de teleporte e bloqueio em combate.
- **TradeService:** comércio P2P de Aetherium com trava de oferta, confirmação dupla e validação atômica de saldo.
