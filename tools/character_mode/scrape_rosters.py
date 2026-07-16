#!/usr/bin/env python3
"""Scrape each character's documented Pokemon from Bulbapedia.

Reads characters.txt, queries the Bulbapedia MediaWiki API for the "Pokémon"
sections of each character page, and extracts every species mentioned in
ownership templates/links. Responses are cached under cache/ so re-runs are
offline. Output: rosters_raw.json (display name -> {page, category, species}).

Usage: python3 tools/character_mode/scrape_rosters.py [--only "Name"]
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
API = "https://bulbapedia.bulbagarden.net/w/api.php"
UA = "ROWE-character-mode-research/1.0 (personal ROM hack project; low volume)"

# Sections worth scraping on both game and anime character pages.
SECTION_HINTS = ("pokémon", "pokemon", "on hand", "in rotation", "at professor",
                 "in training", "released", "traded", "given away", "at home",
                 "status unknown", "temporary", "befriended", "borrowed", "team",
                 "battled", "used", "ride")


def api_get(params, cache_key):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r"[^\w.-]", "_", cache_key) + ".json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    params = dict(params, format="json", redirects="1")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    with open(path, "w") as f:
        json.dump(data, f)
    time.sleep(1.0)  # be polite
    return data


def get_sections(page):
    data = api_get({"action": "parse", "page": page, "prop": "sections"},
                   "sections_" + page)
    if "error" in data:
        return None
    return data["parse"]["sections"]


def get_section_wikitext(page, index):
    data = api_get({"action": "parse", "page": page, "prop": "wikitext",
                    "section": str(index)}, "wt_%s_%s" % (page, index))
    if "error" in data:
        return ""
    return data["parse"]["wikitext"]["*"]


SPECIES_PATTERNS = [
    re.compile(r"\{\{[pP]\|([^}|]+)"),                  # {{p|Pikachu}}
    re.compile(r"\|\s*pokemon\s*=\s*([^|}\n]+)"),        # |pokemon=Starmie
    re.compile(r"\{\{TP\|[^|]+\|([^}|]+)"),              # {{TP|Misty|Staryu}}
    re.compile(r"\{\{OP\|[^|]+\|([^}|]+)"),              # {{OP|Ash|Pikachu}}
    re.compile(r"\{\{AOP\|[^|]+\|([^}|]+)", re.I),       # anime owned pokemon
    re.compile(r"'s\s+([A-Z][A-Za-zé'.♀♂: 2-]+?)(?:\]\]|\|)"),  # [[Ash's Pikachu]] / [[Misty's Staryu|Staryu]]
]


def extract_species(wikitext, valid_names):
    found = set()
    for pat in SPECIES_PATTERNS:
        for m in pat.finditer(wikitext):
            name = m.group(1).strip()
            name = re.sub(r"<[^>]*>", "", name)
            if name in valid_names:
                found.add(name)
    return found


def load_valid_names():
    """All species display names, from Bulbapedia's own list (cached)."""
    names = set()
    data = api_get({"action": "parse", "page": "List of Pokémon by National Pokédex number",
                    "prop": "wikitext"}, "natdex_list")
    wt = data["parse"]["wikitext"]["*"]
    for m in re.finditer(r"\{\{rdex\|[^|]*\|[^|]*\|([^|}]+)", wt):
        names.add(m.group(1).strip())
    for m in re.finditer(r"\{\{ndex\|[^|]*\|([^|}]+)", wt):
        names.add(m.group(1).strip())
    if len(names) < 800:
        raise SystemExit("species name list came back too small (%d)" % len(names))
    return names


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    valid_names = load_valid_names()
    print("species name dictionary: %d names" % len(valid_names))

    chars = []
    with open(os.path.join(HERE, "characters.txt")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            disp, pages, cat = parts[0], parts[1], parts[2]
            gen = int(parts[3]) if len(parts) > 3 else 0
            chars.append((disp, [p.strip() for p in pages.split("+")], cat, gen))

    out_path = os.path.join(HERE, "rosters_raw.json")
    out = {}
    if os.path.isfile(out_path):
        with open(out_path) as f:
            out = json.load(f)

    problems = []
    seed_text = open(os.path.join(HERE, "characters.txt")).read()
    for disp, pages, cat, gen in chars:
        if only and disp != only:
            continue
        # auto-union the anime page for every character, per user request:
        # a character usable in game AND anime gets one combined roster.
        base = disp.split(" (")[0]
        auto = base + " (anime)"
        if auto not in pages:
            pages = pages + [auto]
        species = set()
        scanned = 0
        found_any_page = False
        for page in pages:
            is_auto = (page == auto and auto not in seed_text)
            sections = get_sections(page)
            if sections is None and " (" in page and not is_auto:
                plain = page.split(" (")[0]
                sections = get_sections(plain)
                if sections is not None:
                    page = plain
            if sections is None:
                if not is_auto:
                    problems.append("PAGE MISSING: %s (%s)" % (page, disp))
                continue
            found_any_page = True
            picks = [s for s in sections
                     if any(h in s["line"].lower() for h in SECTION_HINTS)]
            scanned += len(picks)
            for s in picks:
                try:
                    wt = get_section_wikitext(page, s["index"])
                except Exception as e:
                    problems.append("SECTION FAIL: %s #%s: %s" % (page, s["index"], e))
                    continue
                species |= extract_species(wt, valid_names)
        if not found_any_page:
            continue
        if not species:
            problems.append("EMPTY: %s (%s) - %d sections scanned"
                            % (disp, disp, scanned))
        out[disp] = {"page": " + ".join(pages), "category": cat, "gen": gen,
                     "species": sorted(species)}
        print("%-14s %3d species (%d sections)" % (disp, len(species), scanned))
        with open(out_path, "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)

    if problems:
        print("\n--- problems ---")
        print("\n".join(problems))
    print("\nwrote %s (%d characters)" % (out_path, len(out)))


if __name__ == "__main__":
    main()
