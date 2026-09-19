# The egg-only party corner — KNOWN, MEASURED, DELIBERATELY LEFT

**Status: not a bug to fix. The user decided on 2026-09-18 to document this
corner and leave the behaviour exactly as it is.** If you are reading this
because the code "looks wrong", read to the end before changing anything — the
obvious fix is a trade-off that was considered and rejected.

Full account: `game_plans/rowe_parity.md` §13.47 (found) and §13.48 (measured).

## What it is

`CharacterMode_SweepPartyToPC` (`src/character_mode.c`) never empties the
party: a pre-scan sets a `kept` flag if any party member is on-roster **or is an
egg**, and the second pass only boxes off-roster mons once something is
guaranteed to remain.

**An egg counts.** So a party of `[egg, off-roster mon]` has `kept` set *by the
egg*, the off-roster mon is boxed, and the player is left holding **nothing but
an egg**.

## Why the engine cannot normally produce this

Gen 3 storage refuses to deposit your last battle-capable mon, and an egg is not
battle-capable. But **that check happens at DEPOSIT time**, and the sweep runs
afterwards — on PC exit — calling the PC routine directly, with no such check.
So the sweep can produce a party state the engine itself forbids.

Reachable in ordinary play, no exploit required:

1. Party is `[signature, off-roster mon, egg]`.
2. Deposit the signature. The engine allows it: the off-roster mon is still able.
3. Exit the PC. The shipped sweep boxes the off-roster mon.
4. Party is `[egg]`.

## What actually happens — MEASURED, not reasoned

Measured live 2026-09-18 on a test ROM that gives two eggs from the ROM's own
`giveegg` and then starts a real wild battle with the ROM's own `setwildbattle`
/ `dowildbattle`. **The engine sends the egg out and the battle is fully
playable:**

- `Go! Egg!`, a black egg silhouette on the player's side
- a health bar reading `Egg ♀ Lv1 HP 11/11`
- `What will Egg do?` with the full Fight / Bag / Pokémon / Run menu
- **Run works** — `Got away safely!`
- **Fight works** — the move list offers a real move (`Water Sport`, 15/15),
  i.e. the egg fights as its hidden underlying species

**No crash. No hang. No softlock. Always escapable.**

## The actual cost

A **spoiler**, and only that. The battle exposes the unhatched egg's gender,
level, HP and move list — and the move usually identifies the species outright.
That is information an egg is meant to hide.

It is also self-limiting: walking hatches the egg, and the egg-hatch tail's own
sweep keeps the hatchling under the same never-empty rule.

## Why it was left, and what NOT to do

⛔ **Do not "fix" this by requiring a non-egg kept mon.** That is not a bug fix,
it is a trade-off: the sweep would then keep an **off-roster** mon in the party
rather than create an egg-only party — enforcement deliberately losing in this
corner, permanently, to prevent a cosmetic spoiler the player has to construct
on purpose. Weighed against the measured severity, that trade was rejected.

⚠️ Present in **all five games, including ROWE**, the reference implementation
the ports inherited it from. It is not a porting error, and it survived ROWE's
own adversarial sweep. Whichever way this is ever decided, it must be decided
five times.
