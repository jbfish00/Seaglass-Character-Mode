# Donor Crosswalk — `rh-hideout/pokeemerald-expansion`

`tools/pokeemerald_expansion_donor/` is a shallow (`--depth 1`) clone of `https://github.com/rh-hideout/pokeemerald-expansion` (`master` branch, cloned 2026-07-12). Gitignored, regenerable via `git clone`.

**Role**: name and evolution-topology reference only for `tools/character_mode/map_species.py`'s Stage A. This mirrors the role `Dynamic-Pokemon-Expansion` played for `Unbound-Character-Mode`, but with a stronger caveat (see below) — do not extend its use beyond what's documented here without updating this file.

## Why this donor

Seaglass's own marketing/changelog states it "includes changes from pokeemerald-expansion to update the battle engine, such as Fairy type and Physical/Special split" — strong circumstantial evidence Nemo622's private fork descends from this project at some point, even though Nemo622's own source was never made public. `rh-hideout/pokeemerald-expansion` is the real, active (748★) org/repo for this project (not `rh-hero`, which does not exist).

## Data layout (verified 2026-07-12, differs from both ROWE and the Unbound/DPE donor)

- No flat `species_names.h` or `gEvolutionTable[NUM_SPECIES][EVOS_PER_MON]` array like ROWE/pret's classic layout.
- Species names and evolution data live inline, per species, across 9 files:
  `src/data/pokemon/species_info/gen_1_families.h` through `gen_9_families.h`
  (all `#include`d and aggregated into `const struct SpeciesInfo gSpeciesInfo[]` by `src/data/pokemon/species_info.h`).
- Each species is a block: `[SPECIES_X] = { ..., .speciesName = _("Name"), ..., .evolutions = EVOLUTION({EVO_TYPE, param, SPECIES_TARGET}, {EVO_TYPE, param, SPECIES_TARGET, CONDITIONS(...)}, ...), ... }`.
- Evolution tuples are consistently 3+ fields: `{EVO_TYPE, param, SPECIES_TARGET}`, optionally followed by a 4th `CONDITIONS(...)` field for conditional/branching evolutions (verified: all 650 `{EVO_` tuples across the 9 files match this shape, no 2-field outliers). Many evolutions are wrapped in `#if P_GEN_N_CROSS_EVOS` blocks (e.g. Eevee's Espeon/Umbreon/Leafeon/Glaceon/Sylveon branches) — these are still valid text to scan even though they're conditionally compiled, since we only need topology, not which build flags Seaglass itself set.
- Parsing approach: for each species block, capture the `.evolutions = EVOLUTION(...)` region (line-bounded: from the line containing `.evolutions = EVOLUTION(` until the next line that is a new top-level `.field =` assignment), then regex `\{EVO_[A-Z0-9_]+,\s*[^,]+,\s*SPECIES_[A-Z0-9_]+` across that region and take the captured `SPECIES_*` token as a child of the enclosing species. This deliberately ignores `CONDITIONS(...)` contents (which can themselves reference unrelated `SPECIES_*` constants, e.g. partner-species conditions like Mantyke/Remoraid) since those appear *after* the 2nd comma's target capture, not before.
- This is the same parent→child evolution-family topology ROWE's `map_species.py` (`first_stage_map()`) already reduces to first-evolution-stage, just re-targeted at this per-file inline format instead of one flat table literal.

## Numeric ID caveat — read before using `SPECIES_*` values from this donor

`include/constants/species.h` in this donor enumerates species up through `SPECIES_GLIMMORA_MEGA = 1572` (a large community-maintained block of fan Mega evolutions/regional forms/etc. — `NUM_SPECIES` here is `SPECIES_EGG`, defined as `SPECIES_CUSTOM_END`, i.e. past all of that fan content). There is **no reason to expect** Nemo622's private Seaglass fork — presumably forked at some earlier, unknown commit, and presumably without most or all of that fan-mega content — has matching numeric IDs.

This is a materially weaker guarantee than Unbound had with its DPE donor, where donor-position-equals-id held up under spot-checks (see `Unbound-Character-Mode/CLAUDE.md`). **Assume zero numeric alignment for Seaglass** until Phase 1 empirically tests it against the real ROM's species name table (see `docs/SPECIES_CAP.md`).

Consequence for the pipeline: `tools/character_mode/map_species.py` Stage A output must never carry a donor-derived numeric ID as if it were usable — `rosters_mapped.json` entries carry `"species_id": "PENDING_PHASE1"` until Stage B (gated on Phase 1) supplies a real, ROM-verified id.
