#!/usr/bin/env python3
"""Map scraped roster names to Seaglass species — Stage A (name/topology only).

Adapted from ROWE's map_species.py (which resolves against its own local
decomp source, guaranteed to match the compiled ROM it builds from) and from
Unbound-Character-Mode's version (which resolves against a donor project for
a closed-binary hack, same situation we're in here).

We have no public Seaglass source. Circumstantial evidence (Seaglass's own
battle-engine changelog cites "Fairy type, Physical/Special split... from
pokeemerald-expansion") points at Nemo622's private fork descending from
rh-hideout/pokeemerald-expansion (cloned to tools/pokeemerald_expansion_donor/).
See docs/DONOR_CROSSWALK.md for the full writeup of that donor's data layout.

CRITICAL DIFFERENCE from Unbound's donor mapping: Unbound's DPE donor turned
out to have donor-position-equals-numeric-id, verified by spot-check, so its
map_species.py could emit provisional numeric ids. This donor's own
include/constants/species.h runs past SPECIES_GLIMMORA_MEGA (1572+, a large
block of community fan content) with no reason to expect any positional or
numeric alignment with Nemo622's private fork. So THIS script only performs
Stage A: resolving display names to SPECIES_* constants (by name) and
reducing every species to its evolution-family base stage (by name-keyed
topology) -- it does NOT invent a numeric id from the donor. Every species_id
in the output is the literal string "PENDING_PHASE1" until Phase 1 extracts
and confirms real ids from the actual ROM (see docs/SPECIES_CAP.md) and a
follow-up Stage B pass fills them in.

Reads rosters_raw.json, writes:
  - rosters_mapped.json   (character -> sorted base-stage species: SPECIES_*
                            const name + "PENDING_PHASE1" placeholder id)
  - roster_review.csv     (for the user to audit: one row per character/species)
  - unmatched_names.txt   (names that resolved to nothing, for fixing)
  - unresolved_ids.json   (distinguishes "matched a const, no ROM id yet" from
                            "name genuinely unmatched", to drive Phase 1/Stage B)
"""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DONOR = os.path.abspath(os.path.join(HERE, "..", "pokeemerald_expansion_donor"))
FAMILY_DIR = os.path.join(DONOR, "src", "data", "pokemon", "species_info")
FAMILY_FILES = ["gen_%d_families.h" % g for g in range(1, 10)]


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_family_file(path):
    """Yield (SPECIES_const, speciesName, {evolution-target SPECIES_consts})
    for every species block in one gen_N_families.h file.

    Each block looks like:
      [SPECIES_BULBASAUR] =
      {
          ...
          .speciesName = _("Bulbasaur"),
          ...
          .evolutions = EVOLUTION({EVO_LEVEL, 16, SPECIES_IVYSAUR}),
          ...
      },
    Evolution tuples are consistently {EVO_TYPE, param, SPECIES_TARGET, ...},
    optionally with a trailing CONDITIONS(...) 4th field for branching/
    conditional evolutions (e.g. Eevee's Espeon/Umbreon/Leafeon/Glaceon/
    Sylveon branches, some gated behind #if P_GEN_N_CROSS_EVOS). We only
    capture the 3rd-field SPECIES_TARGET -- CONDITIONS(...) contents can
    themselves reference unrelated SPECIES_* constants (e.g. partner-species
    conditions like Mantyke/Remoraid) and must not be picked up as children.
    """
    text = read(path)
    starts = list(re.finditer(r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{", text))
    out = []
    for i, m in enumerate(starts):
        const = m.group(1)
        block_start = m.end()
        block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[block_start:block_end]
        name_m = re.search(r'\.speciesName\s*=\s*_\("([^"]*)"\)', block)
        name = name_m.group(1) if name_m else None
        children = set()
        evo_m = re.search(r"\.evolutions\s*=\s*EVOLUTION\(", block)
        if evo_m:
            captured = []
            for line in block[evo_m.end():].split("\n"):
                if line.strip().startswith(".") and "=" in line:
                    break  # next top-level field -- evolutions region ended
                captured.append(line)
            evo_text = "\n".join(captured)
            for tm in re.finditer(r"\{\s*EVO_[A-Z0-9_]+\s*,\s*[^,]+,\s*(SPECIES_[A-Z0-9_]+)", evo_text):
                children.add(tm.group(1))
        out.append((const, name, children))
    return out


def load_donor():
    """Aggregate all 9 gen_N_families.h files into:
      name_to_const: Bulbapedia-style display name -> SPECIES_* (first
                      occurrence wins, base species precede alt forms)
      parent:        child SPECIES_* -> parent SPECIES_* (evolution edges)
    """
    name_to_const = {}
    parent = {}
    for fname in FAMILY_FILES:
        for const, name, children in parse_family_file(os.path.join(FAMILY_DIR, fname)):
            if name and name not in name_to_const:
                name_to_const[name] = const
            for child in children:
                if child != const:
                    parent.setdefault(child, const)
    return name_to_const, parent


def first_stage_map(parent):
    """SPECIES_X -> base-stage SPECIES_Y, walking the parent map to a fixed
    point. Same technique as ROWE's/Unbound's map_species.py, just built from
    this donor's per-file inline evolution data instead of one flat table."""
    base = {}
    def find_base(c):
        seen = set()
        while c in parent and c not in seen:
            seen.add(c)
            c = parent[c]
        return c
    for child in list(parent):
        base[child] = find_base(child)
    return base


# Bulbapedia name -> donor speciesName divergences.
#
# Unlike ROWE's decomp (10-char engine cap) and Unbound's DPE donor (also
# 10-char, different truncation convention), THIS donor stores FULL
# (untruncated) species names -- rh-hideout/pokeemerald-expansion lifts the
# classic name-length cap. Verified directly: "Crabominable", "Fletchinder",
# "Meowscarada", "Nidoran♀"/"Nidoran♂", "Flabébé", "Mime Jr.", "Farfetch'd",
# "Mr. Mime", "Type: Null", "Porygon-Z" all appear in the donor exactly as
# Bulbapedia spells them. So this dict is expected to stay near-empty --
# only add an entry if a genuine mismatch shows up in unmatched_names.txt.
# NOTE: this says nothing about what Seaglass's own in-game strings actually
# are -- that's unknown until Phase 1 reads the real ROM, and Seaglass's own
# name buffer may still be 10-char-capped even if this donor's isn't.
NAME_FIXES = {
}

# Manual const overrides for species whose block in the donor is generated by
# a form-table macro (e.g. `[SPECIES_UNOWN] = UNOWN_MISC_INFO(...)` instead of
# a literal `[SPECIES_X] = { ... }`) -- parse_family_file()'s block-boundary
# regex requires a literal `{` right after `=` and misses these, even though
# the name text itself is present verbatim inside the macro body. All ten are
# multi-form species (Arceus plates, Unown letters, Vivillon/Spewpa/Flabébé/
# Furfrou/Minior/Genesect/Silvally/Mothim form variants). Where a species
# actually evolves FROM another (Mothim from Burmy, Silvally from Type: Null),
# the override points at the specific form constant the donor's evolution
# table actually targets (SPECIES_MOTHIM_PLANT / SPECIES_SILVALLY_NORMAL, not
# the bare SPECIES_MOTHIM / SPECIES_SILVALLY alias) so first_stage_map() can
# still find the real parent edge; the rest point at their plain alias since
# they have no incoming evolution to preserve.
#
# KNOWN LIMITATION: Scatterbug/Spewpa/Vivillon's own multi-form blocks are
# ALL macro-generated (no literal `{`), so the Scatterbug->Spewpa->Vivillon
# chain's evolution edges are themselves unrecoverable by this parser -- both
# stay self-mapped (not reduced to Scatterbug). Likewise a handful of Flabébé
# color-form -> Floette color-form -> Florges color-form chains only reduce
# as far as whichever specific color variant's edges happen to be capturable,
# not consistently to the "default"/red-flower base. This is acceptable for
# Stage A (provisional, pending Phase 1 ROM verification anyway) but should
# be spot-checked in roster_review.csv for any character carrying these
# species (Viola/Vivillon, Tulip/Florges) before Stage B locks in real ids.
MACRO_FORM_CONST_OVERRIDES = {
    "Arceus": "SPECIES_ARCEUS",
    "Flabébé": "SPECIES_FLABEBE",
    "Furfrou": "SPECIES_FURFROU",
    "Genesect": "SPECIES_GENESECT",
    "Minior": "SPECIES_MINIOR",
    "Mothim": "SPECIES_MOTHIM_PLANT",
    "Silvally": "SPECIES_SILVALLY_NORMAL",
    "Spewpa": "SPECIES_SPEWPA",
    "Unown": "SPECIES_UNOWN",
    "Vivillon": "SPECIES_VIVILLON",
}

# Known signature/ace Pokemon per character (any stage; resolved to the
# family's first stage below). Characters absent here get a random starter.
# Reused verbatim from ROWE's SIGNATURES dict (same real-world characters,
# same signatures, full Gen 1-9 scope matching this project's characters.txt).
SIGNATURES = {
 "Red":"Pikachu","Leaf":"Eevee","Blue":"Pidgeot","Lance":"Dragonite",
 "Lorelei":"Lapras","Bruno":"Machamp","Agatha":"Gengar","Koga":"Weezing",
 "Brock":"Onix","Misty":"Starmie","Lt. Surge":"Pikachu","Erika":"Vileplume",
 "Sabrina":"Alakazam","Blaine":"Arcanine","Giovanni":"Rhydon","Ash":"Pikachu",
 "Gary":"Blastoise","Ritchie":"Pikachu","Tracey":"Scyther","Jessie":"Ekans",
 "James":"Weezing",
 "Ethan":"Cyndaquil","Kris":"Totodile","Lyra":"Chikorita","Silver":"Totodile",
 "Falkner":"Hoothoot","Bugsy":"Scyther","Whitney":"Miltank","Morty":"Gengar",
 "Chuck":"Poliwrath","Jasmine":"Steelix","Pryce":"Piloswine","Clair":"Kingdra",
 "Will":"Xatu","Karen":"Umbreon","Janine":"Ariados","Archer":"Houndoom",
 "Ariana":"Arbok",
 "Brendan":"Treecko","May":"Blaziken","Wally":"Gallade","Steven":"Metagross",
 "Wallace":"Milotic","Sidney":"Absol","Phoebe":"Dusclops","Glacia":"Walrein",
 "Drake":"Salamence","Roxanne":"Nosepass","Brawly":"Hariyama","Wattson":"Manectric",
 "Flannery":"Torkoal","Norman":"Slaking","Winona":"Altaria","Tate":"Solrock",
 "Liza":"Lunatone","Juan":"Kingdra","Maxie":"Camerupt","Archie":"Sharpedo",
 "Drew":"Roserade",
 "Lucas":"Turtwig","Dawn":"Piplup","Barry":"Empoleon","Cynthia":"Garchomp",
 "Aaron":"Drapion","Bertha":"Hippowdon","Flint":"Infernape","Lucian":"Bronzong",
 "Roark":"Rampardos","Gardenia":"Roserade","Maylene":"Lucario","Crasher Wake":"Floatzel",
 "Fantina":"Mismagius","Byron":"Bastiodon","Candice":"Froslass","Volkner":"Shinx",
 "Cyrus":"Weavile","Mars":"Purugly","Jupiter":"Skuntank","Saturn":"Toxicroak",
 "Paul":"Electivire","Zoey":"Glameow","Nando":"Roserade",
 "Hilbert":"Oshawott","Hilda":"Tepig","Rosa":"Snivy","Cheren":"Stoutland",
 "Bianca":"Emboar","N":"Zorua","Alder":"Volcarona","Iris":"Haxorus",
 "Cilan":"Pansage","Chili":"Pansear","Cress":"Panpour","Lenora":"Watchog",
 "Burgh":"Leavanny","Elesa":"Zebstrika","Clay":"Excadrill","Skyla":"Swanna",
 "Brycen":"Beartic","Drayden":"Haxorus","Roxie":"Whirlipede","Marlon":"Jellicent",
 "Shauntal":"Chandelure","Marshal":"Conkeldurr","Grimsley":"Bisharp","Caitlin":"Gothitelle",
 "Ghetsis":"Hydreigon","Colress":"Klinklang","Trip":"Serperior",
 "Serena":"Fennekin","Shauna":"Chespin","Diantha":"Gardevoir","Malva":"Talonflame",
 "Siebold":"Clawitzer","Wikstrom":"Aegislash","Drasna":"Noivern","Viola":"Vivillon",
 "Grant":"Tyrunt","Korrina":"Lucario","Ramos":"Gogoat","Clemont":"Heliolisk",
 "Valerie":"Sylveon","Olympia":"Meowstic","Wulfric":"Avalugg","Lysandre":"Gyarados",
 "Alain":"Charizard","Sawyer":"Sceptile",
 "Elio":"Popplio","Selene":"Rowlet","Kukui":"Incineroar","Hau":"Raichu",
 "Molayne":"Dugtrio","Kahili":"Toucannon","Acerola":"Palossand","Hala":"Crabominable",
 "Olivia":"Lycanroc","Nanu":"Persian","Hapu":"Mudsdale","Gladion":"Type: Null",
 "Guzma":"Golisopod","Plumeria":"Salazzle","Lusamine":"Bewear","Lillie (anime)":"Vulpix",
 "Kiawe (anime)":"Turtonator","Lana (anime)":"Popplio","Mallow (anime)":"Tsareena",
 "Sophocles":"Togedemaru",
 "Leon":"Charizard","Milo":"Eldegoss","Nessa":"Drednaw","Kabu":"Centiskorch",
 "Bea":"Machamp","Allister":"Gengar","Opal":"Alcremie","Gordie":"Coalossal",
 "Melony":"Lapras","Piers":"Obstagoon","Raihan":"Duraludon","Hop":"Dubwool",
 "Bede":"Hatterene","Marnie":"Morpeko","Rose":"Copperajah","Goh":"Cinderace",
 "Chloe":"Eevee",
 "Geeta":"Glimmora","Nemona":"Pawmot","Rika":"Clodsire","Poppy":"Tinkaton",
 "Hassel":"Baxcalibur","Katy":"Teddiursa","Brassius":"Sudowoodo","Iono":"Bellibolt",
 "Kofu":"Crabominable","Larry":"Staraptor","Ryme":"Toxtricity","Tulip":"Florges",
 "Grusha":"Cetitan","Arven":"Mabosstiff","Penny":"Sylveon",
}

# Signatures used as the EXACT species (not reduced to first stage):
# these characters' partner is famously the mid-stage itself.
SIGNATURES_EXACT = {"Red", "Lt. Surge", "Ash", "Ritchie"}


def main():
    with open(os.path.join(HERE, "rosters_raw.json")) as f:
        raw = json.load(f)

    name_to_const, parent = load_donor()
    base = first_stage_map(parent)
    unmatched = set()
    mapped = {}

    def resolve_const(name):
        fixed = NAME_FIXES.get(name, name)
        const = name_to_const.get(fixed)
        if const is None:
            const = MACRO_FORM_CONST_OVERRIDES.get(fixed)
        return const

    for disp, info in sorted(raw.items()):
        consts = set()
        for name in info["species"]:
            const = resolve_const(name)
            if const is None:
                unmatched.add(name)
                continue
            consts.add(base.get(const, const))
        species_list = sorted(consts)
        entry = {"page": info["page"], "category": info["category"],
                 "gen": info.get("gen", 0),
                 "species": [{"const": c, "id": "PENDING_PHASE1"} for c in species_list]}
        ace = SIGNATURES.get(disp)
        if ace:
            const = resolve_const(ace)
            if const is None:
                print("SIGNATURE UNRESOLVED: %s -> %s" % (disp, ace))
            else:
                sig_base = base.get(const, const)
                sig = const if disp in SIGNATURES_EXACT else sig_base
                if sig_base in consts:
                    entry["signature"] = {"const": sig, "id": "PENDING_PHASE1"}
                else:
                    print("SIGNATURE NOT ON ROSTER: %s -> %s (%s)" % (disp, ace, sig_base))
        mapped[disp] = entry

    with open(os.path.join(HERE, "rosters_mapped.json"), "w") as f:
        json.dump(mapped, f, indent=1, sort_keys=True)

    with open(os.path.join(HERE, "roster_review.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["character", "category", "base_species", "species_id", "keep(Y/n)"])
        for disp, info in sorted(mapped.items()):
            for c in info["species"]:
                w.writerow([disp, info["category"], c["const"], c["id"], "Y"])

    with open(os.path.join(HERE, "unmatched_names.txt"), "w") as f:
        f.write("\n".join(sorted(unmatched)) + "\n")

    all_species_consts = sorted({c["const"] for info in mapped.values() for c in info["species"]})
    with open(os.path.join(HERE, "unresolved_ids.json"), "w") as f:
        json.dump({
            "pending_phase1_species": all_species_consts,
            "unmatched_names": sorted(unmatched),
        }, f, indent=1)

    empty = [d for d, i in mapped.items() if not i["species"]]
    print("mapped %d characters; %d unmatched names; %d empty rosters%s"
          % (len(mapped), len(unmatched), len(empty),
             (": " + ", ".join(empty)) if empty else ""))
    print("\nSTAGE A COMPLETE (name/topology only, %d distinct species). All species_id"
          % len(all_species_consts))
    print("values are \"PENDING_PHASE1\" -- Stage B (real numeric ROM ids) requires")
    print("Phase 1 reverse-engineering of the actual Seaglass ROM; see docs/SPECIES_CAP.md.")


if __name__ == "__main__":
    main()
