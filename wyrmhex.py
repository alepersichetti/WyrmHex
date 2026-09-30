#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WyrmHex v0.0.2 - hexcrawl map generator for OSR campaigns
=========================================================

This program draws a random map made of hexagons ("hexes") for old-school
role-playing campaigns. The map looks like an old computer screen made
only of letters and symbols, in the style of the games Dwarf Fortress
and Moonring:

  - hexes are drawn with the characters  _ / \\
  - terrains are made of symbols: forest ♣ ♠, mountains ▲ ^, hills ∩ n,
    lakes ≈, deserts ░ · ; plains are left empty and the sea is plain gray
  - rivers use double-line characters: ═ ║ ╔ ╗ ╚ ╝
  - cities, fortresses and dungeons are white symbols in black boxes

The whole page (frame, title, map, legend) is a grid of letters that all
have the same width. First the program builds the map, then it asks on
which paper you want to print it (A4, A3 or A2, suggesting the best one
for the number of hexes), and saves black-on-white pictures for that
paper at 600 dpi, plus the page as plain text (.txt). The sheet is turned
upright or sideways automatically, following the shape of the map.

Where the files go: the first time it runs, the program creates a folder
called "maps_generated" next to wyrmhex.py. Every map gets its own folder
in there, named with its seed (--output chooses another place for them):
  maps_generated/<seed>/<seed>_nonumber.png / .txt   the map without hex numbers
  maps_generated/<seed>/<seed>_number.png / .txt     the same map with a number in every hex
                                     (column + row, e.g. 0101 is the top-left hex)
  e.g. maps_generated/482913/482913_nonumber.png

What happens when it runs without options: it asks for the language
(Italian or English), shows a welcome screen with a wyvern, asks its
questions, then shows a wizard casting the spell and builds the map in
12 numbered steps. Every step starts with a bar that shows how much of
the whole job is done; while the two big pictures are drawn and saved, a
second bar fills up on the same line with the percentage.

The "seed" is the number that produced the map. Every PNG also keeps its
settings hidden inside the file, so the map can be rebuilt from its seed.

How to run it:
  python wyrmhex.py                      (welcome screen, then the program asks you questions)
  python wyrmhex.py --seme 42            (the grid size is chosen to fill the sheet)
  python wyrmhex.py --griglia 20x15      (choose the grid size yourself)
  python wyrmhex.py --riproduci 42       (rebuild map 42 from the settings in its PNG)
  python wyrmhex.py --formato A3         (print format: A4, A3 or A2)
  python wyrmhex.py --language en --seed 42   (English texts; every option also has an English name)
  python wyrmhex.py --solo-ascii         (only the most basic keyboard characters)

If the terrain percentages add up to less than 100%, the rest becomes
plains. If they add up to more than 100%, the program stops with an error.

The code is written in English. What the user sees (questions, messages,
the texts on the map) is in Italian or in English: the language is chosen
at the start, or with --lingua / --language.
"""

import argparse
import heapq
import json
import math
import os
import random
import secrets
import sys
import time
from collections import deque

# Pillow is the only extra library we need: it creates and saves pictures.
try:
    from PIL import Image, ImageDraw, ImageFont
    from PIL.PngImagePlugin import PngInfo
except ImportError:
    sys.exit("Manca la libreria Pillow. Installala con:  pip install -r requirements.txt\n"
             "Pillow is missing. Install it with:   pip install -r requirements.txt")

# An A2 page at 600 dpi has about 139 million pixels. Pillow warns about pictures
# that big because they could be a trick to fill the memory; ours are our own maps.
Image.MAX_IMAGE_PIXELS = None


# ==========================================================================
# SETTINGS
# ==========================================================================

VERSION = "0.0.2"

# The seven terrain types a hex can have.
PLAINS, SEA, LAKE, HILLS, MOUNTAINS, FOREST, DESERT = (
    "plains", "sea", "lake", "hills", "mountains", "forest", "desert")
WATER = (SEA, LAKE)   # the two "water" terrains

# Terrain names as the user reads them in the console: (Italian, English).
TERRAIN_NAMES = {PLAINS: ("pianura", "plains"), SEA: ("mare", "sea"), LAKE: ("lago", "lake"),
                 HILLS: ("colline", "hills"), MOUNTAINS: ("montagne", "mountains"),
                 FOREST: ("foresta", "forest"), DESERT: ("deserto", "desert")}

# For each terrain the user can set a percentage.
# Each line is: (Italian option name, English option name, terrain, label shown to the user)
TERRAIN_OPTIONS = [
    ("pianura", "plains", PLAINS, ("Pianura", "Plains")),
    ("mare", "sea", SEA, ("Mare", "Sea")),
    ("laghi", "lakes", LAKE, ("Laghi", "Lakes")),
    ("colline", "hills", HILLS, ("Colline", "Hills")),
    ("montagne", "mountains", MOUNTAINS, ("Montagne", "Mountains")),
    ("foreste", "forests", FOREST, ("Foreste", "Forests")),
    ("deserti", "deserts", DESERT, ("Deserti", "Deserts")),
]
# Percentages used when the user does not choose their own.
DEFAULT_PERCENTAGES = {PLAINS: 30, SEA: 15, LAKE: 3, HILLS: 15,
                       MOUNTAINS: 10, FOREST: 20, DESERT: 5}

# The three kinds of sites placed on the map, and their printed names.
CITY, FORTRESS, DUNGEON = "city", "fortress", "dungeon"
SITE_NAMES = {CITY: ("Città", "City"), FORTRESS: ("Fortezza", "Fortress"), DUNGEON: ("Dungeon", "Dungeon")}

# Sheet directions: the words the user types, and the words shown in messages.
ORIENTATION_FROM_USER = {"auto": "auto", "verticale": "portrait", "orizzontale": "landscape",
                         "portrait": "portrait", "landscape": "landscape"}
ORIENTATION_NAMES = {"portrait": ("verticale", "portrait"), "landscape": ("orizzontale", "landscape")}
# Hex sizes: the words the user types.
SIZE_FROM_USER = {"auto": "auto", "piccola": "small", "grande": "large", "small": "small", "large": "large"}

# Printing
DPI = 600                   # print quality: 600 dots per inch, sharp even on large paper
MARGIN_MM = 10.0            # white border around the page, in millimetres
MAX_CHAR_MM = 3.2           # on A4, letters never get wider than this (bigger sheets allow bigger letters)
READABLE_CHAR_MM = 1.35     # letter width used when the program picks the grid size itself
GOOD_CHAR_MM = 1.3          # letters at least this wide read well on paper
SMALL_CHAR_MM = 1.1         # below this width letters are hard to read
# Paper sizes in millimetres (width, height when the sheet is upright), from small to big.
PAPERS = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594)}

# Name of the note, hidden inside every PNG, that keeps the map's settings.
SETTINGS_KEY = "wyrmhex-settings"
# names used by earlier versions of the program, still read when rebuilding an old map
OLD_SETTINGS_KEYS = ("hexwyrm-settings", "hexcrawl-settings", "hexcrawl-impostazioni")

# Symbols. Each entry is (fancy symbol, plain keyboard symbol, weight).
# The plain one is used with --solo-ascii, or when the font lacks the fancy one.
# The weight says how often the symbol shows up compared with the others;
# spaces leave some air inside the hex.
# The fancy symbols come from the old IBM PC character set used by Dwarf Fortress.
TERRAIN_GLYPHS = {
    PLAINS:    [],                                     # plains stay empty
    HILLS:     [("∩", "n", 5), ("n", "m", 2), (" ", " ", 3), ("'", "'", 1)],
    MOUNTAINS: [("▲", "^", 5), ("^", "A", 3), (" ", " ", 1)],
    FOREST:    [("♣", "T", 5), ("♠", "Y", 3), (" ", " ", 1)],
    DESERT:    [("░", ".", 3), ("·", ":", 3), (":", ".", 1), (" ", " ", 2)],
    LAKE:      [("≈", "~", 6), (" ", " ", 1)],        # ≈ prints more clearly than ~
}
# symbol for each kind of site: (fancy, plain)
SITE_GLYPHS = {CITY: ("⌂", "C"), FORTRESS: ("Ω", "F"), DUNGEON: (">", ">")}

# Rivers are drawn with double-line characters. Which one to use depends on
# the directions the river goes out of that letter: l = left, r = right,
# u = up, d = down. For example a river coming from the left and turning
# down uses ╗.
RIVER_CHARS = {
    frozenset("lr"): ("═", "="), frozenset("ud"): ("║", "|"),
    frozenset("rd"): ("╔", "+"), frozenset("ld"): ("╗", "+"),
    frozenset("ru"): ("╚", "+"), frozenset("lu"): ("╝", "+"),
    frozenset("lrd"): ("╦", "+"), frozenset("lru"): ("╩", "+"),
    frozenset("udr"): ("╠", "+"), frozenset("udl"): ("╣", "+"),
    frozenset("lrud"): ("╬", "+"),
    frozenset("l"): ("═", "="), frozenset("r"): ("═", "="),
    frozenset("u"): ("║", "|"), frozenset("d"): ("║", "|"),
}
OPPOSITE = {"l": "r", "r": "l", "u": "d", "d": "u"}   # the opposite of each direction
SEA_GRAY = 205              # shade of the sea: 0 = black, 255 = white

# Fonts where every letter has the same width, as (normal, bold) pairs.
# The first one found on the computer is used. For .ttc files we also
# give the number of the style inside the file.
MONO_FONTS = [
    ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"),                        # Linux
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ("consola.ttf", "consolab.ttf"),                                          # Windows
    (("/System/Library/Fonts/Menlo.ttc", 0), ("/System/Library/Fonts/Menlo.ttc", 1)),   # macOS
    ("cour.ttf", "courbd.ttf"),                                               # Windows
    ("/System/Library/Fonts/Supplemental/Courier New.ttf",                    # macOS
     "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"),
    ("LiberationMono-Regular.ttf", "LiberationMono-Bold.ttf"),                # Linux
    ("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"),
]


def mm(value):
    """Turn millimetres into pixels at 600 dpi."""
    return value / 25.4 * DPI


# ==========================================================================
# LANGUAGE
#
# Everything the user reads exists in Italian and in English. The language
# is chosen at the start (or with --lingua / --language) and kept in LANG.
# Each entry below is  key: (Italian text, English text).  Words in braces,
# like {seed}, are filled in when the text is shown.
# ==========================================================================
LANGUAGES = ("it", "en")
LANG = "it"

TEXTS = {
    # console: general
    "done": ("Completato in {s:.1f} s.", "Done in {s:.1f} s."),
    "interrupted": ("\n\nInterrotto.", "\n\nStopped."),
    "invalid_value": ("    Valore non valido, riprova.", "    Invalid value, try again."),
    "value_range": ("    Il valore deve essere tra {lo} e {hi}.", "    The value must be between {lo} and {hi}."),
    "yes_letter": ("s", "y"),
    # welcome screen and conjuring screen
    "welcome_subtitle": ("generatore di mappe hexcrawl per campagne OSR", "hexcrawl map generator for OSR campaigns"),
    "press_enter": ("  Premi INVIO per iniziare... ", "  Press ENTER to start... "),
    "conjuring": ("L'incantesimo di evocazione ha inizio!", "The conjuring spell begins!"),
    # questions
    "enter_accepts": ("  Premi Invio per accettare il valore tra parentesi\n",
                      "  Press Enter to accept the value in brackets\n"),
    "what_to_do": ("  Cosa vuoi fare?", "  What do you want to do?"),
    "mode_new": ("    1 = creare una mappa nuova", "    1 = make a new map"),
    "mode_rebuild": ("    2 = riprodurre una mappa già fatta, a partire dal suo seme",
                     "    2 = rebuild a map you already made, from its seed"),
    "choice": ("Scelta", "Choice"),
    "ask_seed": ("  Seme della mappa da riprodurre (il numero all'inizio del nome del file): ",
                 "  Seed of the map to rebuild (the number at the start of the file name): "),
    "seed_digits_only": ("    Scrivi solo il numero, per esempio 482913.", "    Type just the number, for example 482913."),
    "found_settings": ("\n  Trovate le impostazioni della mappa {seed}:\n    {desc}",
                       "\n  Found the settings of map {seed}:\n    {desc}"),
    "use_settings": ("  Uso queste impostazioni? (S/n): ", "  Use these settings? (Y/n): "),
    "no_settings": ("\n  Non trovo {seed}_nonumber.png (né in {folder}, né nella cartella corrente), "
                    "quindi non conosco le impostazioni originali.",
                    "\n  Cannot find {seed}_nonumber.png (neither in {folder} nor in the current folder), "
                    "so the original settings are unknown."),
    "same_settings": ("  Inserisci le STESSE impostazioni della mappa originale: il seme da solo non basta.\n",
                      "  Enter the SAME settings as the original map: the seed alone is not enough.\n"),
    "ask_ascii": ("  Usare solo i caratteri base della tastiera, senza simboli come ♣ ▲ ≈? (s/N): ",
                  "  Use only basic keyboard characters, without symbols like ♣ ▲ ≈? (y/N): "),
    "q_columns": ("Esagoni in base (colonne)", "Hexes across (columns)"),
    "q_rows": ("Esagoni in altezza (righe)", "Hexes down (rows)"),
    "q_dungeons": ("Numero di dungeon", "Number of dungeons"),
    "q_cities": ("Numero di città", "Number of cities"),
    "q_fortresses": ("Numero di fortezze", "Number of fortresses"),
    "pct_intro": ("\n  Percentuali di terreno (la somma non deve superare 100; il resto diventa pianura)",
                  "\n  Terrain percentages (they must not add up to more than 100; the rest becomes plains)"),
    "pct_retry": ("\n  ERRORE: {error}\n  Reinserisci le percentuali.\n", "\n  ERROR: {error}\n  Enter the percentages again.\n"),
    "q_rivers": ("Numero di fiumi (-1 = automatico)", "Number of rivers (-1 = automatic)"),
    "q_title": ("  Titolo della mappa [{default}]: ", "  Map title [{default}]: "),
    "default_title": ("Terre Selvagge", "Wild Lands"),
    "default_scale": ("6 miglia", "6 miles"),
    "q_paper": ("  Formato di stampa per le due mappe (A4, A3, A2) [{default}]: ",
                "  Print format for both maps (A4, A3, A2) [{default}]: "),
    "paper_retry": ("    Scrivi A4, A3 oppure A2.", "    Type A4, A3 or A2."),
    # checks and errors
    "pct_out_of_range": ("La percentuale di {label} deve essere tra 0 e 100 (ricevuto {value:g}).",
                         "The {label} percentage must be between 0 and 100 (got {value:g})."),
    "pct_over_100": ("La somma delle percentuali di terreno è {total:g}%, supera il 100%.",
                     "The terrain percentages add up to {total:g}%, more than 100%."),
    "describe": ("griglia {cols}x{rows}, {cities} città, {forts} fortezze, {dungeons} dungeon, fiumi {rivers}"
                 "\n    terreni: {perc}\n    titolo: {title}",
                 "grid {cols}x{rows}, {cities} cities, {forts} fortresses, {dungeons} dungeons, rivers {rivers}"
                 "\n    terrains: {perc}\n    title: {title}"),
    "err_params": ("\nERRORE NEI PARAMETRI:", "\nERROR IN THE SETTINGS:"),
    "err_grid_range": ("La griglia deve essere tra 2x2 e 80x80 esagoni.", "The grid must be between 2x2 and 80x80 hexes."),
    "err_negative": ("Il numero di {name} non può essere negativo.", "The number of {name} cannot be negative."),
    "n_dungeons": ("dungeon", "dungeons"),
    "n_cities": ("città", "cities"),
    "n_fortresses": ("fortezze", "fortresses"),
    "err_land": ("\nERRORE: servono {sites} esagoni di terra per i siti, ma la mappa ne ha solo {land}.",
                 "\nERROR: the sites need {sites} land hexes, but the map has only {land}."),
    "err_no_saved": ("non trovo {seed}_nonumber.png con le impostazioni né in '{folder}' né nella cartella corrente",
                     "cannot find {seed}_nonumber.png with its settings in '{folder}' or in the current folder"),
    "err_grid_format": ("--griglia deve avere il formato BASExALTEZZA, es. 20x15",
                        "--grid must look like COLSxROWS, e.g. 20x15"),
    "err_no_font": ("Nessun font monospazio trovato. Indica un file .ttf con --font (es. DejaVuSansMono.ttf).",
                    "No monospaced font found. Give a .ttf file with --font (e.g. DejaVuSansMono.ttf)."),
    "err_size": ("{path}: {size} non è un foglio A4, A3 o A2 a 600 dpi",
                 "{path}: {size} is not an A4, A3 or A2 sheet at 600 dpi"),
    # step 1-2
    "step_validate": ("Lettura e validazione dei parametri", "Reading and checking the settings"),
    "info_grid": ("Griglia: {c} x {r} = {n} esagoni", "Grid: {c} x {r} = {n} hexes"),
    "info_terrains": ("Terreni: {list}", "Terrains: {list}"),
    "info_pct_sum": ("Somma percentuali: {t:g}% (≤ 100%: OK)", "Percentages add up to {t:g}% (≤ 100%: OK)"),
    "info_pct_rest": ("Il {r:g}% non assegnato viene aggiunto alla pianura", "The unassigned {r:g}% is added to plains"),
    "info_sites": ("Siti richiesti: {c} città, {f} fortezze, {d} dungeon",
                   "Sites wanted: {c} cities, {f} fortresses, {d} dungeons"),
    "info_auto_grid": ("Griglia automatica: {c} x {r} esagoni riempiono un A4 {o} (caratteri da {mm} mm)",
                       "Automatic grid: {c} x {r} hexes fill an A4 {o} sheet ({mm} mm letters)"),
    "info_seed": ("Seme: {s}  (per rifare questa mappa: scegli 2 all'avvio, oppure usa --riproduci {s})",
                  "Seed: {s}  (to rebuild this map: choose 2 at the start, or use --reproduce {s})"),
    "info_folder": ("Cartella della mappa: {folder}", "Map folder: {folder}"),
    "info_new_folder": ("Creata la cartella {folder}: qui dentro finiranno tutte le mappe",
                        "Created the {folder} folder: every map will be saved in there"),
    "step_font": ("Font", "Font"),
    "info_font": ("Font: {name}{fake}, cella {a:.2f} volte più alta che larga",
                  "Font: {name}{fake}, letter cell {a:.2f} times taller than wide"),
    "fake_bold": (" (grassetto simulato)", " (simulated bold)"),
    # steps 3-9: the land
    "step_heights": ("Campo di altitudine: rumore casuale livellato + abbassamento verso i bordi",
                     "Height map: smoothed random noise, lowered towards the edges"),
    "info_heights": ("{n} quote calcolate, normalizzate tra 0 e 1", "{n} heights worked out, scaled between 0 and 1"),
    "step_sea": ("Mare: allagamento dall'esagono di bordo più basso verso le quote minori",
                 "Sea: flooding from the lowest edge hex towards lower ground"),
    "info_no_sea": ("Nessun mare richiesto", "No sea wanted"),
    "info_sea": ("Mare partito da {h}, {n} esagoni allagati", "Sea started at {h}, {n} hexes flooded"),
    "step_lakes": ("Laghi: bacini interni scavati nelle conche", "Lakes: inland basins dug in the dips"),
    "info_lakes": ("{n} laghi per {h} esagoni", "{n} lakes, {h} hexes"),
    "warn_lakes": ("Spazio insufficiente: {n} esagoni di lago diventano pianura",
                   "Not enough room: {n} lake hexes become plains"),
    "step_relief": ("Rilievi: gli esagoni più alti diventano montagne, i successivi colline",
                    "Relief: the highest hexes become mountains, the next ones hills"),
    "info_relief": ("{m} montagne, {h} colline", "{m} mountains, {h} hills"),
    "step_wetness": ("Umidità: foreste nelle zone umide e vicino all'acqua, deserti in quelle aride, il resto pianura",
                     "Wetness: forests where it is wet and near water, deserts where it is dry, plains elsewhere"),
    "info_result": ("Risultato: {list}", "Result: {list}"),
    "step_rivers": ("Fiumi: dalle sorgenti in quota verso il basso fino a mare, lago o bordo",
                    "Rivers: from high springs downhill to the sea, a lake or the edge"),
    "river_water": ("sfocia in acqua", "flows into water"),
    "river_join": ("confluisce in un altro fiume", "joins another river"),
    "river_edge": ("esce dalla mappa", "leaves the map"),
    "info_river": ("Fiume {i}: sorgente {h}, {n} esagoni, {where}", "River {i}: spring {h}, {n} hexes, {where}"),
    "warn_rivers": ("Tracciati {d} fiumi su {n} richiesti (percorsi validi insufficienti)",
                    "Drew {d} of {n} rivers wanted (not enough valid paths)"),
    "step_sites": ("Insediamenti e dungeon: scelta pesata per terreno, con distanze minime",
                   "Settlements and dungeons: chosen by terrain, with minimum distances"),
    "info_site_kind": ("{name}: {n} su {n}, distanza minima tra loro {d} esagoni",
                       "{name}: {n} of {n}, at least {d} hexes apart"),
    "relaxed": (" (rilassata per mancanza di spazio)", " (reduced for lack of room)"),
    "sites_header": ("\nELENCO DEI SITI (codice esagono)", "\nLIST OF SITES (hex code)"),
    "on_river": (", sul fiume", ", on a river"),
    # step 10: print format
    "step_paper": ("Formato di stampa: la direzione del foglio segue la forma della mappa",
                   "Print format: the sheet direction follows the shape of the map"),
    "v_too_small": ("troppo piccoli", "too small"),
    "v_small": ("piccoli", "small"),
    "v_good": ("ben leggibili", "easy to read"),
    "suggested": ("   <- consigliato", "   <- suggested"),
    "hexes_large": ("esagoni grandi", "large hexes"),
    "hexes_small": ("esagoni piccoli", "small hexes"),
    "info_paper_option": ("{paper} {o:<11} {hexes:<15} caratteri da {mm:.2f} mm ({v}){note}",
                          "{paper} {o:<11} {hexes:<15} letters {mm:.2f} mm wide ({v}){note}"),
    "subtitle": ("1 esagono = {scale}  {dot}  {c}{x}{r} esagoni  {dot}  seme {seed}",
                 "1 hex = {scale}  {dot}  {c}{x}{r} hexes  {dot}  seed {seed}"),
    "warn_shrink": ("Il contenuto sfora il foglio: l'immagine viene ridotta al {p:.0%} per stare nell'{paper}",
                    "The content does not fit: the picture is shrunk to {p:.0%} to fit the {paper}"),
    "info_sheet": ("Foglio {paper} {o} ({w} x {h} px a {dpi} dpi): pagina di {nc} x {nr} caratteri, "
                   "carattere largo {mm:.2f} mm",
                   "{paper} sheet, {o} ({w} x {h} px at {dpi} dpi): page of {nc} x {nr} letters, "
                   "letters {mm:.2f} mm wide"),
    "hexes_desc_large": ("Esagoni grandi", "Large hexes"),
    "hexes_desc_small": ("Esagoni piccoli", "Small hexes"),
    "info_hexes": ("{prefix} (k={k}): {w} caratteri x {h} righe; mappa di {mw} x {mh} caratteri",
                   "{prefix} (k={k}): {w} letters x {h} lines; map of {mw} x {mh} letters"),
    "warn_tiny": ("Caratteri molto piccoli: la stampa sarà poco leggibile, scegli un formato più grande",
                  "Very small letters: the print will be hard to read, choose a bigger format"),
    # steps 11-12: drawing and saving
    "step_plain": ("Disegno della mappa senza numeri ({paper}, {dpi} dpi, PNG + TXT)",
                   "Drawing the map without numbers ({paper}, {dpi} dpi, PNG + TXT)"),
    "step_numbered": ("Disegno della mappa numerata ({paper}, {dpi} dpi, stessa mappa + codici CCRR)",
                      "Drawing the numbered map ({paper}, {dpi} dpi, same map + CCRR codes)"),
    "saved": ("Salvate: {a}, {b}", "Saved: {a}, {b}"),
    "warn_missing_glyphs": ("Il font non ha questi glifi, sostituiti con ASCII: {g}",
                            "The font lacks these symbols, replaced with ASCII: {g}"),
    "pb_drawing": ("disegno", "drawing"),
    "pb_saving": ("salvataggio", "saving"),
    "pb_done": ("fatto", "done"),
    # texts drawn on the map (legend)
    "leg_mountains": ("Montagne", "Mountains"),
    "leg_hills": ("Colline", "Hills"),
    "leg_forest": ("Foresta", "Forest"),
    "leg_plains": ("Pianura = esagono vuoto", "Plains = empty hex"),
    "leg_desert": ("Deserto", "Desert"),
    "leg_sea": ("Mare", "Sea"),
    "leg_lake": ("Lago", "Lake"),
    "leg_river": ("Fiume", "River"),
    # command-line help
    "cli_description": ("WyrmHex: genera una mappa hexcrawl OSR in stile ASCII (Dwarf Fortress / Moonring), "
                        "PNG a 600 dpi in formato A4, A3 o A2 + TXT.",
                        "WyrmHex: makes an ASCII-style OSR hexcrawl map (Dwarf Fortress / Moonring), "
                        "600 dpi PNG on A4, A3 or A2 + TXT."),
    "mv_grid": ("BASExALTEZZA", "COLSxROWS"),
    "mv_seed": ("SEME", "SEED"),
    "mv_text": ("TESTO", "TEXT"),
    "mv_folder": ("CARTELLA", "FOLDER"),
    "h_grid": ("esagoni in base X altezza, es. 33x15; auto (default) riempie un A4",
               "hexes across X down, e.g. 33x15; auto (default) fills an A4"),
    "h_dungeons": ("numero di dungeon", "number of dungeons"),
    "h_cities": ("numero di città", "number of cities"),
    "h_fortresses": ("numero di fortezze", "number of fortresses"),
    "h_terrain": ("%% di {label} (default {default})", "%% of {label} (default {default})"),
    "h_rivers": ("numero di fiumi, -1 = automatico", "number of rivers, -1 = automatic"),
    "h_seed": ("seme casuale per rigenerare la stessa mappa", "random seed, to make the same map again"),
    "h_reproduce": ("rifà la mappa con questo seme, leggendo le impostazioni dal suo PNG "
                    "(in maps_generated/<seme>, o nella cartella --output)",
                    "rebuilds the map with this seed, reading the settings from its PNG "
                    "(in maps_generated/<seed>, or in the --output folder)"),
    "h_title": ("titolo della mappa", "map title"),
    "h_scale": ("testo della scala, es. '6 miglia'", "scale text, e.g. '6 miles'"),
    "h_paper": ("formato di stampa delle due mappe; se manca si usa quello consigliato",
                "print format of the two maps; if missing the suggested one is used"),
    "h_orientation": ("di solito non serve: la direzione del foglio segue la forma della mappa",
                      "usually not needed: the sheet direction follows the shape of the map"),
    "h_output": ("cartella in cui salvare le mappe (default: maps_generated accanto a wyrmhex.py); ogni mappa "
                 "va in una sua cartella <seme>, con i file <seme>_nonumber e <seme>_number",
                 "folder where the maps are saved (default: maps_generated next to wyrmhex.py); every map goes "
                 "in its own <seed> folder, with the files <seed>_nonumber and <seed>_number"),
    "h_ascii": ("usa solo caratteri ASCII a 7 bit", "use only 7-bit ASCII characters"),
    "h_size": ("esagoni piccoli (k=2) o grandi (k=3); auto sceglie in base al formato",
               "small (k=2) or large (k=3) hexes; auto chooses from the print format"),
    "h_version": ("mostra la versione del programma ed esce", "show the program version and exit"),
    "h_font": ("file .ttf monospazio da usare", "monospaced .ttf font file to use"),
    "h_language": ("lingua dei testi: it (italiano) o en (inglese)", "language of the texts: it (Italian) or en (English)"),
}


def tr(key, **values):
    """The text 'key' in the chosen language, with the {words} in braces filled in."""
    text = TEXTS[key][LANGUAGES.index(LANG)]
    return text.format(**values) if values else text


def pick(pair):
    """Pick the Italian or the English half of an (Italian, English) pair."""
    return pair[LANGUAGES.index(LANG)]


def normalize_language(value):
    """Turn what the user typed (1, 2, it, en, italiano, english...) into "it" or "en", or None."""
    value = (value or "").strip().lower()
    if value in ("1", "it", "ita", "italiano", "italian"):
        return "it"
    if value in ("2", "en", "eng", "english", "inglese"):
        return "en"
    return None


def ask_language():
    """The very first question, shown in both languages."""
    global LANG
    print("\n  Lingua / Language:")
    print("    1 = Italiano")
    print("    2 = English")
    while True:
        choice = normalize_language(input("  Scelta / Choice [1]: ") or "1")
        if choice:
            LANG = choice
            return
        print("    1 / 2")


def language_from_options(argv):
    """Find --lingua / --language among the typed options before anything else,
    so that even the help text is in the right language."""
    global LANG
    for i, arg in enumerate(argv):
        for name in ("--lingua", "--language"):
            if arg == name and i + 1 < len(argv):
                LANG = normalize_language(argv[i + 1]) or LANG
            elif arg.startswith(name + "="):
                LANG = normalize_language(arg.split("=", 1)[1]) or LANG


# ==========================================================================
# MESSAGES IN THE CONSOLE
# ==========================================================================
def bar(fraction, cells):
    """A progress bar made of blocks, e.g. [██████░░░░] for 60%."""
    full = round(max(0.0, min(1.0, fraction)) * cells)
    return "[" + "█" * full + "░" * (cells - full) + "]"


class LiveBar:
    """A progress bar that fills up on the same line while something long runs
    (drawing and saving a big map). When the output is not a console window
    (for example when it goes to a file) it stays silent."""

    def __init__(self):
        self.live = sys.stdout.isatty()
        self.shown = None

    def update(self, fraction, label):
        percent = int(fraction * 100)
        if self.live and (percent, label) != self.shown:
            self.shown = (percent, label)
            print(f"\r        {bar(fraction, 30)} {percent:>3}%  {label:<14}", end="", flush=True)

    def finish(self):
        if self.live:
            print(f"\r        {bar(1, 30)} 100%  {tr('pb_done'):<14}")


class Log:
    """Prints numbered steps so the user can follow the work. Each step starts
    with a bar that shows how much of the whole job is done."""

    def __init__(self, total_steps):
        self.total_steps, self.step_number, self.start_time = total_steps, 0, time.perf_counter()

    def step(self, message):
        # a new numbered step, with the overall progress bar
        self.step_number += 1
        progress = bar(self.step_number / self.total_steps, self.total_steps)
        print(f"\n{progress} {self.step_number:>2}/{self.total_steps}  {message}")

    def info(self, message):
        # a detail inside the current step
        print(f"        · {message}")

    def warn(self, message):
        # a warning
        print(f"        ! {message}")

    def done(self):
        # the closing line, with how long everything took
        print("\n" + tr("done", s=time.perf_counter() - self.start_time))


# ==========================================================================
# THE HEX GRID
#
# Hexes have a flat top. Columns are numbered left to right, rows top to
# bottom, and every odd column is pushed down by half a hex. This is the
# usual layout of printed hexcrawl maps, where hexes are numbered CCRR.
# ==========================================================================
class HexGrid:
    # How to reach the six neighbours of a hex, as (column change, row change).
    # The list is different for even and odd columns because odd ones sit lower.
    DIRS_EVEN = ((1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1))
    DIRS_ODD = ((1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1))

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        # every hex of the map, as (column, row), counting from 0
        self.hexes = [(c, r) for c in range(cols) for r in range(rows)]
        # remember the neighbours of each hex that are inside the map
        self._neighbours = {h: [n for n in self.all_neighbours(h) if self.inside(n)]
                            for h in self.hexes}

    def inside(self, hex_):
        """True if the hex is inside the map."""
        return 0 <= hex_[0] < self.cols and 0 <= hex_[1] < self.rows

    def all_neighbours(self, hex_):
        """All six neighbours, even the ones that fall outside the map."""
        c, r = hex_
        dirs = self.DIRS_ODD if c & 1 else self.DIRS_EVEN
        return [(c + dc, r + dr) for dc, dr in dirs]

    def neighbours(self, hex_):
        """The neighbours that are inside the map."""
        return self._neighbours[hex_]

    def on_edge(self, hex_):
        """True if the hex touches the edge of the map (it has fewer than 6 neighbours)."""
        return len(self._neighbours[hex_]) < 6

    @staticmethod
    def distance(a, b):
        """How many steps you need to walk from hex a to hex b."""
        # We switch to a different way of writing hex positions ("cube"
        # coordinates) where distance is easy to measure.
        ax, az = a[0], a[1] - (a[0] - (a[0] & 1)) // 2
        bx, bz = b[0], b[1] - (b[0] - (b[0] & 1)) // 2
        return max(abs(ax - bx), abs(az - bz), abs((-ax - az) - (-bx - bz)))

    def distances_from(self, starts):
        """For every hex, how many steps it is from the nearest hex in 'starts'."""
        # We spread outwards from the starting hexes one ring at a time,
        # like ripples on a pond.
        dist = {h: None for h in self.hexes}
        queue = deque()
        for s in starts:
            dist[s] = 0
            queue.append(s)
        while queue:
            current = queue.popleft()
            for n in self._neighbours[current]:
                if dist[n] is None:
                    dist[n] = dist[current] + 1
                    queue.append(n)
        return dist


def hex_code(hex_, digits):
    """The hex number, column then row, counting from 1: e.g. column 3 row 7 -> '0307'."""
    return f"{hex_[0] + 1:0{digits}d}{hex_[1] + 1:0{digits}d}"


# ==========================================================================
# READING AND CHECKING WHAT THE USER ASKED FOR
# ==========================================================================
def check_percentages(perc):
    """Check the terrain percentages. Returns an error message, or None if all is fine."""
    # each percentage must be between 0 and 100
    for _, _, terrain, label in TERRAIN_OPTIONS:
        if perc[terrain] < 0 or perc[terrain] > 100:
            return tr("pct_out_of_range", label=pick(label).lower(), value=perc[terrain])
    # and all together they must not go over 100
    total = sum(perc.values())
    if total > 100 + 1e-9:
        detail = " + ".join(f"{pick(label).lower()} {perc[terrain]:g}" for _, _, terrain, label in TERRAIN_OPTIONS)
        return tr("pct_over_100", total=total) + f"\n         ({detail})"
    return None


def new_seed():
    """Pick a random 6-digit seed (100000-999999). The same seed always makes the same map."""
    return 100_000 + secrets.randbelow(900_000)


# All maps are saved in this folder, next to wyrmhex.py: one sub-folder per map, named with its seed.
MAPS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps_generated")


def make_maps_folder():
    """Create the maps_generated folder if it does not exist yet.
    Returns True when it has just been created (the very first run)."""
    if os.path.isdir(MAPS_FOLDER):
        return False
    os.makedirs(MAPS_FOLDER, exist_ok=True)
    return True


def map_folder(base, seed):
    """The folder of one map: <base>/<seed>."""
    return os.path.join(base, str(seed))


def short_path(path):
    """A path written the short way for the screen: relative to the current folder when possible."""
    try:
        short = os.path.relpath(path)
    except ValueError:                   # Windows: another drive letter
        return path
    return path if short.startswith("..") else short


def output_names(base, seed, extension="png"):
    """File names for the two maps: <seed>_nonumber and <seed>_number,
    inside the map's own folder <base>/<seed> (created if it does not exist yet)."""
    folder = map_folder(base, seed)
    os.makedirs(folder, exist_ok=True)
    return (os.path.join(folder, f"{seed}_nonumber.{extension}"),
            os.path.join(folder, f"{seed}_number.{extension}"))


def upgrade_settings(data):
    """Settings saved by an earlier version of the program used Italian names:
    translate them to the names used now. New settings are returned as they are."""
    if "colonne" not in data:
        return data
    names = {"colonne": "columns", "righe": "rows", "dungeon": "dungeons", "citta": "cities",
             "fortezze": "fortresses", "perc": "percentages", "fiumi": "rivers", "titolo": "title",
             "scala": "scale", "orientamento": "orientation", "solo_ascii": "ascii_only",
             "invertito": "inverted", "dimensione": "size", "font": "font"}
    new = {names[k]: v for k, v in data.items() if k in names}
    terrain_of_option = {option: terrain for option, _, terrain, _ in TERRAIN_OPTIONS}
    new["percentages"] = {terrain_of_option[k]: v for k, v in new["percentages"].items()}
    if "orientation" in new:
        new["orientation"] = ORIENTATION_FROM_USER.get(new["orientation"], new["orientation"])
    if "size" in new:
        new["size"] = SIZE_FROM_USER.get(new["size"], new["size"])
    return new


def load_settings(folder, seed):
    """Read back the settings saved inside <seed>_nonumber.png (or _number.png).
    Returns them as a dictionary, or None if the file is not there."""
    for name in (f"{seed}_nonumber.png", f"{seed}_number.png"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        try:
            # the settings note sits before the picture data, so 'info' has it
            # without having to decode the whole (possibly huge) picture
            with Image.open(path) as img:
                text = next((img.info[key] for key in (SETTINGS_KEY, *OLD_SETTINGS_KEYS)
                             if key in img.info), None)
        except (OSError, AttributeError):
            continue
        if text:
            return upgrade_settings(json.loads(text))
    return None


def find_settings(base, seed):
    """Look for the saved settings of map 'seed': first in its own folder <base>/<seed>,
    then in maps_generated, then in the current folder (where older versions saved the maps)."""
    folders = []
    for folder in (map_folder(base, seed), base, map_folder(MAPS_FOLDER, seed), MAPS_FOLDER,
                   map_folder(".", seed), "."):
        if os.path.abspath(folder) not in (os.path.abspath(f) for f in folders):
            folders.append(folder)
    for folder in folders:
        saved = load_settings(folder, seed)
        if saved:
            return saved
    return None


def complete_settings(p):
    """Fill in any setting missing from saved settings (e.g. from an older version of the program)."""
    for key, value in (("ascii_only", False), ("size", "auto"), ("font", None), ("paper", None)):
        p.setdefault(key, value)
    # maps are always black on white now: an old "white on black" choice is dropped
    p.pop("inverted", None)
    # the sheet direction follows the shape of the map
    p["orientation"] = "auto"
    # a default title or scale written in the other language follows the language chosen now
    for key, default in (("title", "default_title"), ("scale", "default_scale")):
        if p.get(key) in TEXTS[default]:
            p[key] = tr(default)
    return p


def describe_settings(p):
    """A short summary of the settings, to show the user before reproducing a map."""
    perc = ", ".join(f"{pick(label).lower()} {p['percentages'][terrain]:g}%" for _, _, terrain, label in TERRAIN_OPTIONS)
    return tr("describe", cols=p["columns"], rows=p["rows"], cities=p["cities"], forts=p["fortresses"],
              dungeons=p["dungeons"], rivers=p["rivers"], perc=perc, title=p["title"])


def split_hexes(total, perc):
    """Turn percentages into a number of hexes per terrain, so that the total is exact."""
    # First give each terrain the whole part of its share, then hand out the
    # few hexes left over to the terrains that were closest to the next one.
    exact = {k: total * p / 100.0 for k, p in perc.items()}
    counts = {k: int(math.floor(v)) for k, v in exact.items()}
    left_over = total - sum(counts.values())
    for k in sorted(perc, key=lambda k: exact[k] - counts[k], reverse=True)[:left_over]:
        counts[k] += 1
    return counts


def ask(question, default, kind=int, lowest=None, highest=None):
    """Ask the user one question. Pressing Enter keeps the value shown in brackets."""
    while True:
        answer = input(f"  {question} [{default}]: ").strip()
        if not answer:
            return default
        try:
            value = kind(answer.replace(",", "."))   # accept "2,5" as well as "2.5"
        except ValueError:
            print(tr("invalid_value"))
            continue
        if (lowest is not None and value < lowest) or (highest is not None and value > highest):
            print(tr("value_range", lo=lowest, hi=highest))
            continue
        return value


# ==========================================================================
# WELCOME SCREEN, WIZARD AND QUESTIONS
# (the welcome screen and the questions appear only when the program is
# started without options; the wizard appears every time)
# ==========================================================================
# The program's name in big letters.
TITLE_ART = r"""
 _       __                     __  __
| |     / /_  ___________ ___  / / / /__  _  __
| | /| / / / / / ___/ __ `__ \/ /_/ / _ \| |/_/
| |/ |/ / /_/ / /  / / / / / / __  /  __/>  <
|__/|__/\__, /_/  /_/ /_/ /_/_/ /_/\___/_/|_|
       /____/
"""

# A wyvern in front of a castle, with mountains behind.
WYVERN_CASTLE = r"""
                                                                          /\
                                                                         /¨¨\
               ______________                /\    *                    /¨¨¨¨\
           _.-'            ,.`:===,         /__\   |                   / ¨ ¨ ¨\
       _.-'         __.---'.:'              (..)---+                  /        \        /\
     .'         .--'     .:'               /|##|   |                 /.  .      \      /¨¨\
   .'         .'        ./                _.|__|.__|_               /   .        \    /¨ ¨ \
,.'-,____   .'         ./    ,),,)        |_|_|_|_|_|              /      .       \  /      \
         `.'___.--,   ./   \'     `,)      |       |              /   |>     |>    \/.       \
         '         `;./   ,'  .--,  `,  ,  |  []   |             /   [_]_n_n[_]     \
                    ;/    :  /    } ,C}'   |       |            / .  | |'  '| |      \
                    \\    \  \    `,,V     |    [] |           /     |_|_/\_|_|       \
    ,      .---,    .\\-, `,  \    ;;l     |       |          /                  .     \
    \`,   /  _  \  /  _  \ `,  \   `;/     |  []   |         /    | σ                   \
     \ `.'  / \  `'  / \  `'   /           |   _   |        /     ´√))θ                 .\  .
      `,__.'   `,__.'   `,___.'           _|__/ \__|_      /       / \      .             \
 ,     .     ,,     .      ,      .    ,     .     ,,     .      ,      .     ,,     .      ,
"""


def terminal_width():
    """How many letters fit across the console window, or None if we cannot tell."""
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError):
        return None


def show_welcome():
    """Show the title and the drawing, then wait for the user to press ENTER."""
    art = WYVERN_CASTLE.strip("\n").split("\n")
    title = TITLE_ART.strip("\n").split("\n")
    subtitle = f"v{VERSION}  ·  " + tr("welcome_subtitle")
    width = max(len(line) for line in art)
    # In a narrow window long lines would wrap and scramble the drawing:
    # use only the width of the window and cut the drawing at its edge.
    columns = terminal_width()
    if columns and columns <= width:
        width = columns - 1
    title_width = max(len(line) for line in title)
    screen = [
        "═" * width,
        "",
        # centre the title as one block, so its letters stay lined up
        *[" " * max(0, (width - title_width) // 2) + line for line in title],
        "",
        " " * max(0, (width - len(subtitle)) // 2) + subtitle,
        "",
        "═" * width,
        *[line[:width] for line in art],
        "═" * width,
    ]
    print("\n" + "\n".join(line.rstrip() for line in screen) + "\n")
    input(tr("press_enter"))
    print()


# A wizard casting a spell, shown once the settings are decided.
# ASCII art by Row, from the classic ASCII art archives: the artist's signature
# "-Row" at the bottom right is replaced on screen by the spell text (@SPELL@).
WIZARD = r"""
                  .

                   .
         /^\     .
    /\   "V"
   /__\   I      O  o
  //..\\  I     .
  \].`[/  I
  /l\/j\  (]    .  O
 /. ~~ ,\/I          .
 \\L__j^\/I       o
  \/--v}  I     o   .
  |    |  I   _________
  |    |  I c(`       ')o
  |    l  I   \.     ,/
_/j  L l\_!  _//^---^\\_    @SPELL@
"""


def show_conjuring():
    """Show the wizard: the map is about to be conjured."""
    print(WIZARD.replace("@SPELL@", tr("conjuring")).rstrip())


def ask_mode(folder=MAPS_FOLDER):
    """The first question: make a brand new map, or rebuild one from its seed?
    Returns None for a new map, otherwise (seed, saved settings or None)."""
    print(tr("what_to_do"))
    print(tr("mode_new"))
    print(tr("mode_rebuild"))
    choice = ask(tr("choice"), 1, int, 1, 2)
    if choice == 1:
        return None
    # the seed has no default value: keep asking until we get a number
    seed = None
    while seed is None:
        answer = input(tr("ask_seed")).strip()
        if answer.isdigit():
            seed = int(answer)
        else:
            print(tr("seed_digits_only"))
    saved = find_settings(folder, seed)
    if saved:
        print(tr("found_settings", seed=seed, desc=describe_settings(saved)))
        if input(tr("use_settings")).strip().lower().startswith("n"):
            saved = None
    else:
        print(tr("no_settings", seed=seed, folder=short_path(folder)))
    if not saved:
        print(tr("same_settings"))
    return seed, saved


def ask_look(p):
    """Ask how the map should look. This never changes the land itself,
    so it is asked again even when an old map is rebuilt from its seed."""
    p["ascii_only"] = input(tr("ask_ascii")).strip().lower().startswith(tr("yes_letter"))


def ask_settings():
    """Ask the user every setting, one question at a time (used when no options are given)."""
    ask_language()
    show_welcome()
    print(tr("enter_accepts"))
    # first question: new map, or rebuild an old one from its seed?
    mode = ask_mode()
    if mode and mode[1]:
        # the old settings were found inside the picture: only ask how it should look
        # (the print format is asked later, after the map is built)
        seed, saved = mode
        saved.update(seed=seed, output=MAPS_FOLDER)
        print()
        ask_look(saved)
        return complete_settings(saved)
    print()
    p = {}
    # "auto" = the program works out how many hexes fill the sheet
    p["columns"] = ask(tr("q_columns"), "auto", int, 2, 80)
    p["rows"] = ask(tr("q_rows"), "auto", int, 2, 80)
    p["dungeons"] = ask(tr("q_dungeons"), 4, int, 0, 500)
    p["cities"] = ask(tr("q_cities"), 3, int, 0, 500)
    p["fortresses"] = ask(tr("q_fortresses"), 2, int, 0, 500)
    print(tr("pct_intro"))
    # keep asking for the percentages until they make sense
    while True:
        perc = {terrain: ask(f"% {pick(label).lower()}", DEFAULT_PERCENTAGES[terrain], float, 0, 100)
                for _, _, terrain, label in TERRAIN_OPTIONS}
        error = check_percentages(perc)
        if not error:
            break
        print(tr("pct_retry", error=error))
    p["percentages"] = perc
    p["rivers"] = ask(tr("q_rivers"), -1, int, -1, 100)
    if mode:
        p["seed"] = mode[0]          # we already know the seed
    else:
        p["seed"] = None             # a new map gets a new random seed
    p["title"] = input(tr("q_title", default=tr("default_title"))).strip() or tr("default_title")
    p["scale"] = tr("default_scale")
    p["output"] = MAPS_FOLDER
    p["orientation"] = "auto"
    ask_look(p)
    p["size"], p["font"], p["paper"] = "auto", None, None   # paper: asked after the map is built
    return p


def settings_from_options(argv):
    """Read the settings from the options typed after the program name (e.g. --seme 42).
    Every option has an Italian and an English name (--seme / --seed): both work,
    and the help lists first the one of the chosen language."""
    language_from_options(argv)

    def names(italian, english):
        # the two names of an option, the chosen language first
        if italian == english:
            return (f"--{italian}",)
        return (f"--{italian}", f"--{english}") if LANG == "it" else (f"--{english}", f"--{italian}")

    def shown(options):
        # the choices of an option, as listed in the help for the chosen language
        return "{" + ",".join(options[LANG]) + "}"

    ap = argparse.ArgumentParser(prog="wyrmhex.py", epilog=f"WyrmHex v{VERSION}", description=tr("cli_description"))
    ap.add_argument(*names("lingua", "language"), dest="language", default=LANG, metavar="{it,en}",
                    help=tr("h_language"))
    ap.add_argument(*names("griglia", "grid"), dest="grid", default="auto", metavar=tr("mv_grid"), help=tr("h_grid"))
    ap.add_argument(*names("dungeon", "dungeons"), dest="dungeons", type=int, default=4, metavar="N",
                    help=tr("h_dungeons"))
    ap.add_argument(*names("citta", "cities"), dest="cities", type=int, default=3, metavar="N", help=tr("h_cities"))
    ap.add_argument(*names("fortezze", "fortresses"), dest="fortresses", type=int, default=2, metavar="N",
                    help=tr("h_fortresses"))
    # one option per terrain: --pianura / --plains, --mare / --sea, ...
    for italian, english, terrain, label in TERRAIN_OPTIONS:
        ap.add_argument(*names(italian, english), dest=terrain, type=float, default=DEFAULT_PERCENTAGES[terrain],
                        metavar="%", help=tr("h_terrain", label=pick(label).lower(),
                                             default=DEFAULT_PERCENTAGES[terrain]))
    ap.add_argument(*names("fiumi", "rivers"), dest="rivers", type=int, default=-1, metavar="N", help=tr("h_rivers"))
    ap.add_argument(*names("seme", "seed"), dest="seed", type=int, default=None, metavar=tr("mv_seed"),
                    help=tr("h_seed"))
    ap.add_argument(*names("riproduci", "reproduce"), dest="reproduce", type=int, default=None,
                    metavar=tr("mv_seed"), help=tr("h_reproduce"))
    ap.add_argument(*names("titolo", "title"), dest="title", default=tr("default_title"), metavar=tr("mv_text"),
                    help=tr("h_title"))
    ap.add_argument(*names("scala", "scale"), dest="scale", default=tr("default_scale"), metavar=tr("mv_text"),
                    help=tr("h_scale"))
    ap.add_argument(*names("formato", "format"), dest="paper", type=str.upper, choices=list(PAPERS), default=None,
                    help=tr("h_paper"))
    orientations = {"it": ["auto", "verticale", "orizzontale"], "en": ["auto", "portrait", "landscape"]}
    ap.add_argument(*names("orientamento", "orientation"), dest="orientation", choices=list(ORIENTATION_FROM_USER),
                    default="auto", metavar=shown(orientations), help=tr("h_orientation"))
    ap.add_argument("--output", default=MAPS_FOLDER, metavar=tr("mv_folder"), help=tr("h_output"))
    ap.add_argument(*names("solo-ascii", "ascii-only"), dest="ascii_only", action="store_true", help=tr("h_ascii"))
    sizes = {"it": ["auto", "piccola", "grande"], "en": ["auto", "small", "large"]}
    ap.add_argument(*names("dimensione", "size"), dest="size", choices=list(SIZE_FROM_USER), default="auto",
                    metavar=shown(sizes), help=tr("h_size"))
    ap.add_argument("--version", action="version", version=f"WyrmHex v{VERSION}", help=tr("h_version"))
    ap.add_argument("--font", default=None, metavar="FILE", help=tr("h_font"))
    a = ap.parse_args(argv)
    orientation = ORIENTATION_FROM_USER[a.orientation]
    size = SIZE_FROM_USER[a.size]

    if a.reproduce is not None:
        # rebuild an old map: read its settings from its picture,
        # looking in its folder inside --output first, then in maps_generated and the current folder
        saved = find_settings(a.output, a.reproduce)
        if not saved:
            ap.error(tr("err_no_saved", seed=a.reproduce, folder=short_path(a.output)))
        saved.update(seed=a.reproduce, output=a.output)
        # the look comes from this command, not from the old picture
        saved.update(ascii_only=a.ascii_only)
        for key, value in (("size", size), ("font", a.font)):
            saved.setdefault(key, value)
        saved = complete_settings(saved)
        if a.paper:
            saved["paper"] = a.paper            # a format typed now wins over the saved one
        saved["orientation"] = orientation
        return saved

    # "20x15" becomes 20 columns and 15 rows; "auto" is worked out later
    if a.grid.strip().lower() == "auto":
        columns = rows = "auto"
    else:
        try:
            columns, rows = (int(v) for v in a.grid.lower().replace("×", "x").split("x"))
        except ValueError:
            ap.error(tr("err_grid_format"))
    return {
        "columns": columns, "rows": rows,
        "dungeons": a.dungeons, "cities": a.cities, "fortresses": a.fortresses,
        "percentages": {terrain: getattr(a, terrain) for _, _, terrain, _ in TERRAIN_OPTIONS},
        "rivers": a.rivers, "seed": a.seed, "title": a.title, "scale": a.scale,
        "orientation": orientation, "output": a.output, "paper": a.paper,
        "ascii_only": a.ascii_only, "size": size, "font": a.font,
    }


def validate(p, log):
    """Check all settings. Stop with a clear message if something is wrong.
    Returns how many hexes each terrain will get."""
    errors = []
    if not (2 <= p["columns"] <= 80 and 2 <= p["rows"] <= 80):
        errors.append(tr("err_grid_range"))
    for key in ("dungeons", "cities", "fortresses"):
        if p[key] < 0:
            errors.append(tr("err_negative", name=tr("n_" + key)))
    perc_error = check_percentages(p["percentages"])
    if perc_error:
        errors.append(perc_error)
    if errors:
        print(tr("err_params"))
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # show the user what we are going to do
    total_perc = sum(p["percentages"].values())
    log.info(tr("info_grid", c=p["columns"], r=p["rows"], n=p["columns"] * p["rows"]))
    log.info(tr("info_terrains", list=", ".join(f"{pick(label).lower()} {p['percentages'][terrain]:g}%"
                                                for _, _, terrain, label in TERRAIN_OPTIONS)))
    log.info(tr("info_pct_sum", t=total_perc))
    if total_perc < 100:
        log.info(tr("info_pct_rest", r=100 - total_perc))

    # the percentage nobody asked for becomes plains
    total = p["columns"] * p["rows"]
    perc = dict(p["percentages"])
    perc[PLAINS] += 100 - total_perc
    counts = split_hexes(total, perc)

    # there must be enough dry land for all the sites
    land = total - counts[SEA] - counts[LAKE]
    sites = p["cities"] + p["fortresses"] + p["dungeons"]
    log.info(tr("info_sites", c=p["cities"], f=p["fortresses"], d=p["dungeons"]))
    if sites > land:
        print(tr("err_land", sites=sites, land=land))
        sys.exit(1)
    return counts


# ==========================================================================
# BUILDING THE LAND
#
# The idea: first we invent a "height" for every hex. Low hexes near the
# edge become sea, dips become lakes, the highest hexes become mountains
# and hills. Then a second random map of "wetness" decides forests
# (wet), deserts (dry) and plains (in between). Finally rivers run
# downhill and sites are placed where they make sense.
# ==========================================================================
def normalize(values):
    """Stretch a set of numbers so the smallest becomes 0 and the largest becomes 1."""
    low, high = min(values.values()), max(values.values())
    spread = (high - low) or 1.0
    return {k: (v - low) / spread for k, v in values.items()}


def noise_field(grid, rng, passes):
    """Give every hex a random number, then smooth it out.
    Each pass mixes every hex with its neighbours: more passes = bigger, softer patches."""
    f = {h: rng.random() for h in grid.hexes}
    for _ in range(passes):
        f = {h: (2 * f[h] + sum(f[n] for n in grid.neighbours(h))) / (2 + len(grid.neighbours(h)))
             for h in grid.hexes}
    return normalize(f)


def make_heights(grid, rng):
    """Invent a height (0 = lowest, 1 = highest) for every hex."""
    big = noise_field(grid, rng, max(3, (grid.cols + grid.rows) // 5))   # big shapes
    small = noise_field(grid, rng, 2)                                    # small details
    edge_band = max(1.0, min(grid.cols, grid.rows) * 0.25)
    height = {}
    for c, r in grid.hexes:
        # hexes near the edge are a little lower, so the sea tends to be at the edge
        from_edge = min(c, grid.cols - 1 - c, r, grid.rows - 1 - r)
        height[(c, r)] = 0.55 * big[(c, r)] + 0.25 * small[(c, r)] + 0.20 * min(1.0, from_edge / edge_band)
    return normalize(height)


def flood_sea(grid, height, n, rng, terrain):
    """Flood 'n' hexes with sea water.
    The water starts from the lowest hex on the edge and keeps spreading
    to the lowest hex next to it, like water filling a basin."""
    if n <= 0:
        return None
    edge = [h for h in grid.hexes if grid.on_edge(h)]
    start = min(edge, key=lambda h: height[h] + rng.uniform(0, 0.08))
    # 'queue' always gives back the lowest hex waiting to be flooded
    queue, seen, placed = [(height[start], start)], {start}, 0
    while queue and placed < n:
        _, hex_ = heapq.heappop(queue)
        terrain[hex_] = SEA
        placed += 1
        for nb in grid.neighbours(hex_):
            if nb not in seen:
                seen.add(nb)
                heapq.heappush(queue, (height[nb] + rng.uniform(0, 0.04), nb))
    return start


def dig_lakes(grid, height, n, rng, terrain):
    """Place 'n' lake hexes, grouped in small lakes of 1-4 hexes each, in low ground.
    Returns (how many lake hexes were placed, how many lakes)."""
    if n <= 0:
        return 0, 0
    # decide the size of each lake
    sizes, left = [], n
    while left > 0:
        s = min(left, rng.randint(1, 4))
        sizes.append(s)
        left -= s

    def free(h, strict):
        # Can a lake go here? The hex must still be empty. In strict mode
        # it also must not touch the sea or the edge of the map.
        if terrain[h] is not None:
            return False
        if strict and (grid.on_edge(h) or any(terrain[nb] == SEA for nb in grid.neighbours(h))):
            return False
        return True

    starts, placed = [], 0
    for size in sizes:
        # Look for a starting hex, keeping lakes apart. If there is no room,
        # try again with looser rules.
        candidates, strict = [], True
        for strict, min_dist in ((True, 3), (False, 2), (False, 1)):
            candidates = [h for h in grid.hexes if free(h, strict)
                          and all(grid.distance(h, s) >= min_dist for s in starts)]
            if candidates:
                break
        if not candidates:
            break
        # start among the lowest third of the free hexes
        candidates.sort(key=lambda h: height[h])
        start = rng.choice(candidates[:max(1, len(candidates) // 3)])
        starts.append(start)
        # grow the lake towards the lowest hexes around it
        queue, seen, done = [(height[start], start)], {start}, 0
        while queue and done < size:
            _, hex_ = heapq.heappop(queue)
            terrain[hex_] = LAKE
            done += 1
            for nb in grid.neighbours(hex_):
                if nb not in seen and free(nb, strict):
                    seen.add(nb)
                    heapq.heappush(queue, (height[nb] + rng.uniform(0, 0.05), nb))
        placed += done
    return placed, len(starts)


def place_mountains_and_hills(grid, height, n_mountains, n_hills, rng, terrain):
    """The highest free hexes become mountains, the next highest become hills."""
    land = [h for h in grid.hexes if terrain[h] is None]
    # a tiny bit of randomness makes the borders between them less regular
    by_height = sorted(land, key=lambda h: height[h] + rng.uniform(-0.03, 0.03), reverse=True)
    for h in by_height[:n_mountains]:
        terrain[h] = MOUNTAINS
    for h in by_height[n_mountains:n_mountains + n_hills]:
        terrain[h] = HILLS


def place_forests_and_deserts(grid, n_forests, n_deserts, rng, terrain):
    """Fill the remaining hexes: forests where it is wet, deserts where it is dry, plains elsewhere."""
    # a random "wetness" map, made of big and small patches
    wetness = {h: 0.7 * v for h, v in noise_field(grid, rng, max(2, (grid.cols + grid.rows) // 7)).items()}
    fine = noise_field(grid, rng, 1)
    to_water = grid.distances_from([h for h in grid.hexes if terrain[h] in WATER])
    for h in grid.hexes:
        wetness[h] += 0.3 * fine[h]
        # land next to water is wetter
        d = to_water[h]
        if d == 1:
            wetness[h] += 0.25
        elif d == 2:
            wetness[h] += 0.12
    # wettest free hexes -> forest
    free = sorted((h for h in grid.hexes if terrain[h] is None), key=lambda h: wetness[h], reverse=True)
    for h in free[:n_forests]:
        terrain[h] = FOREST
    # driest of the rest -> desert, everything else -> plains
    rest = sorted(free[n_forests:], key=lambda h: wetness[h])
    for h in rest[:n_deserts]:
        terrain[h] = DESERT
    for h in rest[n_deserts:]:
        terrain[h] = PLAINS


def trace_rivers(grid, terrain, height, n, rng):
    """Draw up to 'n' rivers.
    Each river starts high up (mountains or hills) and keeps flowing to
    the lowest neighbouring hex, until it reaches the sea, a lake, the
    edge of the map or another river. Rivers that get stuck are thrown away."""
    if n <= 0:
        return []
    # possible starting points: the highest hexes
    high = [h for h in grid.hexes if terrain[h] in (MOUNTAINS, HILLS)]
    if not high:
        high = [h for h in grid.hexes if terrain[h] not in WATER]
    high.sort(key=lambda h: height[h], reverse=True)
    springs = high[:max(1, int(len(high) * 0.7))]
    rng.shuffle(springs)

    rivers, river_hexes = [], set()
    max_length = grid.cols + grid.rows
    for spring in springs:
        if len(rivers) >= n:
            break
        # keep springs apart, and do not start right next to water
        if spring in river_hexes or any(grid.distance(spring, r["path"][0]) < 4 for r in rivers):
            continue
        if any(terrain[nb] in WATER for nb in grid.neighbours(spring)):
            continue
        path, end = [spring], None
        while len(path) <= max_length:
            current = path[-1]
            around = grid.neighbours(current)
            # reached the sea or a lake?
            water = [nb for nb in around if terrain[nb] in WATER]
            if water:
                end = ("water", min(water, key=lambda nb: height[nb]))
                break
            # reached another river? then it joins it
            joins = [nb for nb in around if nb in river_hexes]
            if joins and len(path) >= 3:
                end = ("join", joins[0])
                break
            # the river may not go back or loop around itself
            forbidden = set(path)
            for p in path[:-1]:
                forbidden.update(grid.neighbours(p))
            options = [nb for nb in around if nb not in forbidden and nb not in river_hexes]
            # at the edge, with nowhere lower to go, it leaves the map
            if grid.on_edge(current) and len(path) >= 3 and (
                    not options or min(height[nb] for nb in options) > height[current]):
                end = ("edge", None)
                break
            if not options:
                break   # stuck: this river will be thrown away
            path.append(min(options, key=lambda nb: height[nb] + rng.uniform(0, 0.03)))
        # keep only rivers that are at least 3 hexes long and end somewhere sensible
        if end and len(path) >= 3:
            rivers.append({"path": path, "end": end})
            river_hexes.update(path)
    return rivers


def place_sites(grid, terrain, rivers, wanted, rng, log):
    """Place cities, fortresses and dungeons on dry land.
    Each kind prefers some terrains (for example cities like plains near
    water) and sites keep a minimum distance from each other."""
    land = [h for h in grid.hexes if terrain[h] not in WATER]
    river_hexes = {h for r in rivers for h in r["path"]}

    def near_water(h):
        # on a river, or next to the sea or a lake
        return h in river_hexes or any(terrain[nb] in WATER for nb in grid.neighbours(h))

    # how much each kind of site likes each terrain (higher = more likely)
    base_weights = {
        CITY: {PLAINS: 4, HILLS: 2, FOREST: 1.2, DESERT: 0.6, MOUNTAINS: 0.2},
        FORTRESS: {HILLS: 4, MOUNTAINS: 3, PLAINS: 1.5, FOREST: 1, DESERT: 0.8},
        DUNGEON: {MOUNTAINS: 4, HILLS: 3.5, FOREST: 3, DESERT: 2.5, PLAINS: 1},
    }
    sites, taken = [], set()
    for kind, n in ((CITY, wanted[CITY]), (FORTRESS, wanted[FORTRESS]), (DUNGEON, wanted[DUNGEON])):
        if n <= 0:
            continue
        # minimum distance between two sites of the same kind:
        # the more land per site, the further apart they can be
        spacing = math.sqrt(len(land) / n)
        same_kind_dist = {CITY: max(3, round(spacing * 0.7)),
                          FORTRESS: max(2, round(spacing * 0.5)),
                          DUNGEON: max(2, round(spacing * 0.45))}[kind]
        relaxed = False
        for _ in range(n):
            same_kind = [h for k, h in sites if k == kind]
            d_same, d_other = same_kind_dist, 2
            # find hexes far enough from the other sites;
            # if there are none, slowly relax the distances
            while True:
                candidates = [h for h in land if h not in taken
                              and all(grid.distance(h, o) >= d_other for o in taken)
                              and all(grid.distance(h, o) >= d_same for o in same_kind)]
                if candidates:
                    break
                if d_same > d_other:
                    d_same -= 1
                elif d_other > 1:
                    d_other -= 1
                else:
                    break
                relaxed = True
            if not candidates:
                candidates = [h for h in land if h not in taken]
            # give every candidate hex a score, then pick one at random,
            # where a higher score means a higher chance
            cities = [h for k, h in sites if k == CITY]
            weights = []
            for h in candidates:
                w = base_weights[kind][terrain[h]]
                if kind == CITY:
                    w *= 3 if near_water(h) else 1           # cities like water
                    w *= 0.5 if grid.on_edge(h) else 1       # ...and not the map edge
                elif kind == FORTRESS:
                    # fortresses like high ground around them
                    w *= 1 + 0.5 * sum(terrain[nb] in (MOUNTAINS, HILLS) for nb in grid.neighbours(h))
                elif kind == DUNGEON and cities:
                    # dungeons like to be far from cities
                    w *= 1 + min(grid.distance(h, c) for c in cities) / 4
                weights.append(w)
            chosen = rng.choices(candidates, weights=weights)[0]
            sites.append((kind, chosen))
            taken.add(chosen)
        log.info(tr("info_site_kind", name=pick(SITE_NAMES[kind]), n=n, d=same_kind_dist)
                 + (tr("relaxed") if relaxed else ""))
    return sites


def build_land(params, counts, grid, rng, log):
    """Steps 3 to 9: heights, sea, lakes, mountains and hills, forests and
    deserts, rivers, sites. Returns (terrain of every hex, rivers, sites)."""
    log.step(tr("step_heights"))
    height = make_heights(grid, rng)
    log.info(tr("info_heights", n=len(grid.hexes)))

    # at the start every hex is empty (None); the steps below fill them in
    terrain = {h: None for h in grid.hexes}
    log.step(tr("step_sea"))
    start = flood_sea(grid, height, counts[SEA], rng, terrain)
    if start is None:
        log.info(tr("info_no_sea"))
    else:
        log.info(tr("info_sea", h=hex_code(start, 2), n=counts[SEA]))

    log.step(tr("step_lakes"))
    placed, n_lakes = dig_lakes(grid, height, counts[LAKE], rng, terrain)
    log.info(tr("info_lakes", n=n_lakes, h=placed))
    if placed < counts[LAKE]:
        log.warn(tr("warn_lakes", n=counts[LAKE] - placed))

    log.step(tr("step_relief"))
    place_mountains_and_hills(grid, height, counts[MOUNTAINS], counts[HILLS], rng, terrain)
    log.info(tr("info_relief", m=counts[MOUNTAINS], h=counts[HILLS]))

    log.step(tr("step_wetness"))
    place_forests_and_deserts(grid, counts[FOREST], counts[DESERT], rng, terrain)
    actual = {t: sum(1 for h in grid.hexes if terrain[h] == t)
              for t in (PLAINS, SEA, LAKE, HILLS, MOUNTAINS, FOREST, DESERT)}
    log.info(tr("info_result", list=", ".join(f"{pick(TERRAIN_NAMES[t])} {n}" for t, n in actual.items())))

    log.step(tr("step_rivers"))
    # automatic number of rivers: about one every 60 land hexes
    land = len(grid.hexes) - actual[SEA] - actual[LAKE]
    n_rivers = params["rivers"] if params["rivers"] >= 0 else max(0, round(land / 60))
    rivers = trace_rivers(grid, terrain, height, n_rivers, rng)
    for i, r in enumerate(rivers, 1):
        where = tr("river_" + r["end"][0])
        log.info(tr("info_river", i=i, h=hex_code(r["path"][0], 2), n=len(r["path"]), where=where))
    if len(rivers) < n_rivers:
        log.warn(tr("warn_rivers", d=len(rivers), n=n_rivers))

    log.step(tr("step_sites"))
    sites = place_sites(grid, terrain, rivers,
                        {CITY: params["cities"], FORTRESS: params["fortresses"], DUNGEON: params["dungeons"]},
                        rng, log)

    return terrain, rivers, sites


def print_sites(grid, terrain, rivers, sites):
    """Print the list of all sites with their hex number, handy for the game master's notes."""
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    print(tr("sites_header"))
    for kind in (CITY, FORTRESS, DUNGEON):
        for i, (_, h) in enumerate([s for s in sites if s[0] == kind], 1):
            extra = tr("on_river") if any(h in r["path"] for r in rivers) else ""
            print(f"  {pick(SITE_NAMES[kind]):<9} {i:>2}  →  {hex_code(h, digits)}  ({pick(TERRAIN_NAMES[terrain[h]])}{extra})")


# ==========================================================================
# FONTS AND SYMBOLS
# ==========================================================================
def open_font(spec, size):
    """Open a font file at the given size."""
    path, index = spec if isinstance(spec, tuple) else (spec, 0)
    return ImageFont.truetype(path, size, index=index)


def find_font(chosen=None):
    """Find a same-width font on this computer. Returns (normal font, bold font or None)."""
    candidates = []
    if chosen:
        candidates.append((chosen, None))   # the font chosen with --font comes first
    candidates += MONO_FONTS
    try:
        # if the matplotlib library is installed, it carries DejaVu Sans Mono with it
        import matplotlib
        base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        candidates.append((os.path.join(base, "DejaVuSansMono.ttf"), os.path.join(base, "DejaVuSansMono-Bold.ttf")))
    except Exception:
        pass
    for regular, bold in candidates:
        try:
            open_font(regular, 20)
        except OSError:
            continue           # this font is not here, try the next one
        try:
            if bold is None:
                raise OSError
            open_font(bold, 20)
        except OSError:
            bold = None        # no bold version: we will fake it later
        return regular, bold
    sys.exit(tr("err_no_font"))


def font_name(spec):
    """Just the file name of a font, for the messages."""
    return os.path.basename(spec[0] if isinstance(spec, tuple) else spec)


def font_metrics(spec):
    """How wide one letter is and how tall one line is, as a fraction of the font size."""
    f = open_font(spec, 200)
    ascent, descent = f.getmetrics()
    return f.getlength("M") / 200, (ascent + descent) / 200


def font_has_glyph(font, ch):
    """True if the font can really draw this symbol.
    We draw it and compare it with a character that surely does not exist:
    if they look the same, the font is missing the symbol."""
    def fingerprint(c):
        img = Image.new("L", (80, 80), 0)
        ImageDraw.Draw(img).text((10, 10), c, font=font, fill=255)
        return img.tobytes()
    missing = fingerprint("\U0010FFFD")
    return fingerprint(ch) != missing and any(fingerprint(ch))


class Glyphs:
    """Chooses between the fancy symbol and the plain one.
    Use it like a function: G("♣", "T") gives "♣", or "T" when fancy
    symbols are switched off or the font cannot draw "♣"."""

    def __init__(self, font, ascii_only):
        self.ascii_only = ascii_only
        self.missing = set()      # fancy symbols the font could not draw
        self._cache = {}          # remembers the answers, so each symbol is tested once
        self.font = font

    def __call__(self, fancy, plain):
        if self.ascii_only:
            return plain
        if fancy not in self._cache:
            self._cache[fancy] = all(c.isascii() or font_has_glyph(self.font, c) for c in fancy)
            if not self._cache[fancy]:
                self.missing.add(fancy)
        return fancy if self._cache[fancy] else plain


def pick_symbol(rng, choices, G):
    """Pick one symbol at random from a list, following the weights."""
    total = sum(w for _, _, w in choices)
    v = rng.uniform(0, total)
    for fancy, plain, w in choices:
        v -= w
        if v <= 0:
            return G(fancy, plain)
    return G(choices[-1][0], choices[-1][1])


# ==========================================================================
# THE CANVAS: A GRID OF LETTERS
# ==========================================================================
class Canvas:
    """A grid of letters. Every square also has a style that says how to draw it:
      n = normal black letter
      b = bold black letter
      i = inverted: white letter on a black square
      g = plain gray square (sea)
      G = normal letter on a gray square
      H = bold letter on a gray square (hex lines inside the sea)
      B = covered by a site box (drawn separately, see 'boxes')"""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.chars = [[" "] * width for _ in range(height)]     # the letters
        self.styles = [["n"] * width for _ in range(height)]    # the style of each letter
        self.boxes = []            # site boxes: (x, y, width, height, symbol)

    def put(self, x, y, ch, style="n"):
        """Write one letter, if it falls inside the canvas."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.chars[y][x], self.styles[y][x] = ch, style

    def write(self, x, y, text, style="n"):
        """Write a word, starting at (x, y) and going right."""
        for i, c in enumerate(text):
            self.put(x + i, y, c, style)

    def paste(self, other, ox, oy):
        """Copy another canvas onto this one, with its top-left corner at (ox, oy)."""
        for y in range(other.height):
            for x in range(other.width):
                self.put(ox + x, oy + y, other.chars[y][x], other.styles[y][x])
        self.boxes += [(ox + x, oy + y, w, h, g) for x, y, w, h, g in other.boxes]

    def copy(self):
        """A separate copy of this canvas."""
        c = Canvas(self.width, self.height)
        c.chars = [row[:] for row in self.chars]
        c.styles = [row[:] for row in self.styles]
        c.boxes = list(self.boxes)
        return c

    def lines(self):
        """The canvas as lines of text, for the .txt file."""
        return ["".join(row).rstrip() for row in self.chars]


# ==========================================================================
# SHAPE OF A HEX MADE OF LETTERS (flat top)
#
# 'k' is the size: k = 2 for small hexes, k = 3 for big ones.
#
#   k = 2              k = 3
#     ____               ______
#    /    \             /      \
#   /      \           /        \
#   \      /          /          \
#    \____/           \          /
#                      \        /
#                       \______/
# ==========================================================================
def hex_template(k):
    """Describe one hex: where its border letters go and which squares are inside it.
    Positions are (row, column) counted from the top-left corner of the hex."""
    u = 2 * k                        # length of the top and bottom sides
    border, inside = [], []
    # top side
    border += [(0, x, "_") for x in range(k + 1, k + u + 1)]
    # upper half: the sides lean outwards  / \
    for i in range(1, k + 1):
        border += [(i, k + 1 - i, "/"), (i, k + u + i, "\\")]
        inside += [(i, x) for x in range(k + 2 - i, k + u + i)]
    # lower half: the sides lean inwards  \ /
    for j in range(1, k):
        border += [(k + j, j, "\\"), (k + j, 2 * k + u + 1 - j, "/")]
        inside += [(k + j, x) for x in range(j + 1, 2 * k + u + 1 - j)]
    # bottom row: corners and bottom side
    border += [(2 * k, k, "\\"), (2 * k, k + u + 1, "/")]
    border += [(2 * k, x, "_") for x in range(k + 1, k + u + 1)]
    return border, inside


def map_size(cols, rows, k):
    """How many letters wide and tall the whole map is."""
    return 3 * k * (cols - 1) + 4 * k + 1, 2 * k * rows + k + 1


def hex_origin(c, r, k):
    """Top-left corner of hex (column, row) on the letter grid.
    Odd columns are pushed down by half a hex."""
    return 3 * k * c, 2 * k * r + (k if c & 1 else 0)


def hex_centre(c, r, k):
    """The exact centre of a hex on the letter grid (it can fall between two letters)."""
    x0, y0 = hex_origin(c, r, k)
    return x0 + 2 * k + 1, y0 + k + 1


# ==========================================================================
# RIVERS
#
# First we draw a smooth line through the centres of the river hexes, then
# we turn that line into a chain of letter squares (a staircase that only
# moves left, right, up or down), and finally each square gets the right
# double-line character.
# ==========================================================================
def wiggle(points, scale, rng, amount=0.18):
    """Add a random bend halfway along each piece of the line, so it wiggles."""
    out = [points[0]]
    for p, q in zip(points, points[1:]):
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy) or 1
        o = rng.uniform(-amount, amount) * scale
        out += [(mx - dy / length * o, my + dx / length * o), q]   # push the middle point sideways
    return out


def smooth(points, rounds=3):
    """Round off the corners of a broken line, so it becomes a smooth curve.
    Each round cuts every corner, replacing it with two points."""
    for _ in range(rounds):
        new = [points[0]]
        for p, q in zip(points, points[1:]):
            new.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            new.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        new.append(points[-1])
        points = new
    return points


def river_line(grid, river, k, rng):
    """The smooth line of a river, measured in letter squares."""
    path, (end_kind, target) = river["path"], river["end"]
    points = [hex_centre(*h, k) for h in path]
    # start a little away from the centre of the spring hex
    points[0] = (points[0][0] * 0.7 + points[1][0] * 0.3, points[0][1] * 0.7 + points[1][1] * 0.3)
    last = path[-1]
    lx, ly = points[-1]
    if end_kind == "water":
        # stop halfway to the water hex, which is on the coastline
        tx, ty = hex_centre(*target, k)
        points.append(((lx + tx) / 2, (ly + ty) / 2))
    elif end_kind == "join":
        # meet the other river at the centre of its hex
        points.append(hex_centre(*target, k))
    else:
        # leave the map through the side that keeps the river going straight on
        px, py = points[-2]
        outside = [n for n in grid.all_neighbours(last) if not grid.inside(n)]
        exit_hex = max(outside, key=lambda n: (hex_centre(*n, k)[0] - lx) * (lx - px)
                       + (hex_centre(*n, k)[1] - ly) * (ly - py))
        tx, ty = hex_centre(*exit_hex, k)
        points.append(((lx + tx) / 2, (ly + ty) / 2))
    # add gentle bends, then round the corners
    return smooth(wiggle(points, 1.2 * k, rng, 0.15), 2)


def line_to_squares(points, aspect):
    """Turn a smooth line into a chain of touching letter squares.
    Each step moves to the square on the left, right, above or below,
    so the double-line characters always connect.
    'aspect' is how many times a letter square is taller than it is wide."""
    squares = []

    def add(sq):
        # if the line comes back to a square it already visited,
        # cut away the loop in between
        if sq in squares:
            del squares[squares.index(sq) + 1:]
        else:
            squares.append(sq)

    current = (math.floor(points[0][0]), math.floor(points[0][1]))
    add(current)
    for p, q in zip(points, points[1:]):
        # walk along each piece of the line in small steps
        steps = max(1, int(math.hypot(q[0] - p[0], (q[1] - p[1]) * aspect) / 0.3))
        for t in range(1, steps + 1):
            x = p[0] + (q[0] - p[0]) * t / steps
            y = p[1] + (q[1] - p[1]) * t / steps
            target = (math.floor(x), math.floor(y))
            # move one square at a time towards the target square,
            # sideways or up/down, whichever is further away
            while current != target:
                dx, dy = target[0] - current[0], target[1] - current[1]
                if dx and (not dy or abs(dx) > abs(dy) * aspect):
                    current = (current[0] + (1 if dx > 0 else -1), current[1])
                else:
                    current = (current[0], current[1] + (1 if dy > 0 else -1))
                add(current)
    return squares


# ==========================================================================
# BUILDING THE MAP OUT OF LETTERS
# ==========================================================================
def draw_map(grid, terrain, rivers, sites, k, G, rng, aspect):
    """Write the whole map on a letter grid: terrains, hex borders, rivers, sites.
    Each layer can overwrite the one before it."""
    width, height = map_size(grid.cols, grid.rows, k)
    canvas = Canvas(width, height)
    border, inside = hex_template(k)

    # 1. terrains: sea is plain gray, plains stay empty, the others are filled with symbols
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        kind = terrain[(c, r)]
        if kind == SEA:
            for (yy, xx) in inside:
                # gray square; the letter ≈ is kept only for the .txt file
                canvas.put(x0 + xx, y0 + yy, G("≈", "~"), "g")
            continue
        choices = TERRAIN_GLYPHS[kind]
        if not choices:
            continue
        for (yy, xx) in inside:
            canvas.put(x0 + xx, y0 + yy, pick_symbol(rng, choices, G))

    # 2. hex borders, in bold so the grid is easy to see on paper.
    #    A border between two sea hexes gets a gray background, so the sea
    #    looks like one continuous gray area.
    shared = {}    # for each border square: [letter, "only sea hexes share it so far"]
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        for (yy, xx, ch) in border:
            shared.setdefault((x0 + xx, y0 + yy), [ch, True])
            shared[(x0 + xx, y0 + yy)][1] &= terrain[(c, r)] == SEA
    for (x, y), (ch, sea_only) in shared.items():
        canvas.put(x, y, ch, "H" if sea_only else "b")

    # 3. rivers: note in which directions each square connects,
    #    then write the matching double-line character
    arms = {}
    for river in rivers:
        squares = line_to_squares(river_line(grid, river, k, rng), aspect)
        for a, b in zip(squares, squares[1:]):
            d = {(1, 0): "r", (-1, 0): "l", (0, 1): "d", (0, -1): "u"}[(b[0] - a[0], b[1] - a[1])]
            arms.setdefault(a, set()).add(d)
            arms.setdefault(b, set()).add(OPPOSITE[d])
    for (x, y), directions in arms.items():
        fancy, plain = RIVER_CHARS[frozenset(directions)]
        canvas.put(x, y, G(fancy, plain), "b")

    # 4. sites: a black box 4 letters wide and 2 tall in the middle of the hex.
    #    In the .txt file it looks like [⌂⌂]; in the picture it is drawn as a
    #    black box with one big white symbol.
    cx = 2 * k + 1
    for kind, (c, r) in sites:
        x0, y0 = hex_origin(c, r, k)
        g = G(*SITE_GLYPHS[kind])
        for yy in (k, k + 1):
            canvas.write(x0 + cx - 2, y0 + yy, "[" + g + g + "]", "B")
        canvas.boxes.append((x0 + cx - 2, y0 + k, 4, 2, g))
    return canvas


def write_hex_numbers(page, grid, k, ox, oy):
    """Write the hex number in the top row inside every hex.
    'ox' and 'oy' tell where the map sits on the page."""
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    _, inside = hex_template(k)
    top_row = [xx for (yy, xx) in inside if yy == 1]    # the squares of the top inside row
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        y = oy + y0 + 1
        # clear the row first (rivers are left in place)
        for xx in top_row:
            style = page.styles[y][ox + x0 + xx]
            if style != "b":
                page.put(ox + x0 + xx, y, " ", "g" if style in "gG" else "n")
        # then write the number, centred. The digits always get a white
        # background, even in the sea: they stay readable on cheap printers.
        code = hex_code((c, r), digits)
        x_num = ox + x0 + 2 * k + 1 - len(code) // 2
        for i, digit in enumerate(code):
            page.put(x_num + i, y, digit, "n")


# ==========================================================================
# THE PAGE: FRAME, TITLE, MAP AND LEGEND
# ==========================================================================
def legend_entries(G):
    """The entries of the legend: (sample symbols, name)."""
    # each terrain entry is (sample symbols, name, style of the sample)
    terrains = [
        (G("▲^", "^A"), tr("leg_mountains"), "b"), (G("∩n", "nm"), tr("leg_hills"), "b"),
        (G("♣♠", "TY"), tr("leg_forest"), "b"), ("", tr("leg_plains"), "b"), (G("░·", ".:"), tr("leg_desert"), "b"),
        (G("≈≈", "~~"), tr("leg_sea"), "g"),   # "g": this sample is drawn as a gray patch
        (G("≈≈", "~~"), tr("leg_lake"), "b"), (G("═╗", "=+"), tr("leg_river"), "b"),
    ]
    sites = [(G(*SITE_GLYPHS[kind]), pick(SITE_NAMES[kind])) for kind in (CITY, FORTRESS, DUNGEON)]
    if G.ascii_only:
        # with --solo-ascii even "Città" loses its accent
        sites = [(g, name.replace("à", "a'")) for g, name in sites]
    return terrains, sites


def pack_legend(G, max_width):
    """Arrange the legend entries in as few lines as possible, each line at most 'max_width' letters."""
    terrains, sites = legend_entries(G)
    # each entry is a list of (text, style) pieces
    entries = [[(g, style), (" " + name, "n")] if g else [(name, "n")] for g, name, style in terrains]
    entries += [[("[" + g + "]", "i"), (" " + name, "n")] for g, name in sites]
    lines, line, length = [], [], 0
    for entry in entries:
        w = sum(len(text) for text, _ in entry)
        # start a new line when this entry would not fit
        if line and length + 4 + w > max_width:
            lines.append(line)
            line, length = [], 0
        line.append(entry)
        length += w + (4 if length else 0)   # 4 spaces between entries
    if line:
        lines.append(line)
    return lines


def compose_page(map_canvas, n_cols, n_rows, legend_lines, title, subtitle, G):
    """Build the whole page as a letter grid 'n_cols' wide and 'n_rows' tall.
    Returns the page and where the map was placed on it."""
    page = Canvas(n_cols, n_rows)
    # double-line frame all around
    horizontal, vertical = G("═", "-"), G("║", "|")
    for x in range(n_cols):
        page.put(x, 0, horizontal)
        page.put(x, n_rows - 1, horizontal)
    for y in range(n_rows):
        page.put(0, y, vertical)
        page.put(n_cols - 1, y, vertical)
    # two dividing lines: under the title and above the legend
    y_legend_line = n_rows - len(legend_lines) - 2
    for y in (2, y_legend_line):
        page.put(0, y, G("╠", "+"))
        page.put(n_cols - 1, y, G("╣", "+"))
        for x in range(1, n_cols - 1):
            page.put(x, y, horizontal)
    # the four corners
    for x, y, ch in ((0, 0, "╔"), (n_cols - 1, 0, "╗"), (0, n_rows - 1, "╚"), (n_cols - 1, n_rows - 1, "╝")):
        page.put(x, y, G(ch, "+"))

    # title set into the top border, subtitle just below it
    heading = f"{G('╡', '[')} {title.upper()} {G('╞', ']')}"
    page.write((n_cols - len(heading)) // 2, 0, heading, "b")
    page.write((n_cols - len(subtitle)) // 2, 1, subtitle)

    # the map, centred in the space between the two dividing lines
    area_top, area_height = 3, y_legend_line - 3
    ox = (n_cols - map_canvas.width) // 2
    oy = area_top + (area_height - map_canvas.height) // 2
    page.paste(map_canvas, ox, oy)

    # the legend, each line centred
    for i, line in enumerate(legend_lines):
        length = sum(sum(len(text) for text, _ in entry) for entry in line) + 4 * (len(line) - 1)
        x = (n_cols - length) // 2
        for j, entry in enumerate(line):
            if j:
                x += 4
            for text, style in entry:
                page.write(x, y_legend_line + 1 + i, text, style)
                x += len(text)
    return page, ox, oy


# ==========================================================================
# FITTING THE PAGE ON PAPER (A4, A3, A2), DRAWING AND SAVING
# ==========================================================================
def paper_pixels(paper, orientation):
    """Size in pixels of a sheet at 600 dpi, upright ("portrait") or sideways ("landscape")."""
    w_mm, h_mm = PAPERS[paper]
    if orientation == "landscape":
        w_mm, h_mm = h_mm, w_mm
    return round(mm(w_mm)), round(mm(h_mm))


# every allowed picture size: each paper, upright and sideways, at 600 dpi
VALID_SIZES = {paper_pixels(p, o) for p in PAPERS for o in ("portrait", "landscape")}


def choose_sheet(map_width, map_height, legend_lines_guess, paper, orientation, aspect):
    """Decide the sheet direction and the letter width in mm for one paper size.
    With orientation "auto" the direction follows the shape of the map: the sheet
    is turned the way that lets the letters be biggest.
    Returns (letter width, how well the sheet is filled, direction, sheet width, sheet height)."""
    short, long_ = PAPERS[paper]
    max_char = MAX_CHAR_MM * short / PAPERS["A4"][0]      # bigger sheet, bigger letters allowed
    options = []
    for name, (w_mm, h_mm) in (("portrait", (short, long_)), ("landscape", (long_, short))):
        if orientation not in ("auto", name):
            continue
        page_w, page_h = w_mm - 2 * MARGIN_MM, h_mm - 2 * MARGIN_MM
        # the biggest letters that let map + frame + title + legend fit
        char_mm = min(page_w / (map_width + 4), page_h / ((map_height + legend_lines_guess + 7) * aspect),
                      max_char)
        filled = (map_width * char_mm) * (map_height * char_mm * aspect) / (page_w * page_h)
        options.append((char_mm, filled, name, w_mm, h_mm))
    # biggest letters wins; if the two are close (within 8%), the fuller sheet wins
    best = max(o[0] for o in options)
    return max((o for o in options if o[0] >= best * 0.92), key=lambda o: o[1])


def fill_page(params, font_spec, aspect, log):
    """Work out how many hexes fill an A4 page frame when letters are
    READABLE_CHAR_MM wide (a size that prints well).
    Only the sizes left on "auto" are changed; sizes typed by the user stay."""
    orientation = "portrait" if params["orientation"] == "portrait" else "landscape"
    w_mm, h_mm = PAPERS["A4"] if orientation == "portrait" else PAPERS["A4"][::-1]
    k = 3 if params["size"] == "large" else 2
    # how many letters fit across and down the sheet
    n_cols = int((w_mm - 2 * MARGIN_MM) / READABLE_CHAR_MM)
    n_rows = int((h_mm - 2 * MARGIN_MM) / (READABLE_CHAR_MM * aspect))
    legend_lines = len(pack_legend(Glyphs(open_font(font_spec, 40), params["ascii_only"]), n_cols - 4))
    # how many hexes fit in that space, leaving room for frame, title and legend
    columns = max(2, (n_cols - 4 - (4 * k + 1)) // (3 * k) + 1)
    rows = max(2, (n_rows - legend_lines - 7 - (k + 1)) // (2 * k))
    if params["columns"] == "auto":
        params["columns"] = columns
    if params["rows"] == "auto":
        params["rows"] = rows
    log.info(tr("info_auto_grid", c=params["columns"], r=params["rows"], o=pick(ORIENTATION_NAMES[orientation]),
                mm=READABLE_CHAR_MM))


def hex_size(params, grid, paper, aspect):
    """How big each hex is in letters: k = 2 (small) or 3 (large).
    With "auto", large hexes are used only if their letters stay easy to read on this paper."""
    if params["size"] == "small":
        return 2
    if params["size"] == "large":
        return 3
    mw, mh = map_size(grid.cols, grid.rows, 3)
    return 3 if choose_sheet(mw, mh, 3, paper, params["orientation"], aspect)[0] >= 1.4 else 2


class QuietLog:
    """A log that prints nothing: used to try out a paper size without messages."""

    def info(self, message):
        pass

    def warn(self, message):
        pass


def suggest_paper(params, grid, fonts, G):
    """For each paper, lay out the page exactly as it would be printed and note
    how wide the letters come out. The suggested paper is the smallest one where
    the letters are easy to read.
    Returns (suggested paper, {paper: (letter width in mm, direction, hex size k)})."""
    font_spec, bold_spec, advance_em, aspect = fonts
    options = {}
    for paper in PAPERS:
        k = hex_size(params, grid, paper, aspect)
        layout = page_layout(params, grid, k, paper, 0, font_spec, bold_spec, advance_em, aspect, G, QuietLog())[0]
        char_w, width, work_w = layout[2], layout[5], layout[7]
        printed_char_mm = char_w * (width / work_w) / DPI * 25.4
        orientation = "landscape" if layout[5] > layout[6] else "portrait"
        options[paper] = (printed_char_mm, orientation, k)
    readable = [p for p in PAPERS if options[p][0] >= GOOD_CHAR_MM]
    return (readable[0] if readable else list(PAPERS)[-1]), options


def ask_paper(params, grid, fonts, G, interactive, log):
    """Show how the map would look on each paper and pick the format:
    asked to the user when the program is asking questions, otherwise taken
    from --formato, from the saved settings, or from the suggestion."""
    suggested, options = suggest_paper(params, grid, fonts, G)
    for paper, (char_mm, orientation, k) in options.items():
        if char_mm < SMALL_CHAR_MM:
            verdict = tr("v_too_small")
        elif char_mm < GOOD_CHAR_MM:
            verdict = tr("v_small")
        else:
            verdict = tr("v_good")
        note = tr("suggested") if paper == suggested else ""
        hexes = tr("hexes_large") if k == 3 else tr("hexes_small")
        log.info(tr("info_paper_option", paper=paper, o=pick(ORIENTATION_NAMES[orientation]), hexes=hexes,
                    mm=char_mm, v=verdict, note=note))
    default = params.get("paper") or suggested
    if interactive:
        print()
        while True:
            answer = input(tr("q_paper", default=default)).strip().upper()
            if not answer:
                return default
            if answer in PAPERS:
                return answer
            print(tr("paper_retry"))
    return default


def render(canvas, regular, bold, char_w, char_h, size, width, height, ox, oy, progress=None):
    """Draw the letter grid as a picture 'width' x 'height' pixels big.
    'regular' and 'bold' are the fonts, 'char_w' and 'char_h' the size of one
    letter square, 'ox' and 'oy' where the grid starts. 'progress', if given,
    is told after each line of letters how much of the drawing is done (0 to 1)."""
    img = Image.new("L", (width, height), 255)   # white grayscale picture
    d = ImageDraw.Draw(img)
    thicken = max(1, size // 22)                 # shift used to fake a bold letter
    real_bold = bold is not None and bold is not regular
    probe = bold.font_variant(size=40) if real_bold else None
    bold_can_draw = {}                           # remembers which symbols the bold font has

    def draw_bold(px, py, ch):
        # Some bold fonts (for example Menlo Bold on macOS) lack the double-line
        # river symbols and would show an empty box. For any symbol the bold font
        # cannot draw, use the normal font drawn twice, a hair apart.
        if real_bold:
            if ch not in bold_can_draw:
                bold_can_draw[ch] = ch.isascii() or font_has_glyph(probe, ch)
            if bold_can_draw[ch]:
                d.text((px, py), ch, font=bold, fill=0, anchor="la")
                return
        d.text((px, py), ch, font=regular, fill=0, anchor="la")
        d.text((px + thicken, py), ch, font=regular, fill=0, anchor="la")

    for y in range(canvas.height):
        py = oy + y * char_h
        for x in range(canvas.width):
            ch, style = canvas.chars[y][x], canvas.styles[y][x]
            # nothing to draw: squares under a site box, and plain spaces
            if style == "B" or (ch == " " and style not in "igGH"):
                continue
            px = ox + x * char_w
            # gray squares (sea), with or without a letter on top
            if style in "gGH":
                d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=SEA_GRAY)
                if style == "G":
                    d.text((px, py), ch, font=regular, fill=0, anchor="la")
                elif style == "H":
                    draw_bold(px, py, ch)
                continue
            if style == "i":
                # white letter on black (brackets are hidden)
                d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=0)
                if ch not in "[] ":
                    d.text((px, py), ch, font=regular, fill=255, anchor="la")
            elif style == "b":
                draw_bold(px, py, ch)
            else:
                d.text((px, py), ch, font=regular, fill=0, anchor="la")
        if progress:
            progress((y + 1) / canvas.height)
    # site boxes: black rectangle with one big white symbol in the middle
    big = regular.font_variant(size=int(size * 1.7))
    for bx, by, bw, bh, g in canvas.boxes:
        x1, y1 = ox + bx * char_w, oy + by * char_h
        d.rectangle([x1, y1, x1 + bw * char_w, y1 + bh * char_h], fill=0)
        d.text((x1 + bw * char_w / 2, y1 + bh * char_h / 2), g, font=big, fill=255, anchor="mm")
    return img


def save_png(img, path, settings=None):
    """The only place where pictures are saved: every PNG must be exactly an
    A4, A3 or A2 sheet at 600 dpi. The map's settings are hidden inside the
    file, so the map can be rebuilt from its seed."""
    if img.size not in VALID_SIZES:
        raise ValueError(tr("err_size", path=path, size=img.size))
    info = PngInfo()
    if settings:
        # keep everything except where the file was saved and the seed (it is in the file name)
        data = {k: v for k, v in settings.items() if k not in ("output", "seed")}
        info.add_itxt(SETTINGS_KEY, json.dumps(data, ensure_ascii=False))
    # no extra "optimize" pass: on an A2 at 600 dpi it would take a long time
    img.save(path, dpi=(DPI, DPI), pnginfo=info)


def save(canvas, layout, png_path, settings=None):
    """Save the page as a PNG picture and as a .txt file with the same name."""
    regular, bold, char_w, char_h, size, width, height, work_w, work_h, ox, oy = layout
    live = LiveBar()
    drawing = tr("pb_drawing")
    # drawing takes most of the time: it fills the bar up to 90%, saving does the rest
    img = render(canvas, regular, bold, char_w, char_h, size, work_w, work_h, ox, oy,
                 progress=lambda done: live.update(0.9 * done, drawing))
    if (work_w, work_h) != (width, height):
        # the page came out bigger than the sheet: shrink it evenly and centre it
        f = min(width / work_w, height / work_h)
        smaller = img.resize((round(work_w * f), round(work_h * f)), Image.LANCZOS)
        img = Image.new("L", (width, height), 255)
        img.paste(smaller, ((width - smaller.width) // 2, (height - smaller.height) // 2))
    live.update(0.9, tr("pb_saving"))
    save_png(img, png_path, settings)
    with open(png_path[:-4] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(canvas.lines()) + "\n")
    live.finish()


def page_layout(params, grid, k, paper, seed, font_spec, bold_spec, advance_em, aspect, G, log):
    """Work out letter size, page size in letters and where everything goes,
    for the chosen paper. Returns what 'save' and 'compose_page' need."""
    map_w, map_h = map_size(grid.cols, grid.rows, k)
    # The legend may need one or more lines depending on the page width, and the
    # page width depends on the legend: repeat the sums until they agree.
    legend_guess = 3
    for _ in range(8):
        char_mm, _, orientation, w_mm, h_mm = choose_sheet(map_w, map_h, legend_guess, paper,
                                                           params["orientation"], aspect)
        size = max(6, int(mm(char_mm) / advance_em))
        regular = open_font(font_spec, size)
        bold = open_font(bold_spec, size) if bold_spec else regular
        char_w = regular.getlength("M")        # width of one letter square, in pixels
        ascent, descent = regular.getmetrics()
        char_h = ascent + descent               # height of one letter square, in pixels
        width, height = paper_pixels(paper, orientation)
        area_w = width - 2 * mm(MARGIN_MM)
        area_h = height - 2 * mm(MARGIN_MM)
        n_cols, n_rows = int(area_w // char_w), int(area_h // char_h)
        legend = pack_legend(G, n_cols - 4)
        if len(legend) <= legend_guess and n_rows >= map_h + len(legend) + 7:
            break
        # not enough room yet: count one more legend line and try again
        legend_guess = max(len(legend), legend_guess + 1)
    dot = G("·", "-")
    subtitle = tr("subtitle", scale=params["scale"], dot=dot, c=grid.cols, x=G("×", "x"), r=grid.rows, seed=seed)
    legend = pack_legend(G, n_cols - 4)
    # Safety net: if something does not fit (a very long title, for example),
    # make the page bigger now; it will be shrunk to the sheet when saving.
    legend_width = max(sum(len(t) for entry in line for t, _ in entry) + 4 * (len(line) - 1) for line in legend)
    need_cols = max(n_cols, map_w + 4, len(params["title"]) + 8, len(subtitle) + 4, legend_width + 4)
    need_rows = max(n_rows, map_h + len(legend) + 7)
    work_w, work_h, shrink = width, height, 1.0
    if need_cols > n_cols or need_rows > n_rows:
        n_cols, n_rows = need_cols, need_rows
        work_w = max(width, round(n_cols * char_w + 2 * mm(MARGIN_MM)))
        work_h = max(height, round(n_rows * char_h + 2 * mm(MARGIN_MM)))
        shrink = min(width / work_w, height / work_h)
        log.warn(tr("warn_shrink", p=shrink, paper=paper))
    # centre the letter grid on the page
    ox = (work_w - n_cols * char_w) / 2
    oy = (work_h - n_rows * char_h) / 2
    printed_char_mm = char_w * shrink / DPI * 25.4
    log.info(tr("info_sheet", paper=paper, o=pick(ORIENTATION_NAMES[orientation]), w=width, h=height, dpi=DPI,
                nc=n_cols, nr=n_rows, mm=printed_char_mm))
    log.info(tr("info_hexes", prefix=tr("hexes_desc_large" if k == 3 else "hexes_desc_small"), k=k,
                w=2 * k + 2 * k + 1, h=2 * k, mw=map_w, mh=map_h))
    if printed_char_mm < SMALL_CHAR_MM:
        log.warn(tr("warn_tiny"))
    layout = (regular, bold if bold_spec else regular, char_w, char_h, size, width, height, work_w, work_h, ox, oy)
    return layout, n_cols, n_rows, legend, subtitle


# ==========================================================================
# MAIN PROGRAM
# ==========================================================================
def main():
    # The first time the program runs, create the maps_generated folder next to wyrmhex.py
    first_run = make_maps_folder()
    # No options typed? Then ask the questions one by one.
    interactive = len(sys.argv) == 1
    params = ask_settings() if interactive else settings_from_options(sys.argv[1:])
    # the settings are decided: the conjuring begins
    show_conjuring()
    log = Log(12)

    # Step 1: find a font, choose the grid size if needed, check the settings,
    # then tell the seed and the folder where the map will be saved
    log.step(tr("step_validate"))
    font_spec, bold_spec = find_font(params["font"])
    advance_em, line_em = font_metrics(font_spec)
    aspect = line_em / advance_em        # a letter square is this many times taller than wide
    if "auto" in (params["columns"], params["rows"]):
        fill_page(params, font_spec, aspect, log)
    counts = validate(params, log)
    # use the seed the user gave, or make a new one
    seed = params["seed"] if params["seed"] is not None else new_seed()
    rng = random.Random(seed)            # every random choice of the land comes from this seed
    log.info(tr("info_seed", s=seed))
    if first_run:
        log.info(tr("info_new_folder", folder=short_path(MAPS_FOLDER)))
    log.info(tr("info_folder", folder=short_path(map_folder(params["output"], seed))))

    # Step 2: tell which font is used, and prepare the hex grid
    log.step(tr("step_font"))
    grid = HexGrid(params["columns"], params["rows"])
    log.info(tr("info_font", name=font_name(font_spec), fake="" if bold_spec else tr("fake_bold"), a=aspect))

    # Steps 3 to 9: build the land
    terrain, rivers, sites = build_land(params, counts, grid, rng, log)

    # Step 10: the map is ready, now the print format
    log.step(tr("step_paper"))
    G = Glyphs(open_font(font_spec, 40), params["ascii_only"])
    paper = ask_paper(params, grid, (font_spec, bold_spec, advance_em, aspect), G, interactive, log)
    params["paper"] = paper
    k = hex_size(params, grid, paper, aspect)
    layout, n_cols, n_rows, legend, subtitle = page_layout(
        params, grid, k, paper, seed, font_spec, bold_spec, advance_em, aspect, G, log)

    # a separate random generator for the symbols, so they are the same every time
    drawing_rng = random.Random(seed + 1)
    map_canvas = draw_map(grid, terrain, rivers, sites, k, G, drawing_rng, aspect)
    page, mx, my = compose_page(map_canvas, n_cols, n_rows, legend, params["title"], subtitle, G)
    plain_path, numbered_path = output_names(params["output"], seed)

    # Step 11: the map without numbers
    log.step(tr("step_plain", paper=paper, dpi=DPI))
    save(page, layout, plain_path, params)
    log.info(tr("saved", a=short_path(plain_path), b=short_path(plain_path[:-4] + ".txt")))
    if G.missing:
        log.warn(tr("warn_missing_glyphs", g=" ".join(sorted(G.missing))))

    # Step 12: the same page with the hex numbers added
    log.step(tr("step_numbered", paper=paper, dpi=DPI))
    numbered = page.copy()
    write_hex_numbers(numbered, grid, k, mx, my)
    save(numbered, layout, numbered_path, params)
    log.info(tr("saved", a=short_path(numbered_path), b=short_path(numbered_path[:-4] + ".txt")))

    print_sites(grid, terrain, rivers, sites)
    log.done()


if __name__ == "__main__":
    # Never crash because the console cannot show a symbol: show "?" instead.
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C (or the input ending) stops the program quietly
        print(tr("interrupted"))
        sys.exit(1)
