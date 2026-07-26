Pokesho field sprites — REFERENCE ONLY, not directly injectable
==============================================================

These are 16x22 single FRONT-FACING FRAMES, not walk cycles, and 22 is not a
multiple of 8 — so they are not tile-aligned and `tools/png_to_gba.py` will
refuse them. That refusal is correct: there is no valid GBA 4bpp encoding of a
16x22 image.

To use one, a person has to draw the side and back frames and lay the result
out as a standard FireRed 9-frame 144x32 sheet (nine 16x32 cells). There is
direct precedent for exactly that: kalarie's PokéCommunity resource (staged in
`sprites/donors/kalarie/`) is these same Pokesho front frames animated into
full sheets, and its credits say so.

Why they are staged anyway: this is the ONLY existing GBA-style art for several
characters — Paul, Zoey, Nando, and a solo James among them — and it was
retrieved from a retired gallery via the Wayback Machine. Losing it again would
be worse than shipping it in an unfinished form.

See CREDITS.txt for the licence, and harvest_index.json for the per-file
character mapping.
