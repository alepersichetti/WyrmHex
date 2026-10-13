#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WyrmHex v1.0.0 - random hexcrawl maps for OSR games, all in ASCII.

Looks like an old terminal game (Dwarf Fortress, NetHack): hexes drawn with
_ / \\, terrain as CP437 symbols (forest ♣♠, mountains ▲^, hills ∩n, lakes ≈,
deserts ░·, swamps ⌠"), empty plains, gray sea, rivers in ═║╔╗, and sites as
white glyphs in black boxes. Black on white for printing, or in colour on a
white or black background. A4/A3/A2 at 600 dpi; the sheet turns to match the
map and the best paper size is suggested.

Output goes to maps_generated/<seed>/ next to this file (or --output):
  <seed>_nonumber.png/.txt   for the players
  <seed>_number.png/.txt     same map, hexes numbered CCRR (0101 = top left)

The seed (e.g. 475T-4KM4-MY0B-JNDJ-ZYEQ-K164) holds the whole land, so the
same seed always gives the same map. The PNG also keeps the settings.

Usage. Every option has an Italian and an English name, use whichever:
  python wyrmhex.py                              interactive: new map, rebuild one,
                                                 or edit one hex by hex (editor)
  python wyrmhex.py --seme 42                    / --seed 42
  python wyrmhex.py --griglia 20x15              / --grid 20x15
  python wyrmhex.py --citta 4 --fortezze 2 --dungeon 6
                    / --cities 4 --fortresses 2 --dungeons 6   (0-99 each)
  python wyrmhex.py --mare 25 --paludi 10 --pianura 10
                    / --sea 25 --swamps 10 --plains 10
      (also --laghi/--lakes, --colline/--hills, --montagne/--mountains,
       --foreste/--forests, --deserti/--deserts; whole numbers, max 100 in
       total, whatever is left becomes plains)
  python wyrmhex.py --casuale                    / --random
      (random sites, terrain % and rivers; ignores the options above)
  python wyrmhex.py --riproduci 475T-4KM4-MY0B-JNDJ-ZYEQ-K164
                    / --reproduce 475T-4KM4-MY0B-JNDJ-ZYEQ-K164
  python wyrmhex.py --riproduci 475T-4KM4-MY0B-JNDJ-ZYEQ-K164 --modificata
                    / --reproduce 475T-4KM4-MY0B-JNDJ-ZYEQ-K164 --edited
      (the edited version made with the editor, saved as <seed>_edit_nonumber/number)
  python wyrmhex.py --formato A3                / --format A3
  python wyrmhex.py --titolo "Terre del Nord" --scala 12
                    / --title "Northern Lands" --scale 12
      (miles per hex: 2, 6, 12, 24 or any number; free text like "5 km" works too)
  python wyrmhex.py --solo-ascii                 / --ascii-only
  python wyrmhex.py --colori --sfondo nero       / --colors --background black
  python wyrmhex.py --lingua en                  / --language en  (default: Italian)
  python wyrmhex.py --help

Code and comments are in English, the UI is Italian or English.
"""

import argparse
import heapq
import json
import math
import os
import random
import re
import secrets
import sys
import textwrap
import time
import unicodedata
import zlib
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFont
    from PIL.PngImagePlugin import PngInfo
except ImportError:
    sys.exit("Manca la libreria Pillow. Installala con:  pip install -r requirements.txt\n"
             "Pillow is missing. Install it with:   pip install -r requirements.txt")

# A2 at 600 dpi is ~139 Mpx, over Pillow's decompression bomb limit. They're our own
# maps, so just turn the check off.
Image.MAX_IMAGE_PIXELS = None


# --- settings ---

VERSION = "1.0.0"

PLAINS, SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT = (
    "plains", "sea", "lake", "swamp", "hills", "mountains", "forest", "desert")
FERTILE = "fertile"                  # not a terrain: plains whose soil isn't too salty to farm
WATER = (SEA, LAKE)

# (it, en) pairs everywhere below
TERRAIN_NAMES = {PLAINS: ("pianura", "plains"), SEA: ("mare", "sea"), LAKE: ("lago", "lake"),
                 SWAMP: ("palude", "swamp"),
                 HILLS: ("colline", "hills"), MOUNTAINS: ("montagne", "mountains"),
                 FOREST: ("foresta", "forest"), DESERT: ("deserto", "desert")}

# (it option, en option, terrain, label)
TERRAIN_OPTIONS = [
    ("pianura", "plains", PLAINS, ("Pianura", "Plains")),
    ("mare", "sea", SEA, ("Mare", "Sea")),
    ("laghi", "lakes", LAKE, ("Laghi", "Lakes")),
    ("paludi", "swamps", SWAMP, ("Paludi", "Swamps")),
    ("colline", "hills", HILLS, ("Colline", "Hills")),
    ("montagne", "mountains", MOUNTAINS, ("Montagne", "Mountains")),
    ("foreste", "forests", FOREST, ("Foreste", "Forests")),
    ("deserti", "deserts", DESERT, ("Deserti", "Deserts")),
]
DEFAULT_PERCENTAGES = {PLAINS: 27, SEA: 15, LAKE: 3, SWAMP: 3, HILLS: 15,
                       MOUNTAINS: 10, FOREST: 20, DESERT: 5}

CITY, FORTRESS, DUNGEON = "city", "fortress", "dungeon"
SITE_NAMES = {CITY: ("Città", "City"), FORTRESS: ("Fortezza", "Fortress"), DUNGEON: ("Dungeon", "Dungeon")}

ORIENTATION_FROM_USER = {"auto": "auto", "verticale": "portrait", "orizzontale": "landscape",
                         "portrait": "portrait", "landscape": "landscape"}
ORIENTATION_NAMES = {"portrait": ("verticale", "portrait"), "landscape": ("orizzontale", "landscape")}
SIZE_FROM_USER = {"auto": "auto", "piccola": "small", "grande": "large", "small": "small", "large": "large"}

DPI = 600
MARGIN_MM = 10.0
MAX_CHAR_MM = 3.2           # cap on A4; bigger sheets scale it up
READABLE_CHAR_MM = 1.35     # used by the auto grid
GOOD_CHAR_MM = 1.3          # readable
SMALL_CHAR_MM = 1.1         # too small below this
# portrait w, h in mm, smallest first (suggest_paper relies on the order)
PAPERS = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594)}

# iTXt key in the PNG
SETTINGS_KEY = "wyrmhex-settings"
# from when the project was called hexcrawl / HexWyrm
OLD_SETTINGS_KEYS = ("hexwyrm-settings", "hexcrawl-settings", "hexcrawl-impostazioni")

# (fancy, plain fallback, weight). Spaces are there to leave some air in the hex.
# Fancy ones are CP437, as in Dwarf Fortress.
TERRAIN_GLYPHS = {
    PLAINS:    [],
    HILLS:     [("∩", "n", 5), ("n", "m", 2), (" ", " ", 3), ("'", "'", 1)],
    MOUNTAINS: [("▲", "^", 5), ("^", "A", 3), (" ", " ", 1)],
    FOREST:    [("♣", "T", 5), ("♠", "Y", 3), (" ", " ", 1)],
    DESERT:    [("░", ".", 3), ("·", ":", 3), (":", ".", 1), (" ", " ", 2)],
    LAKE:      [("≈", "~", 6), (" ", " ", 1)],        # ~ is too faint on paper
    # DF swamp: reeds and grass tufts
    SWAMP:     [("⌠", '"', 4), ('"', ",", 4), (" ", " ", 2)],
    # sprouts, sparse: farmland is still open plains
    FERTILE:   [("τ", "v", 2), (" ", " ", 5)],
}
SITE_GLYPHS = {CITY: ("⌂", "C"), FORTRESS: ("Ω", "F"), DUNGEON: (">", ">")}

# box-drawing char by the directions a river square connects to (l r u d)
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
OPPOSITE = {"l": "r", "r": "l", "u": "d", "d": "u"}
SEA_GRAY = 205              # 0 black, 255 white

# Colour maps. Keys are canvas tags: terrains, sites, and a few extras. Anything
# without its own colour is drawn in "ink". The black-and-white map is just one
# more palette, in grayscale, where everything is ink.
def bg(terrain):
    """Palette key of a terrain's hex background. Only palettes that have one fill it."""
    return "bg:" + terrain


# the sea is filled hex by hex: painted letter square by letter square, it left
# white notches along the coast and squares sticking out at the map edge
MONO = {"mode": "L", "paper": 255, "ink": 0, "sea": SEA_GRAY, bg(SEA): SEA_GRAY}


def has_backgrounds(p):
    """Coloured land hexes (not just the sea): the legend then shows swatches."""
    return bg(PLAINS) in palette_for(p)


# Swamps are a magenta-leaning purple: olive got lost among the forests, and a
# bluer purple would clash with the fortresses, also for colour-blind eyes.
PALETTES = {
    "white": {"mode": "RGB", "paper": (255, 255, 255), "ink": (25, 25, 25),
              "border": (100, 100, 100), "sea": (180, 211, 236), "sea_line": (115, 155, 195),
              LAKE: (30, 100, 200), "river": (25, 95, 205), SWAMP: (118, 30, 95),
              FOREST: (25, 125, 45), HILLS: (130, 85, 25), MOUNTAINS: (105, 90, 80),
              DESERT: (180, 125, 25), CITY: (190, 35, 35), FORTRESS: (105, 60, 160),
              DUNGEON: (25, 25, 25),
              # hex backgrounds, light enough for the symbols on top (hills brown and
              # desert ochre above are darker than on black for the yellows); lakes get
              # the sea's blue, their ≈ tells them apart
              bg(PLAINS): (222, 239, 200), bg(SEA): (180, 211, 236), bg(LAKE): (180, 211, 236), bg(FOREST): (168, 208, 150), bg(SWAMP): (250, 208, 226),
              bg(DESERT): (252, 238, 160), bg(HILLS): (232, 200, 100), bg(MOUNTAINS): (228, 210, 180)},
    "black": {"mode": "RGB", "paper": (12, 12, 16), "ink": (230, 230, 225),
              "border": (110, 110, 115), "sea": (18, 42, 82), "sea_line": (60, 100, 150),
              LAKE: (80, 150, 255), "river": (90, 160, 255), SWAMP: (195, 105, 165),
              FOREST: (60, 190, 80), HILLS: (215, 165, 80), MOUNTAINS: (195, 180, 165),
              DESERT: (235, 195, 95), CITY: (235, 75, 65), FORTRESS: (170, 120, 230),
              DUNGEON: (230, 230, 225),
              # sea hexes as hexagons; hex codes go straight on them, no box
              bg(SEA): (18, 42, 82)},
}
BACKGROUND_FROM_USER = {"bianco": "white", "nero": "black", "white": "white", "black": "black"}


def palette_for(p):
    return PALETTES[p.get("background", "white")] if p.get("colors") else MONO

# monospace (regular, bold), first one found wins. (path, index) for .ttc
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
    return value / 25.4 * DPI


# --- language ---
# Everything the user reads is (it, en). LANG is set once at startup,
# from the first question or from --lingua/--language.
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
    "mode_new": ("creare una mappa nuova", "make a new map"),
    "mode_edit": ("modificare una mappa, a partire dal suo seme", "edit a map, starting from its seed"),
    "mode_rebuild": ("riprodurre una mappa già fatta, a partire dal suo seme",
                     "rebuild a map you already made, from its seed"),
    "choice": ("Scelta", "Choice"),
    "menu_keys": ("↑ ↓ per scegliere   ·   Invio per confermare   ·   oppure il numero",
                  "↑ ↓ to choose   ·   Enter to confirm   ·   or the number"),
    "menu_keys_ascii": ("su/giu per scegliere - Invio per confermare - oppure il numero",
                        "up/down to choose - Enter to confirm - or the number"),
    "values_how": ("\n  Città, fortezze, dungeon, percentuali di terreno e fiumi:",
                   "\n  Cities, fortresses, dungeons, terrain percentages and rivers:"),
    "values_manual": ("li scelgo io", "I'll choose them"),
    "values_random": ("a caso", "random"),
    "ask_seed": ("  Seme della mappa da rifare (è anche il nome della sua cartella, es. {example}): ",
                 "  Seed of the map to rebuild (it is also the name of its folder, e.g. {example}): "),
    "seed_invalid": ("    Questo seme non è valido: controlla di averlo scritto bene (es. {example}).",
                     "    This seed is not valid: check that you typed it correctly (e.g. {example})."),
    "found_seed": ("\n  Mappa del seme {seed}:\n    {desc}", "\n  Map of seed {seed}:\n    {desc}"),
    "found_settings": ("\n  Trovate le impostazioni della mappa {seed}:\n    {desc}",
                       "\n  Found the settings of map {seed}:\n    {desc}"),
    "use_settings": ("  Uso queste impostazioni? (S/n): ", "  Use these settings? (Y/n): "),
    "no_settings": ("\n  Non trovo {seed}_nonumber.png (né in {folder}, né nella cartella corrente), "
                    "quindi non conosco le impostazioni originali.",
                    "\n  Cannot find {seed}_nonumber.png (neither in {folder} nor in the current folder), "
                    "so the original settings are unknown."),
    "same_settings": ("  È un seme numerico di una versione precedente, che da solo non basta: "
                      "inserisci le STESSE impostazioni della mappa originale.\n",
                      "  This is a number seed from an earlier version, which is not enough on its own: "
                      "enter the SAME settings as the original map.\n"),
    "colors_how": ("\n  Colori:", "\n  Colours:"),
    "colors_mono": ("bianco e nero, per la stampa", "black and white, for printing"),
    "colors_color": ("a colori", "colour"),
    "background_how": ("\n  Sfondo:", "\n  Background:"),
    "background_white": ("bianco", "white"),
    "background_black": ("nero", "black"),
    "err_background": ("--sfondo funziona solo insieme a --colori", "--background only works together with --colors"),
    "h_colors": ("mappa a colori invece che in bianco e nero", "colour map instead of black and white"),
    "h_background": ("sfondo della mappa a colori: bianco (default) o nero", "background of the colour map: white (default) or black"),
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
    "miles": ("{n} miglia", "{n} miles"),
    "mile": ("{n} miglio", "{n} mile"),
    "scale_how": ("\n  Quante miglia copre ogni esagono?", "\n  How many miles does each hex cover?"),
    "ask_rename": ("  Titolo attuale: {title}. Vuoi rinominare la mappa? (s/N): ",
                   "  Current title: {title}. Rename the map? (y/N): "),
    "ask_new_title": ("  Nuovo titolo [{default}]: ", "  New title [{default}]: "),
    "ask_rescale": ("  Scala attuale: 1 esagono = {scale}. Vuoi cambiarla? (s/N): ",
                    "  Current scale: 1 hex = {scale}. Change it? (y/N): "),
    "scale_keep": ("lascia com'è ({scale})", "keep it as it is ({scale})"),
    "scale_other": ("altro, lo scrivo io", "other, I'll type it"),
    "ask_custom_scale": ("  Miglia per esagono (un numero, oppure un testo come \"5 km\"): ",
                         "  Miles per hex (a number, or a text like \"5 km\"): "),
    "q_paper": ("  Formato di stampa per le due mappe (A4, A3, A2) [{default}]: ",
                "  Print format for both maps (A4, A3, A2) [{default}]: "),
    "paper_menu_option": ("{paper} {o}, {hexes} {hex_mm:.0f} mm, caratteri {mm:.2f} mm ({v}){note}",
                          "{paper} {o}, {hexes} {hex_mm:.0f} mm, letters {mm:.2f} mm ({v}){note}"),
    "suggested_short": ("  ← consigliato", "  ← suggested"),
    "q_paper_menu": ("Formato di stampa per le due mappe (la scelta finale è tua):",
                     "Print format for both maps (the final choice is yours):"),
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
    "err_sites_range": ("Il numero di {name} deve essere tra 0 e {max}.", "The number of {name} must be between 0 and {max}."),
    "err_rivers_range": ("Il numero di fiumi deve essere tra -1 (automatico) e {max}.",
                         "The number of rivers must be between -1 (automatic) and {max}."),
    "err_pct_whole": ("Le percentuali di terreno devono essere numeri interi (ricevuto {value:g}).",
                      "The terrain percentages must be whole numbers (got {value:g})."),
    "err_bad_seed": ("'{seed}' non è un seme valido: controlla di averlo scritto bene (es. {example})",
                     "'{seed}' is not a valid seed: check that you typed it correctly (e.g. {example})"),
    "err_seed_number": ("il numero dopo --seme deve essere tra 0 e {max}; per rifare una mappa scrivi il suo "
                        "seme completo (es. {example})",
                        "the number after --seed must be between 0 and {max}; to rebuild a map, type its "
                        "full seed (e.g. {example})"),
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
    "info_random": ("Siti, terreni e fiumi scelti a caso", "Sites, terrains and rivers picked at random"),
    "step_validate": ("Lettura e validazione dei parametri", "Reading and checking the settings"),
    "info_grid": ("Griglia: {c} x {r} = {n} esagoni", "Grid: {c} x {r} = {n} hexes"),
    "info_terrains": ("Terreni: {list}", "Terrains: {list}"),
    "info_pct_sum": ("Somma percentuali: {t:g}% (≤ 100%: OK)", "Percentages add up to {t:g}% (≤ 100%: OK)"),
    "info_pct_rest": ("Il {r:g}% non assegnato viene aggiunto alla pianura", "The unassigned {r:g}% is added to plains"),
    "info_sites": ("Siti richiesti: {c} città, {f} fortezze, {d} dungeon",
                   "Sites wanted: {c} cities, {f} fortresses, {d} dungeons"),
    "info_auto_grid": ("Griglia automatica: {c} x {r} esagoni riempiono un A4 {o} (caratteri da {mm} mm)",
                       "Automatic grid: {c} x {r} hexes fill an A4 {o} sheet ({mm} mm letters)"),
    "info_seed": ("Seme: {s}  (basta questo per rifare la mappa: rispondi 2 a \"Cosa vuoi fare?\", "
                  "oppure usa --riproduci {s})",
                  "Seed: {s}  (this is all you need to rebuild the map: answer 2 to \"What do you want to do?\", "
                  "or use --reproduce {s})"),
    "warn_old_seed": ("Le impostazioni di questa mappa di una versione precedente non entrano in un seme: "
                      "resta il seme numerico {s}",
                      "The settings of this map from an earlier version do not fit in a seed: "
                      "it keeps the number seed {s}"),
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
    "info_archipelago": ("Mare oltre metà mappa: {n} esagoni allagati, terre sparse in un arcipelago (isole: {i})",
                         "Sea over half the map: {n} hexes flooded, land scattered in an archipelago "
                         "(islands: {i})"),
    "info_peninsulas": ("Mare oltre metà mappa: {n} esagoni allagati, terraferma a {side} con penisole e baie, "
                        "isole al largo: {i}",
                        "Sea over half the map: {n} hexes flooded, mainland to the {side} with peninsulas "
                        "and bays, islands offshore: {i}"),
    "info_sea": ("Mare partito da {h}, {n} esagoni allagati", "Sea started at {h}, {n} hexes flooded"),
    "step_lakes": ("Laghi: bacini interni scavati nelle conche", "Lakes: inland basins dug in the dips"),
    "info_lakes": ("{n} laghi per {h} esagoni", "{n} lakes, {h} hexes"),
    "warn_lakes": ("Spazio insufficiente: {n} esagoni di lago diventano pianura",
                   "Not enough room: {n} lake hexes become plains"),
    "step_relief": ("Rilievi: gli esagoni più alti diventano montagne, i successivi colline",
                    "Relief: the highest hexes become mountains, the next ones hills"),
    "info_relief": ("{m} montagne, {h} colline", "{m} mountains, {h} hills"),
    "step_wetness": ("Umidità: paludi nelle zone basse vicino all'acqua, foreste nelle zone umide, "
                     "deserti in quelle aride, il resto pianura",
                     "Wetness: swamps in low ground near water, forests where it is wet, "
                     "deserts where it is dry, plains elsewhere"),
    "info_wind": ("Vento prevalente da {wind}: piove sui versanti rivolti a {wind}, "
                  "a {lee} dei rilievi resta secco",
                  "Prevailing wind from the {wind}: rain on the slopes facing {wind}, "
                  "dry land {lee} of the high ground"),
    "info_salt": ("Salinità: {f} pianure su {p} abbastanza dolci da coltivare; paludi: {s} salmastre "
                  "lungo la costa, {w} d'acqua dolce",
                  "Salinity: {f} of {p} plains fresh enough to farm; swamps: {s} salt marshes on the coast, "
                  "{w} freshwater"),
    "info_result": ("Risultato: {list}", "Result: {list}"),
    "step_rivers": ("Fiumi: dalle sorgenti in quota verso il basso fino a mare, lago o bordo",
                    "Rivers: from high springs downhill to the sea, a lake or the edge"),
    "river_water": ("sfocia in acqua", "flows into water"),
    "river_join": ("confluisce in un altro fiume", "joins another river"),
    "river_edge": ("esce dalla mappa", "leaves the map"),
    "river_stop": ("finisce in {h} senza arrivare all'acqua", "ends at {h} without reaching water"),
    "info_river": ("Fiume {i}: sorgente {h}, {n} esagoni, {where}", "River {i}: spring {h}, {n} hexes, {where}"),
    "warn_rivers": ("Tracciati {d} fiumi su {n} richiesti (percorsi validi insufficienti)",
                    "Drew {d} of {n} rivers wanted (not enough valid paths)"),
    "step_sites": ("Insediamenti e dungeon: scelta pesata per terreno, con distanze minime",
                   "Settlements and dungeons: chosen by terrain, with minimum distances"),
    "info_site_kind": ("{name}: {n} su {n}, distanza minima tra loro {d} esagoni",
                       "{name}: {n} of {n}, at least {d} hexes apart"),
    "relaxed": (" (rilassata per mancanza di spazio)", " (reduced for lack of room)"),
    # editor
    "ed_header": ("\nMODIFICA DELLA MAPPA", "\nEDITING THE MAP"),
    "ed_columns": (("Esagono", "Terreno", "Dungeon", "Città", "Fiume", "Direzione", "Fortezza"),
                   ("Hex", "Terrain", "Dungeon", "City", "River", "Direction", "Fortress")),
    "ed_yes": ("sì", "yes"),
    "ed_dirs": (("nord", "nord-est", "sud-est", "sud", "sud-ovest", "nord-ovest"),
                ("north", "north-east", "south-east", "south", "south-west", "north-west")),
    "ed_resume_png": ("  Ho ritrovato le modifiche nell'immagine della mappa modificata. Le riprendo? (S/n): ",
                      "  The edits are inside the edited map's picture. Pick them up again? (Y/n): "),
    "ed_shown": ("\n  Esagoni con siti, fiumi o modifiche{near} ({n} su {total}). T = tabella completa.",
                 "\n  Hexes with sites, rivers or changes{near} ({n} of {total}). T = full table."),
    "ed_near": (", più i dintorni di {h}", ", plus the hexes around {h}"),
    "ed_next_undo": ("annullare l'ultima modifica", "undo the last change"),
    "ed_next_quit": ("uscire senza generare la mappa (le modifiche restano salvate)",
                     "quit without making the map (the changes stay saved)"),
    "ed_undone": ("    Annullata l'ultima modifica.", "    Last change undone."),
    "ed_nothing_to_undo": ("    Non c'è nessuna modifica da annullare.", "    There's nothing to undo."),
    "ed_quit": ("\n  Le modifiche sono salvate in {path}: le ritrovi scegliendo di nuovo 3 con questo seme.",
                "\n  The changes are saved in {path}: you'll find them again by choosing 3 with this seed."),
    "ed_quit_nothing": ("\n  Esco senza modifiche.", "\n  Quitting, nothing changed."),
    "ed_no_change": ("    Nessuna modifica.", "    Nothing changed."),
    "ed_river_cut_end": ("accorciarlo: il fiume finisce qui", "shorten it: the river ends here"),
    "ed_river_cut_start": ("accorciarlo: il fiume nasce qui", "shorten it: the river springs here"),
    "ed_too_short": ("    Resterebbe un fiume troppo corto: se vuoi, toglilo tutto.",
                     "    The river would be too short: remove it altogether if you want."),
    "ed_did_cut_end": ("il fiume ora finisce in {h}{how}", "the river now ends at {h}{how}"),
    "ed_did_cut_start": ("il fiume ora nasce in {h}", "the river now springs at {h}"),
    "ed_into_water": (", sfociando in acqua", ", flowing into the water"),
    "ed_off_map": (", uscendo dalla mappa", ", leaving the map"),
    "info_has_edits": ("Questa mappa ha anche una versione modificata: per rifare quella, usa "
                       "--riproduci {s} --modificata, oppure scegli 3 (\"modificare una mappa\") con questo seme",
                       "This map also has an edited version: to make that one, use "
                       "--reproduce {s} --edited, or choose 3 (\"edit a map\") with this seed"),
    "ed_bad_edits": ("    Le modifiche salvate sono illeggibili: riparto dalla mappa originale.",
                     "    The saved edits can't be read: starting from the original map."),
    "ed_resume": ("  Questa mappa ha già delle modifiche salvate. Le riprendo? (S/n): ",
                  "  This map already has saved edits. Pick them up again? (Y/n): "),
    "ed_ask_hex": ("  Esagono da modificare (colonna.riga, es. 03.07; T = tabella completa, A = annulla, E = esci): ",
                   "  Hex to edit (column.row, e.g. 03.07; T = full table, U = undo, Q = quit): "),
    "ed_bad_hex": ("    Esagono non valido: scrivi colonna.riga, es. 03.07 (la mappa va da 01.01 a {last}).",
                   "    Not a valid hex: type column.row, e.g. 03.07 (the map goes from 01.01 to {last})."),
    "ed_hex_is": ("\n  Esagono {h}: {desc}", "\n  Hex {h}: {desc}"),
    "ed_what": ("  Cosa vuoi fare?", "  What do you want to do?"),
    "ed_terrain": ("cambiare il tipo di terreno", "change the terrain"),
    "ed_add": ("aggiungere {what}", "add {what}"),
    "ed_remove": ("togliere {what}", "remove {what}"),
    "ed_a_dungeon": ("un dungeon", "a dungeon"), "ed_the_dungeon": ("il dungeon", "the dungeon"),
    "ed_a_city": ("una città", "a city"), "ed_the_city": ("la città", "the city"),
    "ed_a_fortress": ("una fortezza", "a fortress"), "ed_the_fortress": ("la fortezza", "the fortress"),
    "ed_add_river": ("aggiungere un fiume che nasce qui", "add a river that springs here"),
    "ed_river_piece": ("togliere o spostare il fiume", "remove or move the river"),
    "ed_nothing": ("niente, scegli un altro esagono", "nothing, pick another hex"),
    "ed_which_terrain": ("  Nuovo terreno:", "  New terrain:"),
    "ed_river_how": ("  Il fiume:", "  The river:"),
    "ed_river_all": ("togliere tutto il fiume", "remove the whole river"),
    "ed_river_move": ("spostare questo tratto di un esagono", "move this stretch by one hex"),
    "ed_no_dirs": ("    Da qui il fiume non ha altre direzioni in cui spostarsi.",
                   "    There's no other direction to move the river to from here."),
    "ed_which_dir": ("  In quale direzione?", "  Which way?"),
    "ed_next": ("\n  E adesso?", "\n  What next?"),
    "ed_next_more": ("modificare un altro esagono", "edit another hex"),
    "ed_next_go": ("generare la mappa con le modifiche", "make the map with the changes"),
    "ed_done": ("    Fatto: {what}.", "    Done: {what}."),
    "ed_did_terrain": ("{h} ora è {t}", "{h} is now {t}"),
    "ed_did_add": ("aggiunto {what} in {h}", "added {what} at {h}"),
    "ed_did_replace": ("{h}: {old} → {what}", "{h}: {old} → {what}"),
    "ed_did_remove": ("tolto {what} da {h}", "removed {what} from {h}"),
    "ed_did_river_add": ("nuovo fiume da {h}, lungo {n} esagoni: {how}", "new river from {h}, {n} hexes long: {how}"),
    "ed_did_river_del": ("tolto il fiume che passava da {h}", "removed the river through {h}"),
    "ed_did_river_move": ("il fiume ora passa da {h} invece che da {old}", "the river now goes through {h} instead of {old}"),
    "ed_lost_site": ("tolto {what} da {h}: sull'acqua non può stare", "removed {what} from {h}: it can't stand on water"),
    "ed_cut_river": ("il fiume che passava da {h} ora finisce lì nell'acqua", "the river through {h} now ends there in the water"),
    "ed_no_water_site": ("    Su mare e laghi non si possono mettere siti.", "    Sites can't go on sea or lakes."),
    "ed_no_water_river": ("    Un fiume non può nascere nell'acqua.", "    A river can't spring in the water."),
    "ed_no_river_path": ("    Da qui il fiume non trova una strada verso il basso.",
                         "    From here the river finds no way downhill."),
    "ed_try_manual": ("  Lo tracci tu, esagono per esagono? (S/n): ", "  Trace it yourself, hex by hex? (Y/n): "),
    "ed_river_way": ("  Come lo tracciamo?", "  How should it run?"),
    "ed_river_auto": ("lo traccia il programma, seguendo la discesa", "the program traces it, downhill"),
    "ed_river_manual": ("lo traccio io, esagono per esagono", "I'll trace it myself, hex by hex"),
    "ed_ask_path": ("  Esagoni del fiume dopo {h}, in ordine e separati da spazi (es. {example}).\n"
                    "  Per farlo sfociare, scrivi per ultimo l'esagono di mare o di lago; per farlo confluire, "
                    "un esagono di un altro fiume.\n  Invio = annulla: ",
                    "  The river's hexes after {h}, in order, separated by spaces (e.g. {example}).\n"
                    "  To make it flow into the water, end with a sea or lake hex; to make it join another river, "
                    "end with a hex of that river.\n  Enter = cancel: "),
    "ed_ask_path_again": ("  Esagoni del fiume dopo {h} (Invio = annulla): ", "  The river's hexes after {h} (Enter = cancel): "),
    "ed_path_bad_hex": ("    '{x}' non è un esagono della mappa.", "    '{x}' is not a hex of this map."),
    "ed_path_not_near": ("    {a} e {b} non sono vicini: ogni esagono deve toccare quello prima.",
                         "    {a} and {b} are not neighbours: every hex must touch the one before."),
    "ed_path_twice": ("    {h} c'è due volte.", "    {h} is there twice."),
    "ed_path_after_end": ("    Il fiume finisce già in {h}: dopo non può continuare.",
                          "    The river already ends at {h}: it can't go on after that."),
    "ed_path_short": ("    Serve almeno un esagono di terra dopo {h}.", "    It needs at least one land hex after {h}."),
    "ed_end_note": ("    Nota: il fiume che nasce in {h} ora {how}.", "    Note: the river that springs at {h} now {how}."),
    "ed_into_river": (", confluendo in un altro fiume", ", joining another river"),
    "ed_no_water_end": (", senza arrivare all'acqua", ", without reaching water"),
    "ed_dropped": ("    {n} voci delle modifiche salvate non erano valide e le ho saltate.",
                   "    {n} entries of the saved edits were not valid and were skipped."),
    "ed_moved_bad": ("  Il file {path} non si legge (forse è stato cambiato a mano): l'ho rinominato {new}, "
                     "così non va perso.",
                     "  The file {path} can't be read (maybe it was changed by hand): I renamed it {new}, "
                     "so it isn't lost."),
    "ed_start_over": ("  Riparto dalla mappa originale.", "  Starting from the original map."),
    "ask_edit_now": ("\n  Vuoi modificare questa mappa adesso? (s/N): ", "\n  Do you want to edit this map now? (y/N): "),
    "ed_no_move": ("    Non posso spostare il fiume lì: {why}.", "    Can't move the river there: {why}."),
    "ed_why_water": ("c'è acqua", "there's water"),
    "ed_why_river": ("c'è già un fiume", "there's already a river"),
    "ed_why_break": ("il fiume si spezzerebbe", "the river would break apart"),
    "ed_edited": ("(modificata)", "(edited)"),
    # the editor drawn in the terminal
    "ve_title": (" WyrmHex v{v} · Editor ", " WyrmHex v{v} · Editor "),
    "ve_seed": ("seme {s}", "seed {s}"),
    "ve_hex": ("Esagono {h}", "Hex {h}"),
    "ve_rows": (("Terreno", "Sito", "Nome", "Fiume", "Quota"), ("Terrain", "Site", "Name", "River", "Height")),
    "ve_farmland": ("pianura coltivabile", "plains, farmland"),
    "ve_river_dir": ("sì, verso {d}", "yes, flows {d}"),
    "ve_no": ("no", "no"),
    "ve_actions": ("Azioni", "Actions"),
    "ve_enter": ("Invio  tutte le azioni", "Enter  all the actions"),
    "ve_keys": ((("T", "terreno"), ("C", "città"), ("F", "fortezza"), ("D", "dungeon"), ("R", "fiume"),
                 ("N", "nome"), ("Z", "annulla"), ("?", "aiuto"), ("S", "genera mappa"), ("Q", "esci")),
                (("T", "terrain"), ("C", "city"), ("F", "fortress"), ("D", "dungeon"), ("R", "river"),
                 ("N", "name"), ("Z", "undo"), ("?", "help"), ("S", "make the map"), ("Q", "quit"))),
    "ve_changes": ("Modifiche: {n}", "Changes: {n}"),
    "ve_view": ("Mappa {c}×{r} esagoni · in vista colonne {a}–{b}, righe {d}–{e}",
                "Map {c}×{r} hexes · in view columns {a}–{b}, rows {d}–{e}"),
    "ve_bar": (" ←↑↓→ o clic: muovi   Invio: azioni   S: genera la mappa   Q: esci   ?: aiuto ",
               " ←↑↓→ or click: move   Enter: actions   S: make the map   Q: quit   ?: help "),
    "ve_trace_bar": (" ←↑↓→ muovi   Invio o clic: aggiungi   Backspace: togli l'ultimo   F: fine   Esc: annulla ",
                     " ←↑↓→ move   Enter or click: add   Backspace: drop the last   F: done   Esc: cancel "),
    "ve_popup_keys": ("↑ ↓ scegli · Invio conferma · Esc annulla", "↑ ↓ choose · Enter confirms · Esc cancels"),
    "ve_text_keys": ("Invio conferma · Esc annulla · vuoto = nessun nome",
                     "Enter confirms · Esc cancels · empty = no name"),
    "ve_yes": ("sì", "yes"),
    "ve_quit_q": ("Uscire senza generare la mappa? Le modifiche restano salvate.",
                  "Quit without making the map? The changes stay saved."),
    "ve_quit_no": ("no, continuo a modificare", "no, keep editing"),
    "ve_quit_yes": ("sì, esci", "yes, quit"),
    "ve_name_title": ("{site} in {h}: nome (massimo {n} caratteri)", "{site} at {h}: name (up to {n} characters)"),
    "ve_no_site": ("Qui non c'è un sito: i nomi vanno a città, fortezze e dungeon.",
                   "There's no site here: names go to cities, fortresses and dungeons."),
    "ve_did_name": ("{h} ora si chiama \"{name}\"", "{h} is now called \"{name}\""),
    "ve_did_unname": ("tolto il nome in {h}", "removed the name at {h}"),
    "ve_trace_title": ("Nuovo fiume da {h}", "New river from {h}"),
    "ve_trace_help": ("Porta il cursore su un esagono vicino all'ultimo e premi Invio: il fiume ci passa. "
                      "Un esagono di mare, di lago o di un altro fiume lo chiude. F lo finisce dov'è.",
                      "Move the cursor to a hex next to the last one and press Enter: the river goes "
                      "through it. A sea, lake or other river's hex ends it. F ends it where it is."),
    "ve_trace_path": ("Percorso ({n} esagoni):", "Path ({n} hexes):"),
    "ve_trace_cancel": ("Nuovo fiume annullato.", "New river cancelled."),
    "ve_help_title": ("Aiuto", "Help"),
    "ve_help": (("←↑↓→, clic   sposta il cursore",
                 "Invio        tutte le azioni sull'esagono",
                 "T            cambia il terreno",
                 "C F D        mette o toglie città, fortezza, dungeon",
                 "N            dà un nome al sito, o lo cambia",
                 "R            nuovo fiume da qui, o togli e sposta",
                 "             quello che c'è",
                 "Z            annulla l'ultima modifica",
                 "S            genera la mappa con le modifiche",
                 "Q            esci: le modifiche restano salvate",
                 "",
                 "Ogni modifica è salvata subito in {file}."),
                ("←↑↓→, click  move the cursor",
                 "Enter        all the actions on the hex",
                 "T            change the terrain",
                 "C F D        add or remove a city, fortress, dungeon",
                 "N            name the site, or rename it",
                 "R            new river from here, or remove and",
                 "             move the one that's there",
                 "Z            undo the last change",
                 "S            make the map with the changes",
                 "Q            quit: the changes stay saved",
                 "",
                 "Every change is saved at once in {file}.")),
    "ve_any_key": ("un tasto qualsiasi per chiudere", "any key to close"),
    "ve_too_small": ("  Il terminale è troppo piccolo per l'editor sulla mappa (serve almeno {w}×{h}): "
                     "uso quello a domande.",
                     "  The terminal is too small for the editor on the map (it needs at least {w}×{h}): "
                     "using the one with questions."),
    "ve_log": ("  Nell'editor:", "  In the editor:"),
    "info_edits": ("Modifiche salvate in {path}", "Edits saved in {path}"),
    "info_edits_applied": ("Modifiche prese da {path}", "Edits taken from {path}"),
    "warn_json_broken": ("{path} non si legge: uso le modifiche salvate nella mappa modificata",
                         "{path} can't be read: using the edits saved in the edited map"),
    "warn_edits_dropped": ("{n} voci delle modifiche salvate non erano valide e sono state saltate",
                           "{n} entries of the saved edits were not valid and were skipped"),
    "err_no_edits": ("\nERRORE: la mappa {seed} non ha modifiche salvate (cercate in {folder}). "
                     "Per farne, scegli 3 (\"modificare una mappa\") avviando il programma senza opzioni.",
                     "\nERROR: map {seed} has no saved edits (looked in {folder}). "
                     "To make some, choose 3 (\"edit a map\") starting the program without options."),
    "err_bad_edits": ("\nERRORE: le modifiche salvate in {path} non si leggono: correggi il file, oppure riapri "
                      "la mappa nell'editor (scelta 3) per ricominciare.",
                      "\nERROR: the edits saved in {path} can't be read: fix the file, or open the map "
                      "in the editor again (choice 3) to start over."),
    "err_edited_needs_seed": ("--modificata funziona solo insieme a --riproduci, o a --seme con un seme completo",
                              "--edited only works together with --reproduce, or --seed with a full seed"),
    "sites_header": ("\nELENCO DEI SITI (codice esagono)", "\nLIST OF SITES (hex code)"),
    "labels_intro": ("\n  Nomi dei siti: per ogni città, fortezza e dungeon puoi scrivere un nome, che compare "
                     "sulla mappa.\n  Rispondi s e poi scrivi il nome, oppure scrivilo subito; "
                     "premi Invio per lasciarlo senza nome.",
                     "\n  Site names: for every city, fortress and dungeon you can type a name, which shows on "
                     "the map.\n  Answer y and then type the name, or just type it straight away; "
                     "press Enter to leave it without one."),
    "ask_label": ("  {site} {i}, esagono {h} ({terrain}). Vuoi dare un nome? (s/N): ",
                  "  {site} {i}, hex {h} ({terrain}). Give it a name? (y/N): "),
    "ask_relabel": ("  {site} {i}, esagono {h} ({terrain}), si chiama \"{name}\". Vuoi cambiare il nome? (s/N): ",
                    "  {site} {i}, hex {h} ({terrain}), is called \"{name}\". Change the name? (y/N): "),
    "q_label": ("    Nome (massimo {n} caratteri; vuoto = nessun nome): ",
                "    Name (up to {n} characters; empty = no name): "),
    "label_taken": ("    Nome: \"{name}\"", "    Name: \"{name}\""),
    "label_cut": ("    Troppo lungo: diventa \"{name}\"", "    Too long: it becomes \"{name}\""),
    "ask_labels_again": ("  Vuoi dare o cambiare i nomi di città, fortezze e dungeon? (s/N): ",
                         "  Do you want to give or change the names of cities, fortresses and dungeons? (y/N): "),
    "info_labels": ("{n} siti con un nome", "{n} named sites"),
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
    "info_paper_intro": ("Griglia di {c} x {r} esagoni: ecco come verrebbe stampata su ogni formato "
                         "(esagono misurato da lato piatto a lato piatto)",
                         "Grid of {c} x {r} hexes: this is how it would print on each format "
                         "(hex measured from flat side to flat side)"),
    "info_paper_option": ("{paper} {o:<11} {hexes:<15} da {hex_mm:>2.0f} mm, caratteri da {mm:.2f} mm ({v}){note}",
                          "{paper} {o:<11} {hexes:<11} {hex_mm:>2.0f} mm, letters {mm:.2f} mm wide ({v}){note}"),
    "paper_choice": ("  La scelta finale è tua: premi Invio per il formato consigliato, oppure scrivine un altro.",
                     "  The final choice is yours: press Enter for the suggested format, or type another one."),
    "subtitle": ("1 esagono = {scale}  {dot}  {c}{x}{r} esagoni  {dot}  seme {seed}",
                 "1 hex = {scale}  {dot}  {c}{x}{r} hexes  {dot}  seed {seed}"),
    # shorter versions of the line above, for small pages
    "subtitle_tight": ("1 esagono = {scale} {dot} {c}{x}{r} esagoni {dot} seme {seed}",
                       "1 hex = {scale} {dot} {c}{x}{r} hexes {dot} seed {seed}"),
    "subtitle_short": ("1 esagono = {scale} {dot} seme {seed}", "1 hex = {scale} {dot} seed {seed}"),
    "subtitle_seed": ("seme {seed}", "seed {seed}"),
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
    "leg_fertile": ("Pianura coltivabile", "Farmland"),
    "leg_barren": ("Pianura incolta = esagono vuoto", "Barren plains = empty hex"),
    "leg_plains_bg": ("Pianura", "Plains"),
    "leg_barren_bg": ("Pianura incolta", "Barren plains"),
    "leg_desert": ("Deserto", "Desert"),
    "leg_sea": ("Mare", "Sea"),
    "leg_lake": ("Lago", "Lake"),
    "leg_swamp": ("Palude", "Swamp"),
    "leg_river": ("Fiume", "River"),
    # command-line help
    "cli_description": ("WyrmHex: genera una mappa hexcrawl OSR in stile ASCII (Dwarf Fortress / NetHack), "
                        "PNG a 600 dpi in formato A4, A3 o A2 + TXT.",
                        "WyrmHex: makes an ASCII-style OSR hexcrawl map (Dwarf Fortress / NetHack), "
                        "600 dpi PNG on A4, A3 or A2 + TXT."),
    "mv_grid": ("BASExALTEZZA", "COLSxROWS"),
    "mv_seed": ("SEME", "SEED"),
    "mv_text": ("TESTO", "TEXT"),
    "mv_folder": ("CARTELLA", "FOLDER"),
    "h_grid": ("esagoni in base X altezza, es. 33x15; auto (default) riempie un A4",
               "hexes across X down, e.g. 33x15; auto (default) fills an A4"),
    "h_dungeons": ("numero di dungeon (0-99)", "number of dungeons (0-99)"),
    "h_cities": ("numero di città (0-99)", "number of cities (0-99)"),
    "h_fortresses": ("numero di fortezze (0-99)", "number of fortresses (0-99)"),
    "h_terrain": ("%% di {label}, numero intero (default {default})", "%% of {label}, whole number (default {default})"),
    "h_rivers": ("numero di fiumi (fino a 100), -1 = automatico", "number of rivers (up to 100), -1 = automatic"),
    "h_seed": ("un seme completo (es. {example}) rifà quella mappa; un numero da 0 a {max} fa una mappa "
               "nuova con le tue impostazioni e quel numero casuale",
               "a full seed (e.g. {example}) rebuilds that map; a number from 0 to {max} makes a new map "
               "with your settings and that random number"),
    "h_reproduce": ("rifà la mappa di questo seme; con un seme numerico di una versione precedente "
                    "legge le impostazioni dal suo PNG (in maps_generated/<seme>, o nella cartella --output)",
                    "rebuilds the map of this seed; with a number seed from an earlier version it reads "
                    "the settings from its PNG (in maps_generated/<seed>, or in the --output folder)"),
    "h_title": ("titolo della mappa", "map title"),
    "h_scale": ("miglia per esagono: 2, 6 (default), 12, 24 o un altro numero; oppure un testo libero, es. '5 km'",
                "miles per hex: 2, 6 (default), 12, 24 or any other number; or free text, e.g. '5 km'"),
    "h_paper": ("formato di stampa delle due mappe; se manca, il programma lo chiede proponendo quello "
                "consigliato (o lo usa direttamente, se non gira in un terminale)",
                "print format of the two maps; if missing, the program asks for it, offering the suggested one "
                "(or just uses it, when not running in a terminal)"),
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
    "h_random": ("città, fortezze, dungeon, percentuali di terreno e fiumi a caso "
                 "(le opzioni corrispondenti vengono ignorate)",
                 "random cities, fortresses, dungeons, terrain percentages and rivers "
                 "(the matching options are ignored)"),
    "h_edited": ("con --riproduci (o --seme con un seme completo): rifà la versione modificata della mappa, "
                 "con le modifiche salvate dall'editor",
                 "with --reproduce (or --seed with a full seed): rebuilds the edited version of the map, "
                 "with the changes saved by the editor"),
    "h_language": ("lingua dei testi: it (italiano) o en (inglese)", "language of the texts: it (Italian) or en (English)"),
}


def tr(key, **values):
    text = TEXTS[key][LANGUAGES.index(LANG)]
    return text.format(**values) if values else text


def pick(pair):
    return pair[LANGUAGES.index(LANG)]


def normalize_language(value):
    """Map "1", "it", "italiano"... to "it" (same for "en"). None if unknown."""
    value = (value or "").strip().lower()
    if value in ("1", "it", "ita", "italiano", "italian"):
        return "it"
    if value in ("2", "en", "eng", "english", "inglese"):
        return "en"
    return None


def ask_language():
    global LANG
    if menus_available():
        print()
        LANG = ("it", "en")[menu("Lingua / Language:", ["Italiano", "English"])]
        return
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
    """Peek at --lingua/--language before argparse runs, so that --help
    comes out in the right language too."""
    global LANG
    for i, arg in enumerate(argv):
        for name in ("--lingua", "--language"):
            if arg == name and i + 1 < len(argv):
                LANG = normalize_language(argv[i + 1]) or LANG
            elif arg.startswith(name + "="):
                LANG = normalize_language(arg.split("=", 1)[1]) or LANG


# --- console output ---
def bar(fraction, cells):
    full = round(max(0.0, min(1.0, fraction)) * cells)
    return "[" + "█" * full + "░" * (cells - full) + "]"


class LiveBar:
    """Progress bar that keeps redrawing the same line. Silent when stdout isn't a
    tty (e.g. redirected to a file), or the file would fill up with junk."""

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

    def __init__(self, total_steps):
        self.total_steps, self.step_number, self.start_time = total_steps, 0, time.perf_counter()

    def step(self, message):
        self.step_number += 1
        progress = bar(self.step_number / self.total_steps, self.total_steps)
        print(f"\n{progress} {self.step_number:>2}/{self.total_steps}  {message}")

    def info(self, message):
        print(f"        · {message}")

    def warn(self, message):
        print(f"        ! {message}")

    def done(self):
        print("\n" + tr("done", s=time.perf_counter() - self.start_time))


# --- hex grid ---
# Flat-top hexes, odd-q layout (odd columns pushed down half a hex), numbered
# CCRR like printed hexcrawls.
class HexGrid:
    # odd-q offsets: odd columns sit lower, so they get different neighbours
    DIRS_EVEN = ((1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1))
    DIRS_ODD = ((1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1))

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.hexes = [(c, r) for c in range(cols) for r in range(rows)]
        self._neighbours = {h: [n for n in self.all_neighbours(h) if self.inside(n)]
                            for h in self.hexes}

    def inside(self, hex_):
        return 0 <= hex_[0] < self.cols and 0 <= hex_[1] < self.rows

    def all_neighbours(self, hex_):
        """Includes the ones that fall off the map."""
        c, r = hex_
        dirs = self.DIRS_ODD if c & 1 else self.DIRS_EVEN
        return [(c + dc, r + dr) for dc, dr in dirs]

    def neighbours(self, hex_):
        return self._neighbours[hex_]

    def on_edge(self, hex_):
        return len(self._neighbours[hex_]) < 6

    @staticmethod
    def distance(a, b):
        """Hex distance, done in cube coordinates."""
        ax, az = a[0], a[1] - (a[0] - (a[0] & 1)) // 2
        bx, bz = b[0], b[1] - (b[0] - (b[0] & 1)) // 2
        return max(abs(ax - bx), abs(az - bz), abs((-ax - az) - (-bx - bz)))

    def distances_from(self, starts):
        """BFS from all of `starts` at once. Unreachable hexes stay None."""
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
    """(2, 6) -> '0307': 1-based, column first, like printed hexcrawls."""
    return f"{hex_[0] + 1:0{digits}d}{hex_[1] + 1:0{digits}d}"


# --- settings: reading and checking ---
def check_percentages(perc):
    """Error message, or None if the percentages are ok."""
    for _, _, terrain, label in TERRAIN_OPTIONS:
        if perc[terrain] < 0 or perc[terrain] > 100:
            return tr("pct_out_of_range", label=pick(label).lower(), value=perc[terrain])
    total = sum(perc.values())
    if total > 100 + 1e-9:
        detail = " + ".join(f"{pick(label).lower()} {perc[terrain]:g}" for _, _, terrain, label in TERRAIN_OPTIONS)
        return tr("pct_over_100", total=total) + f"\n         ({detail})"
    return None


# --- seeds ---
# A seed (e.g. 475T-4KM4-MY0B-JNDJ-ZYEQ-K164) packs everything that shapes the
# land: grid, sites, terrain %, rivers and the random number. Same seed, same
# map, anywhere, no PNG needed. Title/scale/paper/ascii aren't in it.
# All the fields go into one big mixed-radix integer, written in Crockford-ish
# base 32 (no I L O U), plus 2 check symbols at the end.
# v1 seeds (no swamps), v2 seeds (no wind), v3 seeds (no islands) and v4
# seeds (no salinity) still decode and give the same map as before: the
# version also picks how the land is made. Before that the seed was a plain number
# that only worked together with the settings stored in the PNG.
SEED_VERSION = 5                     # 2 = swamps, 3 = wind, 4 = islands, 5 = salinity (3-5: same fields as 2)
SEED_SYMBOLS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # no I, L, O, U: too easy to misread
SEED_LENGTH = 24
MAX_SITES = 99                       # per kind
MAX_RIVERS = 100
RANDOM_NUMBERS = 2 ** 20             # old 6-digit seeds (<= 999999) still fit
# no plains: they're whatever is left
SEED_TERRAINS = {1: (SEA, LAKE, HILLS, MOUNTAINS, FOREST, DESERT),
                 2: (SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT),
                 3: (SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT),
                 4: (SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT),
                 5: (SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT)}
SEED_CHECK_SYMBOLS = {1: 3, 2: 2, 3: 2, 4: 2, 5: 2}
# the land of v1 and v2 seeds (and of old number seeds) is made the same way
LAND_BEFORE_WIND = 2
LAND_WITH_ISLANDS = 4                # from here on, a mostly-sea map gets peninsulas and archipelagos
LAND_WITH_SALT = 5                   # from here on, salinity steers swamps, fertile plains and cities


def new_seed():
    return secrets.randbelow(RANDOM_NUMBERS)


def seed_fields(p, number, version=SEED_VERSION):
    """(value, how many values it can take) for every field packed in the seed."""
    fields = [(version, 16), (p["columns"] - 2, 79), (p["rows"] - 2, 79),
              (p["dungeons"], MAX_SITES + 1), (p["cities"], MAX_SITES + 1), (p["fortresses"], MAX_SITES + 1)]
    fields += [(p["percentages"].get(terrain, 0), 101) for terrain in SEED_TERRAINS[version]]
    fields += [(p["rivers"] + 1, MAX_RIVERS + 2), (number, RANDOM_NUMBERS)]
    return fields


def to_symbols(value, length):
    symbols = ""
    for _ in range(length):
        value, digit = divmod(value, 32)
        symbols = SEED_SYMBOLS[digit] + symbols
    return symbols


def seed_check(data, version=SEED_VERSION):
    """v2: each symbol times its position (1, 2, 3...), summed, mod 1021.
    1021 is prime and bigger than 22 * 31, so one wrong symbol, or two
    neighbours swapped, always changes it. v1 used a truncated crc32."""
    if version == 1:
        return to_symbols(zlib.crc32(data.encode()) % 32 ** 3, 3)
    total = sum((i + 1) * SEED_SYMBOLS.index(c) for i, c in enumerate(data))
    return to_symbols(total % 1021, SEED_CHECK_SYMBOLS[version])


def make_seed(p, number):
    """None if p doesn't fit in a seed (only old saved maps, e.g. sea 12.5%)."""
    version = p.get("version", SEED_VERSION)
    packed = 0
    for value, choices in seed_fields(p, number, version):
        if value != int(value) or not 0 <= value < choices:
            return None
        packed = packed * choices + int(value)
    data = to_symbols(packed, SEED_LENGTH - SEED_CHECK_SYMBOLS[version])
    code = data + seed_check(data, version)
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def read_seed(text):
    """Returns (land, number) or None. Forgives lower case, missing dashes
    and spaces, O typed for 0, I or L typed for 1."""
    code = text.strip().upper().replace("-", "").replace(" ", "")
    code = code.replace("O", "0").replace("I", "1").replace("L", "1")
    if len(code) != SEED_LENGTH or any(c not in SEED_SYMBOLS for c in code):
        return None
    for version in sorted(SEED_TERRAINS, reverse=True):
        unpacked = unpack_seed(code, version)
        if unpacked:
            return unpacked
    return None


def unpack_seed(code, version):
    split = SEED_LENGTH - SEED_CHECK_SYMBOLS[version]
    data, check = code[:split], code[split:]
    if seed_check(data, version) != check:
        return None
    packed = 0
    for c in data:
        packed = packed * 32 + SEED_SYMBOLS.index(c)
    blank = {"columns": 2, "rows": 2, "dungeons": 0, "cities": 0, "fortresses": 0, "percentages": {}, "rivers": 0}
    values = []
    for _, choices in reversed(seed_fields(blank, 0, version)):
        packed, value = divmod(packed, choices)
        values.append(value)
    if packed or values.pop() != version:
        return None
    terrains = SEED_TERRAINS[version]
    columns, rows, dungeons, cities, fortresses, *rest = [v for v in reversed(values)]
    percentages = dict(zip(terrains, rest[:len(terrains)]))
    rivers, number = rest[len(terrains)] - 1, rest[-1]
    percentages.setdefault(SWAMP, 0)
    percentages[PLAINS] = 100 - sum(percentages.values())
    # a v1 seed comes back as v2: same land, and it always has been rewritten so
    land = {"columns": columns + 2, "rows": rows + 2, "dungeons": dungeons, "cities": cities,
            "fortresses": fortresses, "rivers": rivers, "version": max(version, LAND_BEFORE_WIND),
            "percentages": {terrain: percentages[terrain] for _, _, terrain, _ in TERRAIN_OPTIONS}}
    if check_percentages(land["percentages"]) or percentages[PLAINS] < 0:
        return None
    return land, number


def example_seed():
    p = {"columns": 33, "rows": 15, "dungeons": 4, "cities": 3, "fortresses": 2,
         "percentages": dict(DEFAULT_PERCENTAGES), "rivers": -1}
    return make_seed(p, 482913)


def is_old_seed(text):
    """Before 0.0.3 the seed was just a number, like 482913."""
    return text.strip().isdigit()


def rebuild_settings(text, base):
    """Settings to rebuild seed `text`, or None if we can't.
    A new seed carries the land; title, scale and paper come from the PNG if
    it's still around. An old number seed is useless without its PNG."""
    if is_old_seed(text):
        saved = find_settings(base, int(text))
        if saved:
            saved["seed"] = int(text)
            saved.setdefault("version", LAND_BEFORE_WIND)
        return saved
    unpacked = read_seed(text)
    if unpacked is None:
        return None
    land, number = unpacked
    picture = find_settings(base, make_seed(land, number)) or {}
    settings = {key: picture[key] for key in ("title", "scale", "paper", "size", "font", "labels") if key in picture}
    settings.update(land, seed=number)
    return settings


MAPS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps_generated")


def make_maps_folder():
    """True on the very first run."""
    if os.path.isdir(MAPS_FOLDER):
        return False
    os.makedirs(MAPS_FOLDER, exist_ok=True)
    return True


def map_folder(base, seed):
    return os.path.join(base, str(seed))


def short_path(path):
    try:
        short = os.path.relpath(path)
    except ValueError:                   # different drive on Windows
        return path
    return path if short.startswith("..") else short


def output_names(base, seed, suffix=""):
    """suffix is "_edit" for an edited map, which sits next to the original."""
    folder = map_folder(base, seed)
    os.makedirs(folder, exist_ok=True)
    return (os.path.join(folder, f"{seed}{suffix}_nonumber.png"),
            os.path.join(folder, f"{seed}{suffix}_number.png"))


def upgrade_settings(data):
    """Up to the first versions the PNG kept the settings with Italian keys."""
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
    for name in (f"{seed}_nonumber.png", f"{seed}_number.png"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        try:
            # the iTXt chunk comes before IDAT, so this doesn't decode the image
            with Image.open(path) as img:
                text = next((img.info[key] for key in (SETTINGS_KEY, *OLD_SETTINGS_KEYS)
                             if key in img.info), None)
        except (OSError, AttributeError):
            continue
        if text:
            return upgrade_settings(json.loads(text))
    return None


def find_settings(base, seed):
    """Try <base>/<seed>, then maps_generated, then the current folder
    (older versions saved maps straight in there)."""
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
    """Fill in whatever a PNG from an older version doesn't have."""
    for key, value in (("ascii_only", False), ("colors", False), ("background", "white"),
                       ("size", "auto"), ("font", None), ("paper", None),
                       ("title", tr("default_title")), ("scale", tr("default_scale"))):
        p.setdefault(key, value)
    p.setdefault("labels", {})
    p["percentages"].setdefault(SWAMP, 0)
    # white-on-black was dropped in 0.0.2
    p.pop("inverted", None)
    p["orientation"] = "auto"
    # default title/scale saved in the other language -> translate it
    for key, default in (("title", "default_title"), ("scale", "default_scale")):
        if p.get(key) in TEXTS[default]:
            p[key] = tr(default)
    p["scale"] = scale_text(p["scale"])     # "12 miles" -> "12 miglia" and back
    return p


def describe_settings(p):
    perc = ", ".join(f"{pick(label).lower()} {p['percentages'][terrain]:g}%" for _, _, terrain, label in TERRAIN_OPTIONS)
    return tr("describe", cols=p["columns"], rows=p["rows"], cities=p["cities"], forts=p["fortresses"],
              dungeons=p["dungeons"], rivers=p["rivers"], perc=perc, title=p["title"])


def split_hexes(total, perc):
    """Largest remainder, so the counts always add up to `total`."""
    exact = {k: total * p / 100.0 for k, p in perc.items()}
    counts = {k: int(math.floor(v)) for k, v in exact.items()}
    left_over = total - sum(counts.values())
    for k in sorted(perc, key=lambda k: exact[k] - counts[k], reverse=True)[:left_over]:
        counts[k] += 1
    return counts


# range of each terrain before scaling everything to 100%
RANDOM_TERRAIN = {PLAINS: (10, 40), SEA: (0, 35), LAKE: (0, 8), SWAMP: (0, 8),
                  HILLS: (5, 25), MOUNTAINS: (3, 18), FOREST: (5, 35), DESERT: (0, 15)}


def random_settings(p, number):
    """Random sites, terrain % and rivers, for an already known grid size.
    Seeded from the map number, so --seed N --random is repeatable."""
    rng = random.Random(number * 31 + 7)     # not the land's rng
    raw = {t: rng.uniform(lo, hi) for t, (lo, hi) in RANDOM_TERRAIN.items()}
    total = sum(raw.values())
    counts = split_hexes(100, {t: v * 100 / total for t, v in raw.items()})
    p["percentages"] = {t: counts[t] for _, _, t, _ in TERRAIN_OPTIONS}

    hexes = p["columns"] * p["rows"]
    land = hexes - sum(n for t, n in split_hexes(hexes, p["percentages"]).items() if t in WATER)
    sites = {"cities": max(1, round(land / rng.uniform(40, 90))),
             "fortresses": round(land / rng.uniform(60, 140)),
             "dungeons": max(1, round(land / rng.uniform(25, 60)))}
    # tiny maps: drop sites until they fit on the land
    for key in ("dungeons", "fortresses", "cities", "dungeons"):
        while sum(sites.values()) > land and sites[key] > 0:
            sites[key] -= 1
    p.update({k: min(v, MAX_SITES) for k, v in sites.items()})
    p["rivers"] = -1


SCALE_PRESETS = (2, 6, 12, 24)               # miles per hex; 6 is the classic one
MILES = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(miglia|miglio|miles|mile|mi)?$", re.IGNORECASE)


def scale_text(value):
    """'12' or '12 miles' -> '12 miglia' (or '12 miles' in English). Anything
    else, like '5 km', is kept as typed."""
    m = MILES.match(value.strip())
    if not m:
        return value.strip()
    n = float(m.group(1).replace(",", "."))
    n = int(n) if n == int(n) else n
    shown = f"{n:g}".replace(".", ",") if LANG == "it" else f"{n:g}"   # 2,5 miglia / 2.5 miles
    return tr("mile" if n == 1 else "miles", n=shown)


def ask_scale(current=None):
    """current: the scale of a map being rebuilt, offered as the default."""
    presets = [scale_text(str(miles)) for miles in SCALE_PRESETS]
    options = presets + [tr("scale_other")]
    default = SCALE_PRESETS.index(6)
    if current in presets:
        default = presets.index(current)
    elif current:                    # a custom scale: offer to keep it
        options.append(tr("scale_keep", scale=current))
        default = len(options) - 1
    print()
    choice = menu(tr("scale_how"), options, default)
    if choice == len(presets) + 1:
        return current
    if choice < len(presets):
        return presets[choice]
    while True:
        answer = input(tr("ask_custom_scale")).strip()
        if answer:
            return scale_text(answer)


def ask(question, default, kind=int, lowest=None, highest=None):
    """Keep asking until the answer is valid. Enter = default."""
    while True:
        answer = input(f"  {question} [{default}]: ").strip()
        if not answer:
            return default
        try:
            value = kind(answer.replace(",", "."))   # decimal comma, as in Italian
        except ValueError:
            print(tr("invalid_value"))
            continue
        if (lowest is not None and value < lowest) or (highest is not None and value > highest):
            print(tr("value_range", lo=lowest, hi=highest))
            continue
        return value


# --- menus ---
# In a terminal the options are a full-screen menu (asciimatics): arrow keys
# and Enter, or the option's number, or a click. Without a terminal (pipes,
# tests) or without asciimatics it falls back to the numbered question, so
# the program keeps working either way. The choice is echoed afterwards, so
# the scrolling log still says what was picked.
def menus_available():
    if os.environ.get("WYRMHEX_NO_MENUS") or not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    try:
        import asciimatics.screen   # noqa: F401
    except ImportError:
        return False
    return True


def menu(title, options, default=0, context=()):
    """Index (0-based) of the chosen option. context: lines shown above the
    question, for what the full-screen menu would otherwise hide."""
    title = title.strip()
    if menus_available():
        from asciimatics.exceptions import ResizeScreenError
        from asciimatics.screen import Screen
        while True:
            try:
                choice = Screen.wrapper(draw_menu, arguments=[title, options, default, context])
                break
            except ResizeScreenError:
                continue                       # the window changed size: draw it again
        print(f"  {title} {options[choice]}")
        return choice
    print(f"  {title}")                         # context: the caller printed it already
    for i, text in enumerate(options, 1):
        print(f"    {i} = {text}")
    return ask(tr("choice"), default + 1, int, 1, len(options)) - 1


def draw_menu(screen, title, options, current, context):
    from asciimatics.event import KeyboardEvent, MouseEvent
    from asciimatics.screen import Screen
    fancy = screen.unicode_aware
    marker = "▶" if fancy else ">"
    width, height = screen.width, screen.height

    def cut(text, room):
        return text if len(text) <= room else text[:max(0, room - 1)] + ("…" if fancy else "~")

    while True:
        screen.clear_buffer(Screen.COLOUR_WHITE, Screen.A_NORMAL, Screen.COLOUR_BLACK)
        screen.print_at(cut(f"WyrmHex v{VERSION}", width - 4), 2, 1, Screen.COLOUR_YELLOW, Screen.A_BOLD)
        y = 3
        for line in context:                   # long lines wrap, they're there to be read
            for piece in textwrap.wrap(line.strip(), max(20, width - 4)) or [""]:
                screen.print_at(piece, 2, y, Screen.COLOUR_CYAN)
                y += 1
        if context:
            y += 1
        for piece in textwrap.wrap(title, max(20, width - 4)):
            screen.print_at(piece, 2, y, Screen.COLOUR_WHITE, Screen.A_BOLD)
            y += 1
        y += 1
        rows = {}
        for i, text in enumerate(options):
            label = cut(f" {i + 1}  {text} " if len(options) < 10 else f" {text} ", width - 8)
            if i == current:
                screen.print_at(marker, 3, y, Screen.COLOUR_YELLOW, Screen.A_BOLD)
                screen.print_at(label, 5, y, Screen.COLOUR_BLACK, Screen.A_NORMAL, Screen.COLOUR_YELLOW)
            else:
                screen.print_at(label, 5, y, Screen.COLOUR_WHITE)
            rows[y] = i
            y += 1
        keys = tr("menu_keys" if fancy else "menu_keys_ascii")
        screen.print_at(cut(keys, width - 4), 2, max(y + 1, height - 2), Screen.COLOUR_WHITE)
        screen.refresh()

        screen.wait_for_input(0.5)
        event = screen.get_event()
        if screen.has_resized():
            from asciimatics.exceptions import ResizeScreenError
            raise ResizeScreenError("resized")
        if isinstance(event, KeyboardEvent):
            key = event.key_code
            if key in (Screen.KEY_UP, ord("k")):
                current = (current - 1) % len(options)
            elif key in (Screen.KEY_DOWN, ord("j"), Screen.KEY_TAB):
                current = (current + 1) % len(options)
            elif key == Screen.KEY_HOME:
                current = 0
            elif key == Screen.KEY_END:
                current = len(options) - 1
            elif key in (10, 13):
                return current
            elif ord("1") <= key <= ord("9") and key - ord("1") < len(options):
                return key - ord("1")
            elif key == 3:                     # Ctrl+C, when the terminal hands it over as a key
                raise KeyboardInterrupt
        elif isinstance(event, MouseEvent) and event.buttons & MouseEvent.LEFT_CLICK and event.y in rows:
            return rows[event.y]


# --- welcome screen, wizard, questions ---
WELCOME_ART = r"""
\ ___                     \       /   /)                 ___ /
 \    \_______________     \\ _ //   // _______________/    /
  \      //-  -    / \\__,- .\ /. -,((_// \   -  - \\      /
   \    //   ****************) (*****************   \\    /
    \  //   /****************,_,*****************\   \\  /
     \// __/ *             WyrmHex              * \__ \\/
     /       *@VERSION@*       \
             *************M********M*************

                                                |>>>
                                                |
                                            _  _|_  _
                                           |;|_|;|_|;|
                                           \\.    .  /
                                            \\:  .  /
                                             ||:   |
                                             ||:.  |
                                             ||:  .|
                                             ||:   |       \,/
                                             ||: , |            /`\
                                             ||:   |
                                             ||: . |
              __                            _||_   |
     ____--`~    '--~~__            __ ----~    ~`---,              ___
-~--~                   ~---__ ,--~'                  ~~----_____-~'   `~----~~
"""


def terminal_width():
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError):
        return None


def show_welcome():
    # the sign holds the name and the version, centred in its 34 letters
    art = WELCOME_ART.strip("\n").replace("@VERSION@", f"v{VERSION}".center(34)).split("\n")
    subtitle = tr("welcome_subtitle")
    width = max(len(line) for line in art)
    # wrapped lines would scramble the drawing, so cut it at the window edge
    columns = terminal_width()
    if columns and columns <= width:
        width = columns - 1
    screen = [
        "═" * width,
        *[line[:width] for line in art],
        "",
        " " * max(0, (width - len(subtitle)) // 2) + subtitle,
        "═" * width,
    ]
    print("\n" + "\n".join(line.rstrip() for line in screen) + "\n")
    input(tr("press_enter"))
    print()


# Wizard by Row (classic ASCII art archives). His "-Row" signature in the
# bottom right corner is where @SPELL@ goes on screen; credit kept here.
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
    print(WIZARD.replace("@SPELL@", tr("conjuring")).rstrip())


def ask_mode(folder=MAPS_FOLDER):
    """None for a new map, otherwise (number, settings[, edit]). settings is None
    only for an old number seed whose PNG is gone: then everything is asked again.
    settings["edit"] is True when the map is going to be edited."""
    choice = menu(tr("what_to_do"), [tr("mode_new"), tr("mode_rebuild"), tr("mode_edit")])
    if choice == 0:
        return None
    edit = choice == 2
    while True:
        answer = input(tr("ask_seed", example=example_seed())).strip()
        if is_old_seed(answer) or read_seed(answer):
            break
        print(tr("seed_invalid", example=example_seed()))

    if not is_old_seed(answer):
        saved = rebuild_settings(answer, folder)
        print(tr("found_seed", seed=make_seed(saved, saved["seed"]), desc=describe_settings(complete_settings(saved))))
        saved["edit"] = edit
        return saved["seed"], saved

    # old number seed: only the PNG knows the settings
    number = int(answer)
    saved = rebuild_settings(answer, folder)
    if saved:
        print(tr("found_settings", seed=number, desc=describe_settings(saved)))
        if input(tr("use_settings")).strip().lower().startswith("n"):
            saved = None
    else:
        print(tr("no_settings", seed=number, folder=short_path(folder)))
    if not saved:
        print(tr("same_settings"))
    else:
        saved["edit"] = edit
    return number, saved, edit


def ask_look(p):
    """Doesn't change the land, so it's asked again when rebuilding a map."""
    p["ascii_only"] = input(tr("ask_ascii")).strip().lower().startswith(tr("yes_letter"))
    print()
    p["colors"] = menu(tr("colors_how"), [tr("colors_mono"), tr("colors_color")]) == 1
    p["background"] = "white"
    if p["colors"]:      # a black background only makes sense for a colour map
        print()
        p["background"] = ("white", "black")[menu(tr("background_how"),
                                                  [tr("background_white"), tr("background_black")])]


def ask_settings():
    ask_language()
    show_welcome()
    print(tr("enter_accepts"))
    mode = ask_mode()
    if mode and mode[1]:
        # land already known: only the title, the scale and the look are left (paper comes later)
        saved = complete_settings(mode[1])
        saved["output"] = MAPS_FOLDER
        print()
        if input(tr("ask_rename", title=saved["title"])).strip().lower().startswith(tr("yes_letter")):
            saved["title"] = input(tr("ask_new_title", default=saved["title"])).strip() or saved["title"]
        if input(tr("ask_rescale", scale=saved["scale"])).strip().lower().startswith(tr("yes_letter")):
            saved["scale"] = ask_scale(saved["scale"])
            print()
        # the sites are known only once the land is made: main() asks then.
        # In the editor on the map they're named there, with N
        if saved["edit"] and menus_available():
            saved["ask_labels"] = "later"        # asked after the editor, if it had to be the typed one
        else:
            saved["ask_labels"] = input(tr("ask_labels_again")).strip().lower() in YES_WORDS
        ask_look(saved)
        return saved
    print()
    p = {}
    p["columns"] = ask(tr("q_columns"), "auto", int, 2, 80)
    p["rows"] = ask(tr("q_rows"), "auto", int, 2, 80)
    # random values need the grid size, which may still be "auto": main() fills them in
    print()
    p["randomize"] = menu(tr("values_how"), [tr("values_manual"), tr("values_random")]) == 1
    if not p["randomize"]:
        print()
        p["dungeons"] = ask(tr("q_dungeons"), 4, int, 0, MAX_SITES)
        p["cities"] = ask(tr("q_cities"), 3, int, 0, MAX_SITES)
        p["fortresses"] = ask(tr("q_fortresses"), 2, int, 0, MAX_SITES)
        print(tr("pct_intro"))
        while True:
            perc = {terrain: ask(f"% {pick(label).lower()}", DEFAULT_PERCENTAGES[terrain], int, 0, 100)
                    for _, _, terrain, label in TERRAIN_OPTIONS}
            error = check_percentages(perc)
            if not error:
                break
            print(tr("pct_retry", error=error))
        p["percentages"] = perc
        p["rivers"] = ask(tr("q_rivers"), -1, int, -1, MAX_RIVERS)
    print()
    if mode:
        p["seed"] = mode[0]          # an old number seed: we already know the random number
        p["version"] = LAND_BEFORE_WIND
        p["edit"] = mode[-1] is True
    else:
        p["seed"] = None             # a new map gets a new random number
    p["title"] = input(tr("q_title", default=tr("default_title"))).strip() or tr("default_title")
    p["scale"] = ask_scale()
    print()
    p["output"] = MAPS_FOLDER
    p["orientation"] = "auto"
    ask_look(p)
    p["size"], p["font"], p["paper"] = "auto", None, None   # paper: asked after the map is built
    # site names too, but not with random values: those maps start without names
    p["ask_labels"] = not p["randomize"]
    return p


def settings_from_options(argv):
    """Command line version of ask_settings(). Each option has an Italian
    and an English name; --help lists the current language's first."""
    language_from_options(argv)

    def names(italian, english):
        if italian == english:
            return (f"--{italian}",)
        return (f"--{italian}", f"--{english}") if LANG == "it" else (f"--{english}", f"--{italian}")

    def shown(options):
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
    for italian, english, terrain, label in TERRAIN_OPTIONS:
        ap.add_argument(*names(italian, english), dest=terrain, type=int, default=DEFAULT_PERCENTAGES[terrain],
                        metavar="%", help=tr("h_terrain", label=pick(label).lower(),
                                             default=DEFAULT_PERCENTAGES[terrain]))
    ap.add_argument(*names("fiumi", "rivers"), dest="rivers", type=int, default=-1, metavar="N", help=tr("h_rivers"))
    ap.add_argument(*names("casuale", "random"), dest="randomize", action="store_true", help=tr("h_random"))
    ap.add_argument(*names("seme", "seed"), dest="seed", default=None, metavar=tr("mv_seed"),
                    help=tr("h_seed", example=example_seed(), max=RANDOM_NUMBERS - 1))
    ap.add_argument(*names("riproduci", "reproduce"), dest="reproduce", default=None,
                    metavar=tr("mv_seed"), help=tr("h_reproduce"))
    ap.add_argument(*names("modificata", "edited"), dest="edited", action="store_true", help=tr("h_edited"))
    ap.add_argument(*names("titolo", "title"), dest="title", default=None, metavar=tr("mv_text"),
                    help=tr("h_title"))
    ap.add_argument(*names("scala", "scale"), dest="scale", default=None, metavar=tr("mv_text"),
                    help=tr("h_scale"))
    ap.add_argument(*names("formato", "format"), dest="paper", type=str.upper, choices=list(PAPERS), default=None,
                    help=tr("h_paper"))
    orientations = {"it": ["auto", "verticale", "orizzontale"], "en": ["auto", "portrait", "landscape"]}
    ap.add_argument(*names("orientamento", "orientation"), dest="orientation", choices=list(ORIENTATION_FROM_USER),
                    default="auto", metavar=shown(orientations), help=tr("h_orientation"))
    ap.add_argument("--output", default=MAPS_FOLDER, metavar=tr("mv_folder"), help=tr("h_output"))
    ap.add_argument(*names("solo-ascii", "ascii-only"), dest="ascii_only", action="store_true", help=tr("h_ascii"))
    ap.add_argument(*names("colori", "colors"), dest="colors", action="store_true", help=tr("h_colors"))
    backgrounds = {"it": ["bianco", "nero"], "en": ["white", "black"]}
    ap.add_argument(*names("sfondo", "background"), dest="background", choices=list(BACKGROUND_FROM_USER),
                    default=None, metavar=shown(backgrounds), help=tr("h_background"))
    sizes = {"it": ["auto", "piccola", "grande"], "en": ["auto", "small", "large"]}
    ap.add_argument(*names("dimensione", "size"), dest="size", choices=list(SIZE_FROM_USER), default="auto",
                    metavar=shown(sizes), help=tr("h_size"))
    ap.add_argument("--version", action="version", version=f"WyrmHex v{VERSION}", help=tr("h_version"))
    ap.add_argument("--font", default=None, metavar="FILE", help=tr("h_font"))
    a = ap.parse_args(argv)
    if a.background and not a.colors:
        ap.error(tr("err_background"))
    background = BACKGROUND_FROM_USER[a.background or "white"]
    orientation = ORIENTATION_FROM_USER[a.orientation]
    ask_for_paper = a.paper is None and sys.stdin.isatty()
    size = SIZE_FROM_USER[a.size]

    # --seed with a full code means "rebuild that one"
    if a.reproduce is None and a.seed is not None and not is_old_seed(a.seed):
        a.reproduce, a.seed = a.seed, None
    if a.seed is not None and not (is_old_seed(a.seed) and int(a.seed) < RANDOM_NUMBERS):
        ap.error(tr("err_seed_number", max=RANDOM_NUMBERS - 1, example=example_seed()))
    if a.edited and a.reproduce is None:
        ap.error(tr("err_edited_needs_seed"))

    if a.reproduce is not None:
        saved = rebuild_settings(a.reproduce, a.output)
        if not saved:
            if is_old_seed(a.reproduce):
                ap.error(tr("err_no_saved", seed=a.reproduce, folder=short_path(a.output)))
            ap.error(tr("err_bad_seed", seed=a.reproduce, example=example_seed()))
        saved["output"] = a.output
        # the look comes from this command line, not from the old PNG
        saved.update(ascii_only=a.ascii_only, colors=a.colors, background=background)
        for key in ("title", "scale"):
            if getattr(a, key) is not None:
                saved[key] = getattr(a, key)   # a title or scale typed now wins over the saved one
        for key, value in (("size", size), ("font", a.font)):
            saved.setdefault(key, value)
        saved = complete_settings(saved)
        if a.paper:
            saved["paper"] = a.paper            # a format typed now wins over the saved one
        saved["orientation"] = orientation
        saved["ask_paper"] = ask_for_paper
        saved["apply_edits"] = a.edited
        return saved

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
        "rivers": a.rivers, "seed": None if a.seed is None else int(a.seed),
        "title": a.title or tr("default_title"), "scale": scale_text(a.scale) if a.scale else tr("default_scale"),
        "orientation": orientation, "output": a.output, "paper": a.paper,
        "ascii_only": a.ascii_only, "colors": a.colors, "background": background, "size": size, "font": a.font,
        "ask_paper": ask_for_paper, "randomize": a.randomize,
    }


def validate(p, log):
    """Exits on bad settings, otherwise returns the hex count of each terrain."""
    errors = []
    if not (2 <= p["columns"] <= 80 and 2 <= p["rows"] <= 80):
        errors.append(tr("err_grid_range"))
    for key in ("dungeons", "cities", "fortresses"):
        if not 0 <= p[key] <= MAX_SITES:
            errors.append(tr("err_sites_range", name=tr("n_" + key), max=MAX_SITES))
    if not -1 <= p["rivers"] <= MAX_RIVERS:
        errors.append(tr("err_rivers_range", max=MAX_RIVERS))
    perc_error = check_percentages(p["percentages"])
    if perc_error:
        errors.append(perc_error)
    if errors:
        print(tr("err_params"))
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    total_perc = sum(p["percentages"].values())
    log.info(tr("info_grid", c=p["columns"], r=p["rows"], n=p["columns"] * p["rows"]))
    log.info(tr("info_terrains", list=", ".join(f"{pick(label).lower()} {p['percentages'][terrain]:g}%"
                                                for _, _, terrain, label in TERRAIN_OPTIONS)))
    log.info(tr("info_pct_sum", t=total_perc))
    if total_perc < 100:
        log.info(tr("info_pct_rest", r=100 - total_perc))

    total = p["columns"] * p["rows"]
    perc = dict(p["percentages"])
    perc[PLAINS] += 100 - total_perc
    counts = split_hexes(total, perc)

    land = total - counts[SEA] - counts[LAKE]
    sites = p["cities"] + p["fortresses"] + p["dungeons"]
    log.info(tr("info_sites", c=p["cities"], f=p["fortresses"], d=p["dungeons"]))
    if sites > land:
        print(tr("err_land", sites=sites, land=land))
        sys.exit(1)
    return counts


# --- land ---
# Random heightmap -> sea at the low edges, lakes in the dips, mountains and
# hills on top. Then a prevailing wind carries rain across the map: the slopes
# facing it get wet, the land behind the ranges stays dry. Swamps in the low
# wet bits, forest where it rains / desert where it doesn't (plus some noise),
# rivers downhill, sites last.
def normalize(values):
    low, high = min(values.values()), max(values.values())
    spread = (high - low) or 1.0
    return {k: (v - low) / spread for k, v in values.items()}


def noise_field(grid, rng, passes):
    """Random values smoothed `passes` times: more passes, bigger blobs."""
    f = {h: rng.random() for h in grid.hexes}
    for _ in range(passes):
        f = {h: (2 * f[h] + sum(f[n] for n in grid.neighbours(h))) / (2 + len(grid.neighbours(h)))
             for h in grid.hexes}
    return normalize(f)


def make_heights(grid, rng):
    big = noise_field(grid, rng, max(3, (grid.cols + grid.rows) // 5))   # big shapes
    small = noise_field(grid, rng, 2)                                    # small details
    edge_band = max(1.0, min(grid.cols, grid.rows) * 0.25)
    height = {}
    for c, r in grid.hexes:
        # pull the edges down so the sea tends to end up there
        from_edge = min(c, grid.cols - 1 - c, r, grid.rows - 1 - r)
        height[(c, r)] = 0.55 * big[(c, r)] + 0.25 * small[(c, r)] + 0.20 * min(1.0, from_edge / edge_band)
    return normalize(height)


ISLAND_SEA = 50                      # more sea than this (%) -> peninsulas and archipelagos
SIDES = (("nord", "north"), ("est", "east"), ("sud", "south"), ("ovest", "west"))


def side_distance(grid, h, side):
    """0 on the given map side (index into SIDES), 1 on the opposite one."""
    c, r = h
    return ((r, grid.cols - 1 - c, grid.rows - 1 - r, c)[side]
            / max(1, (grid.rows, grid.cols)[side % 2] - 1))


def ridge_noise(grid, rng, passes, axis):
    """Noise smoothed mostly along `axis` (a unit vector in hex_xy units):
    long ridges and troughs that point that way."""
    pos = {h: hex_xy(h) for h in grid.hexes}
    weights = {}
    for h in grid.hexes:
        for nb in grid.neighbours(h):
            along = abs((pos[nb][0] - pos[h][0]) * axis[0] + (pos[nb][1] - pos[h][1]) * axis[1]) / math.sqrt(3)
            weights[h, nb] = 0.1 + 2.0 * along ** 4
    f = {h: rng.random() for h in grid.hexes}
    for _ in range(passes):
        f = {h: (f[h] + sum(weights[h, nb] * f[nb] for nb in grid.neighbours(h)))
                / (1 + sum(weights[h, nb] for nb in grid.neighbours(h)))
             for h in grid.hexes}
    return normalize(f)


def make_island_heights(grid, rng, sea_percent):
    """For maps that are mostly sea. Unless the sea is nearly everything, a
    mainland along one side, its coast cut into long peninsulas and bays by
    ridges pointing out to sea; out in the water, bumps that rise as islands.
    The open-sea edges are pulled down so the islands sit inside the map.
    Returns (heights, mainland side or None)."""
    side = rng.randrange(len(SIDES)) if sea_percent < 80 else None
    blobs = noise_field(grid, rng, max(2, (grid.cols + grid.rows) // 12))   # islands
    small = noise_field(grid, rng, 1)                                       # ragged coasts
    ridges = None
    if side is not None:
        axis = (0.0, 1.0) if side % 2 == 0 else (1.0, 0.0)                  # out to sea
        ridges = ridge_noise(grid, rng, max(3, (grid.cols + grid.rows) // 6), axis)
    land = (100 - sea_percent) / 100
    band = max(1.0, min(grid.cols, grid.rows) * 0.2)
    height = {}
    for h in grid.hexes:
        c, r = h
        edges = [r, grid.cols - 1 - c, grid.rows - 1 - r, c]
        if side is not None:
            edges.pop(side)
        sink = 0.25 * max(0.0, 1.0 - min(edges) / band)
        value = 0.55 * blobs[h] + 0.2 * small[h] - sink
        if side is not None:
            # the mainland rises near its side; the ridges reach further out,
            # into the sea, and become peninsulas with bays between them
            d = side_distance(grid, h, side)
            value += 0.25 * max(0.0, 1.0 - d / min(1.0, 1.5 * land))
            value += 0.4 * (ridges[h] - 0.35) * max(0.0, 1.0 - d / min(1.0, 3 * land))
        height[h] = value
    return normalize(height), side


def flood_open_sea(grid, height, n, rng, terrain, side):
    """Like flood_sea, but the water comes in from every edge except the
    mainland's, so it surrounds the islands and fills the bays."""
    starts = [h for h in grid.hexes if grid.on_edge(h) and (side is None or side_distance(grid, h, side) > 0)]
    queue = [(height[h] + rng.uniform(0, 0.04), h) for h in starts]
    heapq.heapify(queue)
    seen, placed = set(starts), 0
    while queue and placed < n:
        _, hex_ = heapq.heappop(queue)
        terrain[hex_] = SEA
        placed += 1
        for nb in grid.neighbours(hex_):
            if nb not in seen:
                seen.add(nb)
                heapq.heappush(queue, (height[nb] + rng.uniform(0, 0.04), nb))
    return placed


def count_islands(grid, terrain, side):
    """Pieces of land not touching the mainland side (all of them if there's
    no mainland)."""
    seen, islands = set(), 0
    for h in grid.hexes:
        if terrain[h] == SEA or h in seen:
            continue
        piece, queue = [], deque([h])
        seen.add(h)
        while queue:
            current = queue.popleft()
            piece.append(current)
            for nb in grid.neighbours(current):
                if terrain[nb] != SEA and nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        if side is None or not any(side_distance(grid, p, side) == 0 for p in piece):
            islands += 1
    return islands


def flood_sea(grid, height, n, rng, terrain):
    """Start from the lowest edge hex and keep taking the lowest hex next to the
    water, like a basin filling up."""
    if n <= 0:
        return None
    edge = [h for h in grid.hexes if grid.on_edge(h)]
    start = min(edge, key=lambda h: height[h] + rng.uniform(0, 0.08))
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
    """Lakes of 1-4 hexes in low ground. Returns (hexes placed, number of lakes)."""
    if n <= 0:
        return 0, 0
    sizes, left = [], n
    while left > 0:
        s = min(left, rng.randint(1, 4))
        sizes.append(s)
        left -= s

    def free(h, strict):
        # strict: also keep away from the sea and the map edge
        if terrain[h] is not None:
            return False
        if strict and (grid.on_edge(h) or any(terrain[nb] == SEA for nb in grid.neighbours(h))):
            return False
        return True

    starts, placed = [], 0
    for size in sizes:
        # no room? loosen the rules and try again
        candidates, strict = [], True
        for strict, min_dist in ((True, 3), (False, 2), (False, 1)):
            candidates = [h for h in grid.hexes if free(h, strict)
                          and all(grid.distance(h, s) >= min_dist for s in starts)]
            if candidates:
                break
        if not candidates:
            break
        candidates.sort(key=lambda h: height[h])
        start = rng.choice(candidates[:max(1, len(candidates) // 3)])
        starts.append(start)
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
    land = [h for h in grid.hexes if terrain[h] is None]
    # a bit of jitter, or the hill/mountain border looks like a contour line
    by_height = sorted(land, key=lambda h: height[h] + rng.uniform(-0.03, 0.03), reverse=True)
    for h in by_height[:n_mountains]:
        terrain[h] = MOUNTAINS
    for h in by_height[n_mountains:n_mountains + n_hills]:
        terrain[h] = HILLS


# where the prevailing wind blows from, clockwise from north; the vector is
# where it blows to, in map units (x right, y down)
WIND_NAMES = (("nord", "north"), ("nord-est", "north-east"), ("est", "east"), ("sud-est", "south-east"),
              ("sud", "south"), ("sud-ovest", "south-west"), ("ovest", "west"), ("nord-ovest", "north-west"))
WIND_VECTORS = tuple((-math.sin(i * math.pi / 4), math.cos(i * math.pi / 4)) for i in range(8))
WIND_LIFT = {MOUNTAINS: 0.45, HILLS: 0.2}    # share of the air's water a hex wrings out
WIND_DRIZZLE = 0.04                          # same, on flat land
WIND_DRYING = 0.985                          # air loses a bit every hex inland
WIND_SEA_PICKUP = 0.25                       # and gets it back over sea and lakes


def hex_xy(h):
    """Centre of a flat-top odd-q hex: neighbours are all sqrt(3) apart."""
    c, r = h
    return 1.5 * c, math.sqrt(3) * (r + 0.5 * (c & 1))


def rain_map(grid, height, terrain, wind):
    """Air comes in wet from the upwind edge and crosses the map with the wind.
    Climbing hills and mountains wrings the water out of it, so the slopes
    facing the wind get the rain and the land behind them stays dry (rain
    shadow). Over sea and lakes it fills up again. 0-1 for every land hex."""
    dx, dy = WIND_VECTORS[wind]
    pos = {h: hex_xy(h) for h in grid.hexes}
    along = {h: pos[h][0] * dx + pos[h][1] * dy for h in grid.hexes}
    air, rain = {}, {}
    for h in sorted(grid.hexes, key=along.get):           # upwind hexes first
        moist = rise = weight = 0.0
        for nb in grid.neighbours(h):
            # how straight the wind blows from nb into h: 1 = head on
            w = (along[h] - along[nb]) / math.sqrt(3)
            if w > 0.3:
                weight += w
                moist += w * air[nb]
                rise += w * (height[h] - height[nb])
        if weight:
            moist, rise = moist / weight, rise / weight
        else:
            moist, rise = 1.0, 0.0                        # fresh air from off the map
        if terrain[h] in WATER:
            air[h] = min(1.0, moist + WIND_SEA_PICKUP)
            continue
        wrung = moist * min(0.8, WIND_LIFT.get(terrain[h], WIND_DRIZZLE) + max(0.0, rise))
        rain[h] = 0.4 * moist + wrung
        air[h] = (moist - wrung) * WIND_DRYING
    return normalize(rain) if rain else rain


# Salt in the soil comes from two places: the sea (spray and salt water
# seeping into low coastal ground) and dry ground, where water evaporates and
# leaves its salt behind, worst in closed dips with nowhere to drain. Rain,
# lakes and rivers wash it out.
SALT_SEA_REACH = 3                   # hexes inland the sea still salts the soil
FERTILE_SALT = 0.16                  # plains saltier than this can't be farmed


def salinity_map(grid, terrain, height, rain, rivers=()):
    """(salt, the part of it that comes from the sea) for every land hex, 0-1."""
    to_sea = grid.distances_from([h for h in grid.hexes if terrain[h] == SEA])
    fresh = [h for h in grid.hexes if terrain[h] == LAKE] + [h for r in rivers for h in r["path"]]
    to_fresh = grid.distances_from(fresh)
    salt, sea_salt = {}, {}
    for h in grid.hexes:
        if terrain[h] in WATER:
            continue
        d = to_sea[h]
        from_sea = 0.0 if d is None else max(0.0, 1.0 - (d - 1) / SALT_SEA_REACH) * (1.0 - 0.7 * height[h])
        dry = (1.0 - rain[h]) * (1.0 - 0.6 * height[h])
        if all(height[nb] >= height[h] for nb in grid.neighbours(h)):
            dry *= 1.4                                   # a closed dip: the salt can't drain away
        washed = {0: 0.45, 1: 0.3, 2: 0.12}.get(to_fresh[h], 0.0)
        salt[h] = min(1.0, max(0.0, 0.6 * from_sea + 0.5 * dry - washed))
        sea_salt[h] = 0.6 * from_sea
    return salt, sea_salt


def place_swamps(grid, height, n, rng, terrain, rain=None, salt=None):
    """Lowest free hexes, nearer to water first (and where it rains, if there
    is wind). Patches come out by themselves."""
    if n <= 0:
        # don't touch rng here: maps without swamps must match pre-0.0.3 ones
        return
    to_water = grid.distances_from([h for h in grid.hexes if terrain[h] in WATER])
    score = {}
    for h in grid.hexes:
        if terrain[h] is None:
            d = to_water[h] if to_water[h] is not None else 4
            score[h] = height[h] + 0.06 * min(d, 4) + 0.05 * rng.random()
            if rain:
                score[h] -= 0.1 * rain[h]
            if salt:
                # salt marshes are fine on the coast; inland, salty dry
                # ground turns into a crust, not a marsh
                score[h] += 0.15 * max(0.0, salt[0][h] - salt[1][h])
    for h in sorted(score, key=score.get)[:n]:
        terrain[h] = SWAMP


def place_forests_and_deserts(grid, n_forests, n_deserts, rng, terrain, rain=None):
    """Wettest free hexes become forest, driest desert. Wetness is noise, plus
    the rain brought by the wind if there is one, plus being near water."""
    wetness = {h: 0.7 * v for h, v in noise_field(grid, rng, max(2, (grid.cols + grid.rows) // 7)).items()}
    fine = noise_field(grid, rng, 1)
    to_water = grid.distances_from([h for h in grid.hexes if terrain[h] in WATER])
    for h in grid.hexes:
        wetness[h] += 0.3 * fine[h]
        if rain and h in rain:
            wetness[h] = 0.4 * wetness[h] + 0.6 * rain[h]
        d = to_water[h]
        if d == 1:
            wetness[h] += 0.25
        elif d == 2:
            wetness[h] += 0.12
    free = sorted((h for h in grid.hexes if terrain[h] is None), key=lambda h: wetness[h], reverse=True)
    for h in free[:n_forests]:
        terrain[h] = FOREST
    rest = sorted(free[n_forests:], key=lambda h: wetness[h])
    for h in rest[:n_deserts]:
        terrain[h] = DESERT
    for h in rest[n_deserts:]:
        terrain[h] = PLAINS


def follow_river(grid, terrain, height, spring, river_hexes, rng, max_length):
    """Walk downhill from spring. Returns (path, end); end is None if it got stuck."""
    path, end = [spring], None
    while len(path) <= max_length:
        current = path[-1]
        around = grid.neighbours(current)
        water = [nb for nb in around if terrain[nb] in WATER]
        if water:
            end = ("water", min(water, key=lambda nb: height[nb]))
            break
        joins = [nb for nb in around if nb in river_hexes]
        if joins and len(path) >= 3:
            end = ("join", joins[0])
            break
        # no going back, no loops
        forbidden = set(path)
        for p in path[:-1]:
            forbidden.update(grid.neighbours(p))
        options = [nb for nb in around if nb not in forbidden and nb not in river_hexes]
        if grid.on_edge(current) and len(path) >= 3 and (
                not options or min(height[nb] for nb in options) > height[current]):
            end = ("edge", None)
            break
        if not options:
            break   # stuck
        path.append(min(options, key=lambda nb: height[nb] + rng.uniform(0, 0.03)))
    return path, end


def trace_rivers(grid, terrain, height, n, rng):
    """Rivers start high up and always go to the lowest neighbour, until they hit
    water, another river or the map edge. The ones that get stuck are dropped."""
    if n <= 0:
        return []
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
        if spring in river_hexes or any(grid.distance(spring, r["path"][0]) < 4 for r in rivers):
            continue
        if any(terrain[nb] in WATER for nb in grid.neighbours(spring)):
            continue
        path, end = follow_river(grid, terrain, height, spring, river_hexes, rng, max_length)
        # keep it only if it's >= 3 hexes and ends somewhere sensible
        if end and len(path) >= 3:
            rivers.append({"path": path, "end": end})
            river_hexes.update(path)
    return rivers


def place_sites(grid, terrain, rivers, wanted, rng, log, fertile=()):
    """Weighted random choice by terrain, with a minimum distance between sites
    of the same kind (relaxed if the map is too crowded)."""
    land = [h for h in grid.hexes if terrain[h] not in WATER]
    river_hexes = {h for r in rivers for h in r["path"]}

    def near_water(h):
        return h in river_hexes or any(terrain[nb] in WATER for nb in grid.neighbours(h))

    # higher = more likely
    base_weights = {
        CITY: {PLAINS: 4, HILLS: 2, FOREST: 1.2, DESERT: 0.6, SWAMP: 0.3, MOUNTAINS: 0.2},
        FORTRESS: {HILLS: 4, MOUNTAINS: 3, PLAINS: 1.5, FOREST: 1, DESERT: 0.8, SWAMP: 0.5},
        DUNGEON: {MOUNTAINS: 4, HILLS: 3.5, FOREST: 3, SWAMP: 3, DESERT: 2.5, PLAINS: 1},
    }
    sites, taken = [], set()
    for kind, n in ((CITY, wanted[CITY]), (FORTRESS, wanted[FORTRESS]), (DUNGEON, wanted[DUNGEON])):
        if n <= 0:
            continue
        # more land per site -> sites further apart
        spacing = math.sqrt(len(land) / n)
        same_kind_dist = {CITY: max(3, round(spacing * 0.7)),
                          FORTRESS: max(2, round(spacing * 0.5)),
                          DUNGEON: max(2, round(spacing * 0.45))}[kind]
        relaxed = False
        for _ in range(n):
            same_kind = [h for k, h in sites if k == kind]
            d_same, d_other = same_kind_dist, 2
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
            cities = [h for k, h in sites if k == CITY]
            weights = []
            for h in candidates:
                w = base_weights[kind][terrain[h]]
                if kind == CITY:
                    w *= 3 if near_water(h) else 1
                    w *= 2 if h in fertile else 1             # farmland to feed it
                    w *= 0.5 if grid.on_edge(h) else 1       # ...and not the map edge
                elif kind == FORTRESS:
                    w *= 1 + 0.5 * sum(terrain[nb] in (MOUNTAINS, HILLS) for nb in grid.neighbours(h))
                elif kind == DUNGEON and cities:
                    w *= 1 + min(grid.distance(h, c) for c in cities) / 4
                weights.append(w)
            chosen = rng.choices(candidates, weights=weights)[0]
            sites.append((kind, chosen))
            taken.add(chosen)
        log.info(tr("info_site_kind", name=pick(SITE_NAMES[kind]), n=n, d=same_kind_dist)
                 + (tr("relaxed") if relaxed else ""))
    return sites


def build_land(params, counts, grid, rng, log):
    """Steps 3-9. Returns (terrain of every hex, rivers, sites, heights, farmable plains)."""
    islands = (params.get("version", SEED_VERSION) >= LAND_WITH_ISLANDS
               and params["percentages"][SEA] > ISLAND_SEA)
    log.step(tr("step_heights"))
    if islands:
        height, side = make_island_heights(grid, rng, params["percentages"][SEA])
    else:
        height = make_heights(grid, rng)
    log.info(tr("info_heights", n=len(grid.hexes)))

    terrain = {h: None for h in grid.hexes}
    log.step(tr("step_sea"))
    if islands:
        flood_open_sea(grid, height, counts[SEA], rng, terrain, side)
        n_islands = count_islands(grid, terrain, side)
        if side is None:
            log.info(tr("info_archipelago", n=counts[SEA], i=n_islands))
        else:
            log.info(tr("info_peninsulas", n=counts[SEA], side=pick(SIDES[side]), i=n_islands))
    else:
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
    rain = None
    if params.get("version", SEED_VERSION) > LAND_BEFORE_WIND:
        wind = rng.randrange(len(WIND_NAMES))
        rain = rain_map(grid, height, terrain, wind)
        log.info(tr("info_wind", wind=pick(WIND_NAMES[wind]), lee=pick(WIND_NAMES[(wind + 4) % 8])))
    salty = params.get("version", SEED_VERSION) >= LAND_WITH_SALT
    place_swamps(grid, height, counts[SWAMP], rng, terrain, rain,
                 salinity_map(grid, terrain, height, rain) if salty else None)
    place_forests_and_deserts(grid, counts[FOREST], counts[DESERT], rng, terrain, rain)
    actual = {t: sum(1 for h in grid.hexes if terrain[h] == t)
              for t in (PLAINS, SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT)}
    log.info(tr("info_result", list=", ".join(f"{pick(TERRAIN_NAMES[t])} {n}" for t, n in actual.items())))

    log.step(tr("step_rivers"))
    # auto: ~1 river every 60 land hexes
    land = len(grid.hexes) - actual[SEA] - actual[LAKE]
    n_rivers = params["rivers"] if params["rivers"] >= 0 else max(0, round(land / 60))
    rivers = trace_rivers(grid, terrain, height, n_rivers, rng)
    for i, r in enumerate(rivers, 1):
        where = tr("river_" + r["end"][0])
        log.info(tr("info_river", i=i, h=hex_code(r["path"][0], 2), n=len(r["path"]), where=where))
    if len(rivers) < n_rivers:
        log.warn(tr("warn_rivers", d=len(rivers), n=n_rivers))

    # rivers wash the salt out too, so the farmland is worked out once they're there
    fertile = set()
    if salty:
        salt, sea_salt = salinity_map(grid, terrain, height, rain, rivers)
        plains = [h for h in grid.hexes if terrain[h] == PLAINS]
        fertile = {h for h in plains if salt[h] < FERTILE_SALT}
        swamps = [h for h in grid.hexes if terrain[h] == SWAMP]
        marsh = sum(1 for h in swamps if sea_salt[h] > 0.25)
        log.info(tr("info_salt", f=len(fertile), p=len(plains), s=marsh, w=len(swamps) - marsh))

    log.step(tr("step_sites"))
    sites = place_sites(grid, terrain, rivers,
                        {CITY: params["cities"], FORTRESS: params["fortresses"], DUNGEON: params["dungeons"]},
                        rng, log, fertile)

    return terrain, rivers, sites, height, fertile


def print_sites(grid, terrain, rivers, sites, labels=None):
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    print(tr("sites_header"))
    for kind in (CITY, FORTRESS, DUNGEON):
        for i, (_, h) in enumerate([s for s in sites if s[0] == kind], 1):
            extra = tr("on_river") if any(h in r["path"] for r in rivers) else ""
            name = (labels or {}).get(label_key(h))
            name = f"  \"{name}\"" if name else ""
            print(f"  {pick(SITE_NAMES[kind]):<9} {i:>2}  →  {hex_code(h, digits)}  "
                  f"({pick(TERRAIN_NAMES[terrain[h]])}{extra}){name}")


# --- site names ---
# Typed after the land is made, since only then are the sites known. Kept in
# the settings (and so in the PNG) as {"CCRR": name}, like the title: the seed
# can't hold text. A name whose site is gone (editor) is just not drawn.
MAX_LABEL = 24


def label_key(h):
    return hex_code(h, 2)            # grids are at most 80 x 80


def site_labels(sites, labels):
    """Only the names of sites that are still there, in drawing order."""
    labels = labels or {}
    return [(h, labels[label_key(h)]) for _, h in sites if labels.get(label_key(h))]


# answers to "give it a name?": in both languages, whatever the program speaks
YES_WORDS = {"s", "si", "sì", "y", "yes"}
NO_WORDS = {"", "n", "no"}


def ask_labels(grid, terrain, sites, labels):
    """One question per site, cities first. Returns the new {"CCRR": name}."""
    labels = dict(labels or {})
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    print(tr("labels_intro"))
    for kind in (CITY, FORTRESS, DUNGEON):
        for i, (_, h) in enumerate([s for s in sites if s[0] == kind], 1):
            key, old = label_key(h), labels.get(label_key(h))
            values = dict(site=pick(SITE_NAMES[kind]), i=i, h=hex_code(h, digits),
                          terrain=pick(TERRAIN_NAMES[terrain[h]]).lower(), name=old)
            answer = " ".join(input(tr("ask_relabel" if old else "ask_label", **values)).split())
            if answer.lower() in NO_WORDS:
                continue
            # the name typed straight away, without the "yes" first, is taken as
            # it is (it used to count as "no": the site silently stayed nameless)
            typed = answer.lower() not in YES_WORDS
            name = answer if typed else " ".join(input(tr("q_label", n=MAX_LABEL)).split())
            if len(name) > MAX_LABEL:
                cut = name[:MAX_LABEL + 1]
                name = (cut.rsplit(" ", 1)[0] if " " in cut else cut[:MAX_LABEL]).rstrip()
                print(tr("label_cut", name=name))
            elif typed:
                print(tr("label_taken", name=name))
            if name:
                labels[key] = name
            else:
                labels.pop(key, None)
    return labels


def ascii_label(name):
    """For --ascii-only: è -> e, and anything else non-ASCII goes."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


# --- fonts ---
def open_font(spec, size):
    path, index = spec if isinstance(spec, tuple) else (spec, 0)
    return ImageFont.truetype(path, size, index=index)


def find_font(chosen=None):
    """Returns (regular, bold or None)."""
    candidates = []
    if chosen:
        candidates.append((chosen, None))   # the font chosen with --font comes first
    candidates += MONO_FONTS
    try:
        # matplotlib ships DejaVu Sans Mono
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
    return os.path.basename(spec[0] if isinstance(spec, tuple) else spec)


def font_metrics(spec):
    """Advance and line height, as fractions of the font size."""
    f = open_font(spec, 200)
    ascent, descent = f.getmetrics()
    return f.getlength("M") / 200, (ascent + descent) / 200


def font_has_glyph(font, ch):
    """A missing glyph renders as the .notdef box, so compare with a
    character that surely isn't in the font."""
    def fingerprint(c):
        img = Image.new("L", (80, 80), 0)
        ImageDraw.Draw(img).text((10, 10), c, font=font, fill=255)
        return img.tobytes()
    missing = fingerprint("\U0010FFFD")
    return fingerprint(ch) != missing and any(fingerprint(ch))


class Glyphs:
    """G("♣", "T") -> "♣", or "T" with --ascii-only or if the font lacks ♣."""

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
    total = sum(w for _, _, w in choices)
    v = rng.uniform(0, total)
    for fancy, plain, w in choices:
        v -= w
        if v <= 0:
            return G(fancy, plain)
    return G(choices[-1][0], choices[-1][1])


# --- canvas ---
class Canvas:
    """Grid of characters, each with a style:
      n normal, b bold, i white on black, g gray square (sea),
      G / H normal / bold char on gray, B under a site box (see boxes)"""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.chars = [[" "] * width for _ in range(height)]     # the letters
        self.styles = [["n"] * width for _ in range(height)]    # the style of each letter
        self.tags = [[None] * width for _ in range(height)]     # palette key, for colour maps
        self.boxes = []            # site boxes: (x, y, width, height, symbol, tag)
        self.fills = []            # backgrounds drawn first: ([(x, y) corners, in letter squares], tag)

    def put(self, x, y, ch, style="n", tag=None):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.chars[y][x], self.styles[y][x], self.tags[y][x] = ch, style, tag

    def write(self, x, y, text, style="n", tag=None):
        for i, c in enumerate(text):
            self.put(x + i, y, c, style, tag)

    def paste(self, other, ox, oy):
        for y in range(other.height):
            for x in range(other.width):
                self.put(ox + x, oy + y, other.chars[y][x], other.styles[y][x], other.tags[y][x])
        self.boxes += [(ox + x, oy + y, w, h, g, t) for x, y, w, h, g, t in other.boxes]
        self.fills += [([(ox + x, oy + y) for x, y in points], t) for points, t in other.fills]

    def copy(self):
        c = Canvas(self.width, self.height)
        c.chars = [row[:] for row in self.chars]
        c.styles = [row[:] for row in self.styles]
        c.tags = [row[:] for row in self.tags]
        c.boxes = list(self.boxes)
        c.fills = list(self.fills)
        return c

    def lines(self):
        return ["".join(row).rstrip() for row in self.chars]


# --- hex shape ---
#   k = 2              k = 3
#     ____               ______
#    /    \             /      \
#   /      \           /        \
#   \      /          /          \
#    \____/           \          /
#                      \        /
#                       \______/
def hex_template(k):
    """Border chars and inside squares of a hex, as (row, col) from its top-left."""
    u = 2 * k                        # length of the top and bottom sides
    border, inside = [], []
    border += [(0, x, "_") for x in range(k + 1, k + u + 1)]
    for i in range(1, k + 1):
        border += [(i, k + 1 - i, "/"), (i, k + u + i, "\\")]
        inside += [(i, x) for x in range(k + 2 - i, k + u + i)]
    for j in range(1, k):
        border += [(k + j, j, "\\"), (k + j, 2 * k + u + 1 - j, "/")]
        inside += [(k + j, x) for x in range(j + 1, 2 * k + u + 1 - j)]
    border += [(2 * k, k, "\\"), (2 * k, k + u + 1, "/")]
    border += [(2 * k, x, "_") for x in range(k + 1, k + u + 1)]
    return border, inside


def map_size(cols, rows, k):
    return 3 * k * (cols - 1) + 4 * k + 1, 2 * k * rows + k + 1


def hex_origin(c, r, k):
    """Odd columns sit half a hex lower."""
    return 3 * k * c, 2 * k * r + (k if c & 1 else 0)


def hex_centre(c, r, k):
    x0, y0 = hex_origin(c, r, k)
    return x0 + 2 * k + 1, y0 + k + 1


# --- rivers ---
# Smooth curve through the hex centres -> staircase of squares -> box-drawing chars.
def wiggle(points, scale, rng, amount=0.18):
    out = [points[0]]
    for p, q in zip(points, points[1:]):
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy) or 1
        o = rng.uniform(-amount, amount) * scale
        out += [(mx - dy / length * o, my + dx / length * o), q]   # push the middle point sideways
    return out


def smooth(points, rounds=3):
    """Chaikin corner cutting."""
    for _ in range(rounds):
        new = [points[0]]
        for p, q in zip(points, points[1:]):
            new.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            new.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        new.append(points[-1])
        points = new
    return points


def river_line(grid, river, k, rng):
    path, (end_kind, target) = river["path"], river["end"]
    points = [hex_centre(*h, k) for h in path]
    points[0] = (points[0][0] * 0.7 + points[1][0] * 0.3, points[0][1] * 0.7 + points[1][1] * 0.3)
    last = path[-1]
    lx, ly = points[-1]
    if end_kind == "water":
        # stop at the coastline, halfway to the water hex
        tx, ty = hex_centre(*target, k)
        points.append(((lx + tx) / 2, (ly + ty) / 2))
    elif end_kind == "join":
        points.append(hex_centre(*target, k))
    elif end_kind == "stop":         # only from the editor: the river just ends here
        pass
    else:
        px, py = points[-2]
        outside = [n for n in grid.all_neighbours(last) if not grid.inside(n)]
        exit_hex = max(outside, key=lambda n: (hex_centre(*n, k)[0] - lx) * (lx - px)
                       + (hex_centre(*n, k)[1] - ly) * (ly - py))
        tx, ty = hex_centre(*exit_hex, k)
        points.append(((lx + tx) / 2, (ly + ty) / 2))
    return smooth(wiggle(points, 1.2 * k, rng, 0.15), 2)


def line_to_squares(points, aspect):
    """Staircase of 4-connected squares along the line, so the box-drawing
    chars always join up. aspect = letter height / width."""
    squares = []

    def add(sq):
        # back on a square we already visited: cut the loop out
        if sq in squares:
            del squares[squares.index(sq) + 1:]
        else:
            squares.append(sq)

    current = (math.floor(points[0][0]), math.floor(points[0][1]))
    add(current)
    for p, q in zip(points, points[1:]):
        steps = max(1, int(math.hypot(q[0] - p[0], (q[1] - p[1]) * aspect) / 0.3))
        for t in range(1, steps + 1):
            x = p[0] + (q[0] - p[0]) * t / steps
            y = p[1] + (q[1] - p[1]) * t / steps
            target = (math.floor(x), math.floor(y))
            while current != target:
                dx, dy = target[0] - current[0], target[1] - current[1]
                if dx and (not dy or abs(dx) > abs(dy) * aspect):
                    current = (current[0] + (1 if dx > 0 else -1), current[1])
                else:
                    current = (current[0], current[1] + (1 if dy > 0 else -1))
                add(current)
    return squares


# --- drawing the map ---
def draw_map(grid, terrain, rivers, sites, k, G, rng, aspect, original=None, labels=None, ascii_only=False,
             fertile=()):
    """Terrain, then hex borders, then rivers, then sites; each layer can
    overwrite the previous one.
    original = (terrain, rivers) before editing. Its glyphs and river wiggles
    are rolled first, in the usual order, so everything the editor didn't touch
    looks exactly as on the unedited map; only the changed bits get new dice."""
    width, height = map_size(grid.cols, grid.rows, k)
    canvas = Canvas(width, height)
    border, inside = hex_template(k)
    u = 2 * k
    corners = ((k + 1, 1), (k + u + 1, 1), (2 * k + u + 1, k + 1), (k + u + 1, 2 * k + 1), (k + 1, 2 * k + 1), (1, k + 1))
    old_terrain, old_rivers = original or (terrain, rivers)

    def glyphs(kind, dice):
        if kind == SEA or not TERRAIN_GLYPHS[kind]:
            return None
        return [pick_symbol(dice, TERRAIN_GLYPHS[kind], G) for _ in inside]

    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        kind = terrain[(c, r)]
        chars = glyphs(old_terrain[(c, r)], rng)
        if kind != old_terrain[(c, r)]:
            chars = glyphs(kind, random.Random(f"{c},{r},{kind}"))
        # the hexagon through the middle of its border letters: neighbours'
        # fills meet right under the / \ _ drawn on top. Sea too, or the coast
        # keeps white notches between its gray squares and the land
        canvas.fills.append(([(x0 + x, y0 + y) for x, y in corners], bg(kind)))
        if kind == SEA:
            for (yy, xx) in inside:
                # the ≈ only shows in the .txt
                canvas.put(x0 + xx, y0 + yy, G("≈", "~"), "g", SEA)
        elif chars:
            for (yy, xx), ch in zip(inside, chars):
                canvas.put(x0 + xx, y0 + yy, ch, "n", kind)
        elif kind == PLAINS and (c, r) in fertile:
            # own dice: the rest of the map rolls exactly as without farmland
            dice = random.Random(f"{c},{r},{FERTILE}")
            for (yy, xx) in inside:
                canvas.put(x0 + xx, y0 + yy, pick_symbol(dice, TERRAIN_GLYPHS[FERTILE], G), "n", FERTILE)

    # borders between two sea hexes get the gray too, or the sea looks tiled
    shared = {}    # for each border square: [letter, "only sea hexes share it so far"]
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        for (yy, xx, ch) in border:
            shared.setdefault((x0 + xx, y0 + yy), [ch, True])
            shared[(x0 + xx, y0 + yy)][1] &= terrain[(c, r)] == SEA
    for (x, y), (ch, sea_only) in shared.items():
        canvas.put(x, y, ch, "H" if sea_only else "b", "sea_line" if sea_only else "border")

    lines = []
    for river in old_rivers:
        squares = line_to_squares(river_line(grid, river, k, rng), aspect)
        if river in rivers:
            lines.append(squares)
    for river in rivers:
        if river not in old_rivers:      # new or changed in the editor
            dice = random.Random(repr(river["path"]))
            lines.append(line_to_squares(river_line(grid, river, k, dice), aspect))
    arms = {}
    for squares in lines:
        for a, b in zip(squares, squares[1:]):
            d = {(1, 0): "r", (-1, 0): "l", (0, 1): "d", (0, -1): "u"}[(b[0] - a[0], b[1] - a[1])]
            arms.setdefault(a, set()).add(d)
            arms.setdefault(b, set()).add(OPPOSITE[d])
    for (x, y), directions in arms.items():
        fancy, plain = RIVER_CHARS[frozenset(directions)]
        canvas.put(x, y, G(fancy, plain), "b", "river")

    # sites: [⌂⌂] in the .txt, a black box with one big white glyph in the PNG
    cx = 2 * k + 1
    for kind, (c, r) in sites:
        x0, y0 = hex_origin(c, r, k)
        g = G(*SITE_GLYPHS[kind])
        for yy in (k, k + 1):
            canvas.write(x0 + cx - 2, y0 + yy, "[" + g + g + "]", "B")
        canvas.boxes.append((x0 + cx - 2, y0 + k, 4, 2, g, kind))
    draw_labels(canvas, site_labels(sites, labels), sites, k, ascii_only)
    return canvas


def draw_labels(canvas, labels, sites, k, ascii_only):
    """Each name in bold, one space either side, on the row under its site's
    box (the hex's bottom side when k = 2). If that runs into another name or
    a box it slides sideways, then tries the row above the box (not when
    k = 2: the hex numbers go there), and as a last resort goes under the box
    anyway. Over sea the gray stays."""
    taken = set()
    for x, y, w, h, _, _ in canvas.boxes:
        taken.update((x + i, y + j) for i in range(w) for j in range(h))
    centre = 2 * k + 1
    for h, name in labels:
        text = f" {ascii_label(name) if ascii_only else name} "
        x0, y0 = hex_origin(*h, k)
        rows = [y0 + k + 2] + ([y0 + k - 1] if k > 2 else [])
        start = x0 + centre - len(text) // 2
        tries = [(row, start + shift) for row in rows for shift in (0, -2, 2, -4, 4, -6, 6)]
        spot = tries[0]
        for row, x in tries:
            x = max(0, min(x, canvas.width - len(text)))
            if not any((x + i, row) in taken for i in range(len(text))):
                spot = (row, x)
                break
        row, x = spot
        x = max(0, min(x, canvas.width - len(text)))
        for i, ch in enumerate(text):
            if not 0 <= row < canvas.height or not 0 <= x + i < canvas.width:
                continue
            on_sea = canvas.styles[row][x + i] in "gGH"
            if ch == " ":
                canvas.put(x + i, row, " ", "g" if on_sea else "n")
            else:
                canvas.put(x + i, row, ch, "H" if on_sea else "b", "label")
            taken.add((x + i, row))


def write_hex_numbers(page, grid, k, ox, oy):
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    _, inside = hex_template(k)
    top_row = [xx for (yy, xx) in inside if yy == 1]    # the squares of the top inside row
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        y = oy + y0 + 1
        # clear the row but leave rivers alone
        for xx in top_row:
            style = page.styles[y][ox + x0 + xx]
            if style != "b":
                page.put(ox + x0 + xx, y, " ", "g" if style in "gG" else "n")
        # straight on the hex's own background, sea included: no box behind
        code = hex_code((c, r), digits)
        x_num = ox + x0 + 2 * k + 1 - len(code) // 2
        for i, digit in enumerate(code):
            page.put(x_num + i, y, digit, "n")


# --- page: frame, title, legend ---
def legend_entries(G, fertile=False, filled=False):
    # (sample, name, style, colour tag). filled: the hexes have coloured
    # backgrounds, so plains get a swatch instead of "empty hex"
    plains = ("  ", tr("leg_barren_bg" if fertile else "leg_plains_bg"), "b", PLAINS) if filled else \
        ("", tr("leg_barren" if fertile else "leg_plains"), "b", None)
    terrains = [
        (G("▲^", "^A"), tr("leg_mountains"), "b", MOUNTAINS), (G("∩n", "nm"), tr("leg_hills"), "b", HILLS),
        (G("♣♠", "TY"), tr("leg_forest"), "b", FOREST), plains,
        *([(G("τ", "v"), tr("leg_fertile"), "b", FERTILE)] if fertile else []),
        (G("░·", ".:"), tr("leg_desert"), "b", DESERT),
        (G("≈≈", "~~"), tr("leg_sea"), "g", SEA),   # "g": this sample is drawn as a gray patch
        (G("≈≈", "~~"), tr("leg_lake"), "b", LAKE), (G('⌠"', '",'), tr("leg_swamp"), "b", SWAMP),
        (G("═╗", "=+"), tr("leg_river"), "b", "river"),
    ]
    sites = [(G(*SITE_GLYPHS[kind]), pick(SITE_NAMES[kind]), kind) for kind in (CITY, FORTRESS, DUNGEON)]
    if G.ascii_only:
        sites = [(g, name.replace("à", "a'"), kind) for g, name, kind in sites]
    return terrains, sites


def has_farmland(params):
    """Maps made with salinity have farmland, and its line in the legend."""
    return params.get("version", SEED_VERSION) >= LAND_WITH_SALT


def pack_legend(G, max_width, fertile=False, filled=False):
    terrains, sites = legend_entries(G, fertile, filled)
    entries = [[(g, style, tag), (" " + name, "n", None)] if g else [(name, "n", None)]
               for g, name, style, tag in terrains]
    entries += [[("[" + g + "]", "i", kind), (" " + name, "n", None)] for g, name, kind in sites]
    lines, line, length = [], [], 0
    for entry in entries:
        w = sum(len(text) for text, _, _ in entry)
        if line and length + 4 + w > max_width:
            lines.append(line)
            line, length = [], 0
        line.append(entry)
        length += w + (4 if length else 0)   # 4 spaces between entries
    if line:
        lines.append(line)
    return lines


def compose_page(map_canvas, n_cols, n_rows, legend_lines, title, subtitle, G):
    """Returns the page and where the map ended up on it."""
    page = Canvas(n_cols, n_rows)
    horizontal, vertical = G("═", "-"), G("║", "|")
    for x in range(n_cols):
        page.put(x, 0, horizontal)
        page.put(x, n_rows - 1, horizontal)
    for y in range(n_rows):
        page.put(0, y, vertical)
        page.put(n_cols - 1, y, vertical)
    y_legend_line = n_rows - len(legend_lines) - 2
    for y in (2, y_legend_line):
        page.put(0, y, G("╠", "+"))
        page.put(n_cols - 1, y, G("╣", "+"))
        for x in range(1, n_cols - 1):
            page.put(x, y, horizontal)
    for x, y, ch in ((0, 0, "╔"), (n_cols - 1, 0, "╗"), (0, n_rows - 1, "╚"), (n_cols - 1, n_rows - 1, "╝")):
        page.put(x, y, G(ch, "+"))

    heading = f"{G('╡', '[')} {title.upper()} {G('╞', ']')}"
    page.write((n_cols - len(heading)) // 2, 0, heading, "b")
    page.write((n_cols - len(subtitle)) // 2, 1, subtitle)

    area_top, area_height = 3, y_legend_line - 3
    ox = (n_cols - map_canvas.width) // 2
    oy = area_top + (area_height - map_canvas.height) // 2
    page.paste(map_canvas, ox, oy)

    for i, line in enumerate(legend_lines):
        length = sum(sum(len(text) for text, _, _ in entry) for entry in line) + 4 * (len(line) - 1)
        x = (n_cols - length) // 2
        for j, entry in enumerate(line):
            if j:
                x += 4
            for text, style, tag in entry:
                y = y_legend_line + 1 + i
                page.write(x, y, text, style, tag)
                if tag in (PLAINS, FERTILE, FOREST, SEA, LAKE, SWAMP, DESERT, HILLS, MOUNTAINS):
                    # the same background as on the map (if the palette has one)
                    swatch = [(x, y), (x + len(text), y), (x + len(text), y + 1), (x, y + 1)]
                    page.fills.append((swatch, bg(PLAINS if tag == FERTILE else tag)))
                x += len(text)
    return page, ox, oy


# --- paper, rendering, saving ---
def paper_pixels(paper, orientation):
    w_mm, h_mm = PAPERS[paper]
    if orientation == "landscape":
        w_mm, h_mm = h_mm, w_mm
    return round(mm(w_mm)), round(mm(h_mm))


VALID_SIZES = {paper_pixels(p, o) for p in PAPERS for o in ("portrait", "landscape")}


def choose_sheet(map_width, map_height, legend_lines_guess, paper, orientation, aspect):
    """Orientation and letter width (mm) for one paper size.
    Returns (char_mm, fill, orientation, sheet_w_mm, sheet_h_mm)."""
    short, long_ = PAPERS[paper]
    max_char = MAX_CHAR_MM * short / PAPERS["A4"][0]      # bigger sheet, bigger letters allowed
    options = []
    for name, (w_mm, h_mm) in (("portrait", (short, long_)), ("landscape", (long_, short))):
        if orientation not in ("auto", name):
            continue
        page_w, page_h = w_mm - 2 * MARGIN_MM, h_mm - 2 * MARGIN_MM
        char_mm = min(page_w / (map_width + 4), page_h / ((map_height + legend_lines_guess + 7) * aspect),
                      max_char)
        filled = (map_width * char_mm) * (map_height * char_mm * aspect) / (page_w * page_h)
        options.append((char_mm, filled, name, w_mm, h_mm))
    # within 8% the fuller sheet wins over slightly bigger letters
    best = max(o[0] for o in options)
    return max((o for o in options if o[0] >= best * 0.92), key=lambda o: o[1])


def fill_page(params, font_spec, aspect, log):
    """Grid size that fills an A4 at READABLE_CHAR_MM. Only touches the
    dimensions left on "auto"."""
    orientation = "portrait" if params["orientation"] == "portrait" else "landscape"
    w_mm, h_mm = PAPERS["A4"] if orientation == "portrait" else PAPERS["A4"][::-1]
    k = 3 if params["size"] == "large" else 2
    n_cols = int((w_mm - 2 * MARGIN_MM) / READABLE_CHAR_MM)
    n_rows = int((h_mm - 2 * MARGIN_MM) / (READABLE_CHAR_MM * aspect))
    legend_lines = len(pack_legend(Glyphs(open_font(font_spec, 40), params["ascii_only"]), n_cols - 4,
                                   has_farmland(params), has_backgrounds(params)))
    columns = max(2, (n_cols - 4 - (4 * k + 1)) // (3 * k) + 1)
    rows = max(2, (n_rows - legend_lines - 7 - (k + 1)) // (2 * k))
    if params["columns"] == "auto":
        params["columns"] = columns
    if params["rows"] == "auto":
        params["rows"] = rows
    log.info(tr("info_auto_grid", c=params["columns"], r=params["rows"], o=pick(ORIENTATION_NAMES[orientation]),
                mm=READABLE_CHAR_MM))


def hex_size(params, grid, paper, aspect):
    """k = 2 (small) or 3 (large). "auto" only goes large if the letters stay
    readable on this paper."""
    if params["size"] == "small":
        return 2
    if params["size"] == "large":
        return 3
    mw, mh = map_size(grid.cols, grid.rows, 3)
    return 3 if choose_sheet(mw, mh, 3, paper, params["orientation"], aspect)[0] >= 1.4 else 2


class QuietLog:

    def info(self, message):
        pass

    def warn(self, message):
        pass


def suggest_paper(params, grid, fonts, G):
    """Lay the page out on every paper for real and suggest the smallest one
    where the letters are readable.
    Returns (paper, {paper: (char_mm, orientation, k)})."""
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


def ask_paper(params, grid, fonts, G, ask_user, log):
    """Print the table and let the user choose. Not asked with --formato/--format
    or without a terminal: then it's --formato, the saved one or the suggestion."""
    suggested, options = suggest_paper(params, grid, fonts, G)
    aspect = fonts[3]
    log.info(tr("info_paper_intro", c=grid.cols, r=grid.rows))
    rows = []
    for paper, (char_mm, orientation, k) in options.items():
        if char_mm < SMALL_CHAR_MM:
            verdict = tr("v_too_small")
        elif char_mm < GOOD_CHAR_MM:
            verdict = tr("v_small")
        else:
            verdict = tr("v_good")
        note = tr("suggested") if paper == suggested else ""
        hexes = tr("hexes_large") if k == 3 else tr("hexes_small")
        # flat-to-flat = 2k lines
        hex_mm = 2 * k * aspect * char_mm
        log.info(tr("info_paper_option", paper=paper, o=pick(ORIENTATION_NAMES[orientation]), hexes=hexes,
                    hex_mm=hex_mm, mm=char_mm, v=verdict, note=note))
        rows.append(tr("paper_menu_option", paper=paper, o=pick(ORIENTATION_NAMES[orientation]), hexes=hexes,
                       hex_mm=hex_mm, mm=char_mm, v=verdict, note=tr("suggested_short") if note else ""))
    default = params.get("paper") or suggested
    if ask_user and menus_available():
        # the table itself is the menu; the line above it tells what it is
        print()
        papers = list(options)
        return papers[menu(tr("q_paper_menu"), rows, papers.index(default),
                           [tr("info_paper_intro", c=grid.cols, r=grid.rows)])]
    if ask_user:
        print()
        print(tr("paper_choice"))
        while True:
            answer = input(tr("q_paper", default=default)).strip().upper()
            if not answer:
                return default
            if answer in PAPERS:
                return answer
            print(tr("paper_retry"))
    return default


def render(canvas, regular, bold, char_w, char_h, size, width, height, ox, oy, progress=None, palette=MONO):
    """Rasterise the canvas. progress(fraction) is called after each row."""
    img = Image.new(palette["mode"], (width, height), palette["paper"])
    d = ImageDraw.Draw(img)
    for points, tag in canvas.fills:
        if tag in palette:
            d.polygon([(ox + x * char_w, oy + y * char_h) for x, y in points], fill=palette[tag])
    paper, sea = palette["paper"], palette["sea"]
    sea_hexes = bg(SEA) in palette            # the sea is filled hex by hex, like the land

    def ink(tag):
        return palette.get(tag, palette["ink"])

    thicken = max(1, size // 22)                 # shift used to fake a bold letter
    real_bold = bold is not None and bold is not regular
    probe = bold.font_variant(size=40) if real_bold else None
    bold_can_draw = {}                           # remembers which symbols the bold font has

    def draw_bold(px, py, ch, fill):
        # Menlo Bold (macOS) has no ═║╔╗: it drew empty boxes for the rivers.
        # Fake bold with the regular font drawn twice instead.
        if real_bold:
            if ch not in bold_can_draw:
                bold_can_draw[ch] = ch.isascii() or font_has_glyph(probe, ch)
            if bold_can_draw[ch]:
                d.text((px, py), ch, font=bold, fill=fill, anchor="la")
                return
        d.text((px, py), ch, font=regular, fill=fill, anchor="la")
        d.text((px + thicken, py), ch, font=regular, fill=fill, anchor="la")

    for y in range(canvas.height):
        py = oy + y * char_h
        for x in range(canvas.width):
            ch, style, tag = canvas.chars[y][x], canvas.styles[y][x], canvas.tags[y][x]
            if style == "B" or (ch == " " and style not in "igGH"):
                continue
            px = ox + x * char_w
            if style in "gGH":
                if not sea_hexes:      # with sea hexagons the squares would stick out at the map edge
                    d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=sea)
                if style == "G":
                    d.text((px, py), ch, font=regular, fill=ink(tag), anchor="la")
                elif style == "H":
                    draw_bold(px, py, ch, ink(tag))
                continue
            if style == "i":
                # the [ ] only make sense in the .txt
                d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=ink(tag))
                if ch not in "[] ":
                    d.text((px, py), ch, font=regular, fill=paper, anchor="la")
            elif style == "b":
                draw_bold(px, py, ch, ink(tag))
            else:
                d.text((px, py), ch, font=regular, fill=ink(tag), anchor="la")
        if progress:
            progress((y + 1) / canvas.height)
    big = regular.font_variant(size=int(size * 1.7))
    for bx, by, bw, bh, g, tag in canvas.boxes:
        x1, y1 = ox + bx * char_w, oy + by * char_h
        d.rectangle([x1, y1, x1 + bw * char_w, y1 + bh * char_h], fill=ink(tag))
        d.text((x1 + bw * char_w / 2, y1 + bh * char_h / 2), g, font=big, fill=paper, anchor="mm")
    return img


def save_png(img, path, settings=None):
    """Every PNG goes through here: it must be exactly A4/A3/A2 at 600 dpi.
    The settings ride along in an iTXt chunk so the map can be rebuilt."""
    if img.size not in VALID_SIZES:
        raise ValueError(tr("err_size", path=path, size=img.size))
    info = PngInfo()
    if settings:
        # seed is in the file name already
        data = {k: v for k, v in settings.items() if k not in ("output", "seed")}
        info.add_itxt(SETTINGS_KEY, json.dumps(data, ensure_ascii=False))
    # no optimize=True: way too slow on an A2
    img.save(path, dpi=(DPI, DPI), pnginfo=info)


def save(canvas, layout, png_path, settings=None):
    regular, bold, char_w, char_h, size, width, height, work_w, work_h, ox, oy = layout
    live = LiveBar()
    drawing = tr("pb_drawing")
    # drawing is ~90% of the time
    palette = palette_for(settings or {})
    img = render(canvas, regular, bold, char_w, char_h, size, work_w, work_h, ox, oy,
                 progress=lambda done: live.update(0.9 * done, drawing), palette=palette)
    if (work_w, work_h) != (width, height):
        f = min(width / work_w, height / work_h)
        smaller = img.resize((round(work_w * f), round(work_h * f)), Image.LANCZOS)
        img = Image.new(palette["mode"], (width, height), palette["paper"])
        img.paste(smaller, ((width - smaller.width) // 2, (height - smaller.height) // 2))
    live.update(0.9, tr("pb_saving"))
    save_png(img, png_path, settings)
    with open(png_path[:-4] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(canvas.lines()) + "\n")
    live.finish()


def page_layout(params, grid, k, paper, seed, font_spec, bold_spec, advance_em, aspect, G, log):
    """Letter size, page size and positions for this paper.
    Returns what save() and compose_page() need."""
    map_w, map_h = map_size(grid.cols, grid.rows, k)
    # legend lines depend on page width and vice versa: iterate until stable
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
        legend = pack_legend(G, n_cols - 4, has_farmland(params), has_backgrounds(params))
        if len(legend) <= legend_guess and n_rows >= map_h + len(legend) + 7:
            break
        legend_guess = max(len(legend), legend_guess + 1)
    values = dict(scale=params["scale"], dot=G("·", "-"), c=grid.cols, x=G("×", "x"), r=grid.rows, seed=seed)
    versions = [tr(key, **values) for key in ("subtitle", "subtitle_tight", "subtitle_short", "subtitle_seed")]
    subtitle = next((v for v in versions if len(v) + 4 <= n_cols), versions[-1])
    legend = pack_legend(G, n_cols - 4, has_farmland(params), has_backgrounds(params))
    # still doesn't fit (very long title?): grow the page, save() shrinks it back
    legend_width = max(sum(len(t) for entry in line for t, _, _ in entry) + 4 * (len(line) - 1) for line in legend)
    need_cols = max(n_cols, map_w + 4, len(params["title"]) + 8, len(subtitle) + 4, legend_width + 4)
    need_rows = max(n_rows, map_h + len(legend) + 7)
    work_w, work_h, shrink = width, height, 1.0
    if need_cols > n_cols or need_rows > n_rows:
        n_cols, n_rows = need_cols, need_rows
        work_w = max(width, round(n_cols * char_w + 2 * mm(MARGIN_MM)))
        work_h = max(height, round(n_rows * char_h + 2 * mm(MARGIN_MM)))
        shrink = min(width / work_w, height / work_h)
        log.warn(tr("warn_shrink", p=shrink, paper=paper))
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


# --- editor ---
# Edits are kept as the final state (terrain overrides, all sites, all rivers)
# in <seed>_edit.json next to the map, and in the edited PNGs. The seed alone
# still gives the original map.
SITE_KEYS = {DUNGEON: ("ed_a_dungeon", "ed_the_dungeon"), CITY: ("ed_a_city", "ed_the_city"),
             FORTRESS: ("ed_a_fortress", "ed_the_fortress")}
TERRAIN_ORDER = (PLAINS, SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT)


def direction(a, b):
    """Index into ed_dirs (N, NE, SE, S, SW, NW) of neighbour b as seen from a."""
    dx = b[0] - a[0]
    dy = (b[1] + 0.5 * (b[0] & 1)) - (a[1] + 0.5 * (a[0] & 1))
    if dx == 0:
        return 0 if dy < 0 else 3
    if dx > 0:
        return 1 if dy < 0 else 2
    return 5 if dy < 0 else 4


def river_direction(grid, river, h):
    """Where the river goes from hex h: index into ed_dirs, or None."""
    path, (kind, target) = river["path"], river["end"]
    i = path.index(h)
    if i + 1 < len(path):
        return direction(h, path[i + 1])
    if kind in ("water", "join"):
        return direction(h, target)
    if kind == "edge" and len(path) > 1:     # it keeps going straight off the map
        return direction(path[-2], h)
    return None


def parse_hex(text, grid):
    """'03.07', '3.7' or '0307' -> (2, 6). None if it's not a hex of this grid."""
    text = text.strip().replace(",", ".")
    if "." in text:
        parts = text.split(".")
    elif text.isdigit() and len(text) == 4:
        parts = [text[:2], text[2:]]
    else:
        return None
    try:
        c, r = (int(p) - 1 for p in parts)
    except ValueError:
        return None
    return (c, r) if grid.inside((c, r)) else None


def show_hex(h):
    return f"{h[0] + 1:02d}.{h[1] + 1:02d}"


def print_hex_table(grid, terrain, rivers, sites, only=None):
    """only: the hexes to list (None = all of them)."""
    head = pick(TEXTS["ed_columns"])
    yes, dirs = tr("ed_yes"), pick(TEXTS["ed_dirs"])
    site_at = {h: kind for kind, h in sites}
    rows = []
    for c in range(grid.cols):
        for r in range(grid.rows):
            h = (c, r)
            if only is not None and h not in only:
                continue
            river = next((rv for rv in rivers if h in rv["path"]), None)
            d = river_direction(grid, river, h) if river else None
            rows.append((show_hex(h), pick(TERRAIN_NAMES[terrain[h]]),
                         yes if site_at.get(h) == DUNGEON else "-",
                         yes if site_at.get(h) == CITY else "-",
                         yes if river else "-",
                         dirs[d] if d is not None else "-",
                         yes if site_at.get(h) == FORTRESS else "-"))
    widths = [max(len(x) for x in col) for col in zip(head, *rows)]
    line = lambda cells: "  " + "  ".join(f"{x:<{w}}" for x, w in zip(cells, widths)).rstrip()
    print()
    print(line(head))
    print(line(["-" * w for w in widths]))
    for row in rows:
        print(line(row))


def joins_back(rivers, start, river):
    """True if joining the river that runs through hex start would bring the
    water back into river (A into B into A)."""
    seen, at = [], start
    while True:
        rv = next((x for x in rivers if at in x["path"]), None)
        if rv is river:
            return True
        if rv is None or any(rv is x for x in seen):
            return False
        seen.append(rv)
        kind, at = rv["end"]
        if kind != "join":
            return False


def fix_river_end(grid, terrain, river, rivers):
    """After an edit, make sure the river still ends somewhere that makes sense."""
    last = river["path"][-1]
    around = grid.neighbours(last)
    others = {h for rv in rivers if rv is not river for h in rv["path"]}

    def can_join(h):
        return h in others and not joins_back(rivers, h, river)

    kind, target = river["end"]
    if kind == "water" and target in around and terrain[target] in WATER:
        return
    if kind == "join" and target in around and can_join(target):
        return
    water = [nb for nb in around if terrain[nb] in WATER]
    joins = [nb for nb in around if can_join(nb)]
    if water:
        river["end"] = ("water", water[0])
    elif kind == "edge" and grid.on_edge(last):
        return              # still runs off the map: a river passing by doesn't change that
    elif joins:
        river["end"] = ("join", joins[0])
    elif grid.on_edge(last):
        river["end"] = ("edge", None)
    else:
        river["end"] = ("stop", None)


def end_text(river):
    """'flows into water', 'ends at 03.07 without reaching water'..."""
    kind = river["end"][0]
    if kind == "stop":
        return tr("river_stop", h=show_hex(river["path"][-1]))
    return tr("river_" + kind)


def end_notes(old_rivers, rivers):
    """Rivers that weren't touched but end differently now (their water was
    filled in, the river they joined was removed...)."""
    old = {tuple(rv["path"]): rv["end"][0] for rv in old_rivers}
    return [tr("ed_end_note", h=show_hex(rv["path"][0]), how=end_text(rv)) for rv in rivers
            if old.get(tuple(rv["path"]), rv["end"][0]) != rv["end"][0]]


# heights for terrain nobody has on the original map
TYPICAL_HEIGHT = {MOUNTAINS: 0.95, HILLS: 0.75, SEA: 0.05, LAKE: 0.1}


def edited_heights(height, original, terrain):
    """A hex whose terrain was changed gets the usual height of its new terrain
    on this map, so a new river runs down from a new mountain."""
    typical = {}
    for t in TERRAIN_ORDER:
        values = [height[h] for h in height if original[h] == t]
        typical[t] = sum(values) / len(values) if values else TYPICAL_HEIGHT.get(t, 0.45)
    return {h: height[h] if terrain[h] == original[h] else typical[terrain[h]] for h in height}


def move_river_piece(grid, terrain, rivers, river, i, target):
    """Bend the river so that its i-th hex becomes target. Returns an error key or None."""
    path = river["path"]
    if terrain[target] in WATER:
        return "ed_why_water"
    if any(target in rv["path"] for rv in rivers):
        return "ed_why_river"
    before, after = path[:i], path[i + 1:]

    def bridge(a, b):
        # hexes to put between a and b so they touch; [] if they already do
        if b in grid.neighbours(a):
            return []
        common = [n for n in grid.neighbours(a) if b in grid.neighbours(n)
                  and n != path[i] and terrain[n] not in WATER and n not in path]
        return [common[0]] if common else None

    left = bridge(before[-1], target) if before else []
    right = bridge(target, after[0]) if after else []
    if left is None or right is None:
        return "ed_why_break"
    new_path = before + left + [target] + right + after
    if len(set(new_path)) != len(new_path):
        return "ed_why_break"
    river["path"] = new_path
    fix_river_end(grid, terrain, river, rivers)
    return None


def choose(title, options, default=1, context=()):
    """The editor's menus: index (0-based) of the answer. default is 1-based."""
    return menu(title, options, default - 1, context)


def edits_to_json(original, terrain, rivers, sites):
    code = lambda h: hex_code(h, 2)
    return {"terrain": {code(h): t for h, t in terrain.items() if t != original[h]},
            "sites": [[kind, code(h)] for kind, h in sites],
            "rivers": [{"path": [code(h) for h in rv["path"]],
                        "end": [rv["end"][0], code(rv["end"][1]) if rv["end"][1] else None]} for rv in rivers]}


def edits_from_json(data, grid, terrain):
    """Returns (terrain, rivers, sites, skipped) with the saved edits applied.
    The file may have been changed by hand: entries that don't make sense
    (a hex off the map, a city on the sea, a river with a gap) are skipped and
    counted. Raises ValueError if it isn't an edits file at all."""
    if not isinstance(data, dict):
        raise ValueError("not an edits file")
    parts = [data.get(key, empty) for key, empty in (("terrain", {}), ("sites", []), ("rivers", []))]
    if not (isinstance(parts[0], dict) and isinstance(parts[1], list) and isinstance(parts[2], list)):
        raise ValueError("not an edits file")
    new_terrain, site_list, river_list = parts
    skipped = 0

    def hx(code):
        if not (isinstance(code, str) and len(code) == 4 and code.isdigit()):
            raise ValueError(code)
        h = (int(code[:2]) - 1, int(code[2:]) - 1)
        if not grid.inside(h):
            raise ValueError(code)
        return h

    terrain = dict(terrain)
    for code, t in new_terrain.items():
        try:
            if t not in TERRAIN_NAMES:
                raise ValueError(t)
            terrain[hx(code)] = t
        except (TypeError, ValueError):
            skipped += 1

    sites = []
    for entry in site_list:
        try:
            kind, code = entry
            h = hx(code)
            if kind not in SITE_KEYS or terrain[h] in WATER or any(h == at for _, at in sites):
                raise ValueError(entry)
            sites.append((kind, h))
        except (TypeError, ValueError):
            skipped += 1

    rivers, busy = [], set()
    for entry in river_list:
        try:
            path = [hx(code) for code in entry["path"]]
            kind, target = entry["end"]
            target = hx(target) if target is not None else None
            ok = (len(path) >= 2 and len(set(path)) == len(path) and not busy & set(path)
                  and all(terrain[h] not in WATER for h in path)
                  and all(b in grid.neighbours(a) for a, b in zip(path, path[1:]))
                  and kind in ("water", "join", "edge", "stop"))
            if not ok:
                raise ValueError(entry)
            rivers.append({"path": path, "end": (kind, target)})
            busy.update(path)
        except (TypeError, ValueError, KeyError):
            skipped += 1
    for rv in rivers:
        fix_river_end(grid, terrain, rv, rivers)
    return terrain, rivers, sites, skipped


def load_edits(edit_base):
    """Saved edits for this map: from <seed>_edit.json or, if that's gone, from
    the edited PNG. Returns (edits, "json" | "png"), (None, None) when there are
    none, or (None, "bad") when the json is there but isn't valid JSON."""
    bad = False
    if os.path.exists(edit_base + ".json"):
        try:
            with open(edit_base + ".json", encoding="utf-8") as f:
                return json.load(f), "json"
        except (OSError, ValueError):
            bad = True
    for name in (edit_base + "_nonumber.png", edit_base + "_number.png"):
        try:
            with Image.open(name) as img:
                edits = json.loads(img.info.get(SETTINGS_KEY, "{}")).get("edits")
        except (OSError, ValueError, AttributeError):
            continue
        if edits:
            return edits, "png"
    return (None, "bad") if bad else (None, None)


def has_edits(edit_base):
    return load_edits(edit_base)[1] is not None


def set_aside(path):
    """Rename a broken edits file instead of writing over it: whatever was
    typed in it by hand is still there. Returns the new name."""
    stem, n = path[:-len(".json")], 1
    new = f"{stem}_broken.json"
    while os.path.exists(new):
        n += 1
        new = f"{stem}_broken{n}.json"
    os.replace(path, new)
    return new


def edit_labels(data):
    """The site names kept in an edits file, or None if it has none."""
    saved = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(saved, dict):
        return None
    return {key: name.strip()[:MAX_LABEL] for key, name in saved.items()
            if isinstance(key, str) and isinstance(name, str) and name.strip()}


def save_edit_labels(edit_base, labels):
    """Put the site names into <seed>_edit.json, where the editor finds them."""
    try:
        with open(edit_base + ".json", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        data["labels"] = labels
        with open(edit_base + ".json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except (OSError, ValueError):
        pass                 # a broken file is the editor's business, next time it opens


def snapshot(terrain, rivers, sites):
    return dict(terrain), [{"path": list(rv["path"]), "end": rv["end"]} for rv in rivers], list(sites)


def restore(state, terrain, rivers, sites):
    t, rv, st = snapshot(*state)
    terrain.clear()
    terrain.update(t)
    rivers[:] = rv
    sites[:] = st


def edit_map(grid, terrain, rivers, sites, height, edit_base, labels=None, fertile=()):
    """The interactive editor. Returns the edited (terrain, rivers, sites, edits,
    on_map), or None if the user quits without making the map. on_map is True
    when it was the editor drawn in the terminal, where the sites get their
    names too: labels ({"CCRR": name}) is changed in place. The edits are
    written to <seed>_edit.json after every change, so nothing is lost on Ctrl+C."""
    labels = {} if labels is None else labels
    original = dict(terrain)
    unedited = (original, snapshot(terrain, rivers, sites)[1])     # to draw what wasn't touched as before
    terrain, rivers, sites = snapshot(terrain, rivers, sites)
    print(tr("ed_header"))
    resumed = False
    def put_aside():
        # unusable, but don't write over a file someone may have typed by hand
        new = set_aside(edit_base + ".json")
        print(tr("ed_moved_bad", path=short_path(edit_base + ".json"), new=os.path.basename(new)))

    data, source = load_edits(edit_base)
    if source != "json" and os.path.exists(edit_base + ".json"):
        put_aside()
    if data is not None:
        prompt = tr("ed_resume") if source == "json" else tr("ed_resume_png")
        if not input(prompt).strip().lower().startswith("n"):
            try:
                terrain, rivers, sites, skipped = edits_from_json(data, grid, terrain)
                resumed = True
                saved_labels = edit_labels(data)
                if saved_labels is not None:           # the names as they were in the editor last time
                    labels.clear()
                    labels.update(saved_labels)
                if skipped:
                    print(tr("ed_dropped", n=skipped))
            except ValueError:
                if source == "json":
                    put_aside()
                print(tr("ed_bad_edits"))
    elif source == "bad":
        print(tr("ed_start_over"))

    def save_edits():
        data = edits_to_json(original, terrain, rivers, sites)
        data["labels"] = labels
        with open(edit_base + ".json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def undo():
        """False if there's nothing to undo."""
        if not history:
            return False
        state, old_labels = history.pop()
        restore(state, terrain, rivers, sites)
        labels.clear()
        labels.update(old_labels)
        save_edits()
        return True

    def show(focus=None, full=False):
        if full or len(grid.hexes) <= 80:
            print_hex_table(grid, terrain, rivers, sites)
            return
        shown = {h for h in grid.hexes if terrain[h] != original[h]}
        shown |= {h for _, h in sites} | {h for rv in rivers for h in rv["path"]}
        near = ""
        if focus:
            shown |= {focus, *grid.neighbours(focus)}
            near = tr("ed_near", h=show_hex(focus))
        print(tr("ed_shown", near=near, n=len(shown), total=len(grid.hexes)))
        print_hex_table(grid, terrain, rivers, sites, only=shown)

    def quit_editor():
        if history or resumed:      # every change is already on disk
            print(tr("ed_quit", path=short_path(edit_base + ".json")))
        else:
            print(tr("ed_quit_nothing"))
        return None

    history, focus = [], None       # history: (snapshot, labels) before each change
    if menus_available():
        editor = VisualEditor(grid, terrain, rivers, sites, height, unedited, labels, fertile,
                              os.path.basename(edit_base)[:-len("_edit")], history, save_edits, undo)
        outcome = editor.run()
        if outcome != "small":
            if editor.log:              # the full screen is gone: leave a trace of what was done
                print(tr("ve_log"))
                for line in editor.log:
                    print(f"    {line}")
            if outcome == "quit":
                return quit_editor()
            save_edits()
            return terrain, rivers, sites, edits_to_json(original, terrain, rivers, sites), True
        print(tr("ve_too_small", w=VE_MIN_SIZE[0], h=VE_MIN_SIZE[1]))
    last = show_hex((grid.cols - 1, grid.rows - 1))
    show()
    ask_next = resumed           # picked up old edits: maybe they just want the map again
    while True:
        if ask_next:
            options = [tr("ed_next_more"), tr("ed_next_go"), tr("ed_next_undo"), tr("ed_next_quit")]
            print()
            answer = choose(tr("ed_next"), options)
            if answer == 1:
                break
            if answer == 3:
                return quit_editor()
            if answer == 2:
                if undo():
                    print(tr("ed_undone"))
                    show(focus)
                else:
                    print(tr("ed_nothing_to_undo"))
                continue
        ask_next = False
        answer = input(tr("ed_ask_hex")).strip().lower()
        if answer == "t":
            show(full=True)
            continue
        if answer in ("a", "u"):
            ask_next = True
            if undo():
                print(tr("ed_undone"))
                show(focus)
            else:
                print(tr("ed_nothing_to_undo"))
            continue
        if answer in ("e", "q"):
            return quit_editor()
        h = parse_hex(answer, grid)
        if not h:
            print(tr("ed_bad_hex", last=last))
            continue
        before = snapshot(terrain, rivers, sites)
        edit_hex(grid, terrain, rivers, sites, edited_heights(height, original, terrain), h)
        if snapshot(terrain, rivers, sites) != before:
            for note in end_notes(before[1], rivers):
                print(note)
            history.append((before, dict(labels)))
            save_edits()
        else:
            print(tr("ed_no_change"))
        focus = h
        show(focus)
        ask_next = True
    save_edits()
    return terrain, rivers, sites, edits_to_json(original, terrain, rivers, sites), False


def trace_by_hand(grid, terrain, rivers, spring):
    """Ask for the hexes of a new river, one after the other. A sea or lake hex
    at the end makes it flow into the water, a hex of another river makes it
    join that one. Returns the river, or None if the user gives up."""
    busy = {h for rv in rivers for h in rv["path"]}
    # an example made of real neighbours, so it can be typed as it is
    step = next((n for n in grid.neighbours(spring) if terrain[n] not in WATER and n not in busy), None)
    after = next((n for n in grid.neighbours(step) if n != spring and n not in grid.neighbours(spring)),
                 None) if step else None
    example = " ".join(show_hex(x) for x in (step, after) if x) or show_hex(spring)
    prompt = tr("ed_ask_path", h=show_hex(spring), example=example)
    while True:
        answer = input(prompt).strip()
        prompt = tr("ed_ask_path_again", h=show_hex(spring))
        if not answer:
            return None
        words = answer.replace(";", " ").split()
        if parse_hex(words[0], grid) == spring:
            words = words[1:]            # they typed the spring too
        path, end, error = [spring], None, None
        for word in words:
            h = parse_hex(word, grid)
            if h is None:
                error = tr("ed_path_bad_hex", x=word)
            elif end:
                error = tr("ed_path_after_end", h=show_hex(end[1]))
            elif h in path:
                error = tr("ed_path_twice", h=show_hex(h))
            elif h not in grid.neighbours(path[-1]):
                error = tr("ed_path_not_near", a=show_hex(path[-1]), b=show_hex(h))
            elif terrain[h] in WATER:
                end = ("water", h)
            elif h in busy:
                end = ("join", h)
            else:
                path.append(h)
            if error:
                break
        if not error and len(path) < 2:
            error = tr("ed_path_short", h=show_hex(spring))
        if not error:
            return {"path": path, "end": end or ("stop", None)}
        print(error)


class TextEditorUI:
    """edit_hex's questions as numbered menus and typed answers."""

    def intro(self, text):
        print(text)

    def choose(self, title, options, default=1, context=()):
        return choose(title, options, default, context)

    def say(self, text):
        print(text)

    def confirm(self, question):
        return not input(question).strip().lower().startswith("n")

    def trace(self, grid, terrain, rivers, spring):
        return trace_by_hand(grid, terrain, rivers, spring)


def edit_hex(grid, terrain, rivers, sites, height, h, ui=None, action=None):
    """One change to hex h. ui asks the questions (TextEditorUI or the
    VisualEditor): its choose() returns None when the user backs out.
    action: already chosen with a key ("terrain", "river" or a site kind)."""
    ui = ui or TextEditorUI()
    name = show_hex(h)
    site = next((kind for kind, at in sites if at == h), None)
    river = next((rv for rv in rivers if h in rv["path"]), None)
    desc = pick(TERRAIN_NAMES[terrain[h]])
    if site:
        desc += ", " + pick(SITE_NAMES[site]).lower()
    if river:
        d = river_direction(grid, river, h)
        desc += ", " + pick(TEXTS["ed_columns"])[4].lower()
        if d is not None:
            desc += " → " + pick(TEXTS["ed_dirs"])[d]
    ui.intro(tr("ed_hex_is", h=name, desc=desc))
    here = [tr("ed_hex_is", h=name, desc=desc)]     # the menu screen hides the log: say which hex
    actions = [("terrain", tr("ed_terrain"))]
    for kind in (DUNGEON, CITY, FORTRESS):
        a, the = SITE_KEYS[kind]
        actions.append((kind, tr("ed_remove", what=tr(the)) if site == kind else tr("ed_add", what=tr(a))))
    actions.append(("river", tr("ed_river_piece") if river else tr("ed_add_river")))
    actions.append(("nothing", tr("ed_nothing")))
    if action is None:
        answer = ui.choose(tr("ed_what"), [text for _, text in actions], len(actions), here)
        if answer is None:
            return
        action = actions[answer][0]
    done = []

    if action == "terrain":
        answer = ui.choose(tr("ed_which_terrain"), [pick(TERRAIN_NAMES[t]) for t in TERRAIN_ORDER],
                           TERRAIN_ORDER.index(terrain[h]) + 1, here)
        if answer is None:
            return
        new = TERRAIN_ORDER[answer]
        terrain[h] = new
        done.append(tr("ed_did_terrain", h=name, t=pick(TERRAIN_NAMES[new])))
        if new in WATER:
            if site:
                sites.remove((site, h))
                done.append(tr("ed_lost_site", what=tr(SITE_KEYS[site][1]), h=name))
            if river:
                i = river["path"].index(h)
                if i < 2:                        # nothing left upstream worth keeping
                    rivers.remove(river)
                    done.append(tr("ed_did_river_del", h=name))
                else:
                    river["path"], river["end"] = river["path"][:i], ("water", h)
                    done.append(tr("ed_cut_river", h=name))
        for rv in rivers:
            fix_river_end(grid, terrain, rv, rivers)

    elif action in SITE_KEYS:
        a, the = SITE_KEYS[action]
        if site == action:
            sites.remove((site, h))
            done.append(tr("ed_did_remove", what=tr(the), h=name))
        elif terrain[h] in WATER:
            ui.say(tr("ed_no_water_site"))
        else:
            if site:
                sites.remove((site, h))
                done.append(tr("ed_did_replace", old=tr(SITE_KEYS[site][1]), h=name, what=tr(a)))
            else:
                done.append(tr("ed_did_add", what=tr(a), h=name))
            sites.append((action, h))

    elif action == "river" and river:
        how = ui.choose(tr("ed_river_how"), [tr("ed_river_all"), tr("ed_river_move"), tr("ed_river_cut_end"),
                                             tr("ed_river_cut_start")], 1, here)
        if how is None:
            return
        i = river["path"].index(h)
        if how == 0:
            rivers.remove(river)
            for rv in rivers:
                fix_river_end(grid, terrain, rv, rivers)
            done.append(tr("ed_did_river_del", h=name))
        elif how in (2, 3):
            path = river["path"][:i + 1] if how == 2 else river["path"][i:]
            if len(path) < 2:
                ui.say(tr("ed_too_short"))
            else:
                river["path"] = path
                for rv in rivers:
                    fix_river_end(grid, terrain, rv, rivers)
                if how == 2:
                    how_end = {"water": tr("ed_into_water"), "edge": tr("ed_off_map"), "join": tr("ed_into_river"),
                               "stop": tr("ed_no_water_end")}[river["end"][0]]
                    done.append(tr("ed_did_cut_end", h=name, how=how_end))
                else:
                    done.append(tr("ed_did_cut_start", h=name))
        else:
            dirs = pick(TEXTS["ed_dirs"])
            # the hexes the river already comes from and goes to are not a move
            path = river["path"]
            used = set(path[max(0, i - 1):i]) | set(path[i + 1:i + 2])
            if i == len(path) - 1 and river["end"][1]:
                used.add(river["end"][1])
            around = sorted((direction(h, n), n) for n in grid.neighbours(h) if n not in used)
            if not around:
                ui.say(tr("ed_no_dirs"))
            else:
                answer = ui.choose(tr("ed_which_dir"), [dirs[d] for d, _ in around], 1, here)
                if answer is None:
                    return
                _, target = around[answer]
                why = move_river_piece(grid, terrain, rivers, river, i, target)
                if why:
                    ui.say(tr("ed_no_move", why=tr(why)))
                else:
                    for rv in rivers:
                        fix_river_end(grid, terrain, rv, rivers)
                    done.append(tr("ed_did_river_move", h=show_hex(target), old=name))

    elif action == "river":
        if terrain[h] in WATER:
            ui.say(tr("ed_no_water_river"))
        else:
            new = None
            way = ui.choose(tr("ed_river_way"), [tr("ed_river_auto"), tr("ed_river_manual")], 1, here)
            if way is None:
                return
            if way == 0:
                busy = {x for rv in rivers for x in rv["path"]}
                path, end = follow_river(grid, terrain, height, h, busy, random.Random(f"river {h}"),
                                         grid.cols + grid.rows)
                if end and len(path) >= 2:
                    new = {"path": path, "end": end}
                else:
                    # usually a low hex: every way out goes uphill
                    ui.say(tr("ed_no_river_path"))
                    if ui.confirm(tr("ed_try_manual")):
                        new = ui.trace(grid, terrain, rivers, h)
            else:
                new = ui.trace(grid, terrain, rivers, h)
            if new:
                rivers.append(new)
                fix_river_end(grid, terrain, new, rivers)
                for rv in rivers:
                    fix_river_end(grid, terrain, rv, rivers)
                done.append(tr("ed_did_river_add", h=name, n=len(new["path"]), how=end_text(new)))

    for what in done:
        ui.say(tr("ed_done", what=what))


# --- the editor on the map ---
# The same editor, drawn in the terminal with asciimatics: the map itself with
# a cursor to move around, a panel with the hex under the cursor and one key
# per action. The actions are edit_hex's, asked in boxes over the map, so the
# two editors change the map in exactly the same way; the one with typed
# answers stays for when there's no terminal or it's too small.
VE_MIN_SIZE = (80, 24)
VE_PANEL = 34                    # columns on the right for the panel
VE_K = 2                         # hex size in the terminal: 10 letters wide, 5 high
VE_ASPECT = 2.0                  # a terminal letter is about twice as tall as it is wide
VE_PLAIN = str.maketrans({"×": "x", "–": "-", "—": "-", "·": "-", "→": "->", "↑": "^", "↓": "v",
                          "←": "<", "è": "e", "à": "a", "ì": "i", "ò": "o", "ù": "u", "é": "e"})


class VisualEditor:
    def __init__(self, grid, terrain, rivers, sites, height, unedited, labels, fertile, seed, history, save, undo):
        self.grid, self.terrain, self.rivers, self.sites = grid, terrain, rivers, sites
        self.height, self.unedited, self.labels, self.fertile = height, unedited, labels, set(fertile)
        self.seed, self.history, self.save, self.undo = seed, history, save, undo
        self.cursor = sites[0][1] if sites else (grid.cols // 2, grid.rows // 2)
        self.ox = self.oy = None         # top-left corner of the map in view
        self.messages = []               # in the panel until the next key
        self.log = []                    # everything done, printed when the editor closes
        self.canvas = None               # drawn again after every change
        self.screen = None

    # --- running ---
    def run(self):
        """"go" (make the map), "quit", or "small" if the terminal is too small."""
        from asciimatics.exceptions import ResizeScreenError
        from asciimatics.screen import Screen
        while True:
            try:
                return Screen.wrapper(self.main_loop)
            except ResizeScreenError:
                self.canvas = None              # the window changed size: draw it all again
                continue

    def main_loop(self, screen):
        from asciimatics.event import KeyboardEvent, MouseEvent
        from asciimatics.screen import Screen
        self.screen, self.S = screen, Screen
        if screen.width < VE_MIN_SIZE[0] or screen.height < VE_MIN_SIZE[1]:
            return "small"
        self.fancy = screen.unicode_aware
        while True:
            self.draw()
            screen.refresh()
            event = self.next_event()
            if isinstance(event, MouseEvent):
                if event.buttons & MouseEvent.LEFT_CLICK:
                    h = self.hex_at(event.x, event.y)
                    if h == self.cursor:
                        self.messages = []
                        self.act(None)          # a click on the hex already chosen: its actions
                    elif h:
                        self.move_to(h)
                continue
            if not isinstance(event, KeyboardEvent):
                continue
            key = event.key_code
            letter = chr(key).lower() if 0 < key < 0x110000 else ""
            if self.arrow(key):
                continue
            self.messages = []
            if key in (10, 13):
                self.act(None)
            elif letter == "t":
                self.act("terrain")
            elif letter and letter in "cfd":
                self.act({"c": CITY, "f": FORTRESS, "d": DUNGEON}[letter])
            elif letter == "r":
                self.act("river")
            elif letter == "n":
                self.name_site()
            elif letter in ("z", "u"):
                if self.undo():
                    self.canvas = None
                    self.say(tr("ed_undone"))
                else:
                    self.say(tr("ed_nothing_to_undo"))
            elif letter == "s":
                return "go"
            elif letter in ("q", "e"):
                if not self.history or self.confirm_box(tr("ve_quit_q"), tr("ve_quit_yes"), tr("ve_quit_no")):
                    return "quit"
            elif letter in ("?", "h"):
                self.help_box()

    def next_event(self):
        from asciimatics.exceptions import ResizeScreenError
        while True:
            self.screen.wait_for_input(0.5)
            event = self.screen.get_event()
            if self.screen.has_resized():
                raise ResizeScreenError("resized")
            if event is None:
                continue
            if getattr(event, "key_code", None) == 3:    # Ctrl+C, when the terminal hands it over as a key
                raise KeyboardInterrupt
            return event

    def arrow(self, key):
        """Move the cursor with the arrow keys. False if key isn't an arrow."""
        S = self.S
        steps = {S.KEY_LEFT: (-1, 0), S.KEY_RIGHT: (1, 0), S.KEY_UP: (0, -1), S.KEY_DOWN: (0, 1)}
        if key not in steps:
            return False
        h = (self.cursor[0] + steps[key][0], self.cursor[1] + steps[key][1])
        if self.grid.inside(h):
            self.move_to(h)
        return True

    def move_to(self, h):
        self.cursor = h
        self.messages = []

    # --- changes ---
    def act(self, action):
        terrain, rivers, sites = self.terrain, self.rivers, self.sites
        before = snapshot(terrain, rivers, sites)
        edit_hex(self.grid, terrain, rivers, sites, edited_heights(self.height, self.unedited[0], terrain),
                 self.cursor, self, action)
        if snapshot(terrain, rivers, sites) != before:
            for note in end_notes(before[1], rivers):
                self.say(note)
            self.history.append((before, dict(self.labels)))
            self.save()
            self.canvas = None

    def name_site(self):
        h = self.cursor
        kind = next((k for k, at in self.sites if at == h), None)
        if not kind:
            self.say(tr("ve_no_site"))
            return
        key = label_key(h)
        old = self.labels.get(key, "")
        title = tr("ve_name_title", site=pick(SITE_NAMES[kind]), h=show_hex(h), n=MAX_LABEL)
        name = self.text_box(title, old, MAX_LABEL)
        if name is None:
            return
        name = " ".join(name.split())
        if name == old:
            return
        before = (snapshot(self.terrain, self.rivers, self.sites), dict(self.labels))
        if name:
            self.labels[key] = name
            self.say(tr("ed_done", what=tr("ve_did_name", h=show_hex(h), name=name)))
        else:
            self.labels.pop(key, None)
            self.say(tr("ed_done", what=tr("ve_did_unname", h=show_hex(h))))
        self.history.append(before)
        self.save()
        self.canvas = None

    # --- what edit_hex asks ---
    def intro(self, text):
        pass                                    # the panel already says what's in the hex

    def say(self, text):
        text = text.strip()
        self.messages.append(text)
        self.log.append(text)

    def choose(self, title, options, default=1, context=()):
        return self.menu_box(title.strip(), options, default - 1)

    def confirm(self, question):
        question = re.sub(r"\s*\(\w/\w\):?\s*$", "", question.strip())     # the "(Y/n):" of the typed editor
        return self.confirm_box(question, tr("ve_yes"), tr("ve_no"), True)

    def trace(self, grid, terrain, rivers, spring):
        """The new river's hexes, picked one by one on the map."""
        from asciimatics.event import KeyboardEvent, MouseEvent
        busy = {h for rv in rivers for h in rv["path"]}
        path, problem = [spring], ""
        self.cursor = spring
        while True:
            self.draw(trace=(path, problem))
            self.screen.refresh()
            event = self.next_event()
            add = False
            if isinstance(event, MouseEvent):
                h = self.hex_at(event.x, event.y) if event.buttons & MouseEvent.LEFT_CLICK else None
                if h:
                    self.cursor, add = h, True
            elif isinstance(event, KeyboardEvent):
                key = event.key_code
                letter = chr(key).lower() if 0 < key < 0x110000 else ""
                if self.arrow(key):
                    continue
                problem = ""
                if key in (10, 13):
                    add = True
                elif key in (self.S.KEY_BACK, self.S.KEY_DELETE, 8, 127):
                    if len(path) > 1:
                        path.pop()
                        self.cursor = path[-1]
                elif key == self.S.KEY_ESCAPE:
                    self.cursor = spring
                    self.say(tr("ve_trace_cancel"))
                    return None
                elif letter == "f":
                    if len(path) >= 2:
                        self.cursor = spring
                        return {"path": path, "end": ("stop", None)}
                    problem = tr("ed_path_short", h=show_hex(spring))
            if not add:
                continue
            h, end = self.cursor, None
            if h in path:
                problem = tr("ed_path_twice", h=show_hex(h))
            elif h not in grid.neighbours(path[-1]):
                problem = tr("ed_path_not_near", a=show_hex(path[-1]), b=show_hex(h))
            elif terrain[h] in WATER:
                end = ("water", h)
            elif h in busy:
                end = ("join", h)
            else:
                path.append(h)
                problem = ""
            if end:
                if len(path) >= 2:
                    self.cursor = spring
                    return {"path": path, "end": end}
                problem = tr("ed_path_short", h=show_hex(spring))

    # --- drawing ---
    def plain(self, text):
        return text if self.fancy else text.replace("←↑↓→", "<^v>").translate(VE_PLAIN)

    def put(self, text, x, y, colour=None, attr=None, bg=None):
        S = self.S
        self.screen.print_at(self.plain(text), x, y, S.COLOUR_WHITE if colour is None else colour,
                             S.A_NORMAL if attr is None else attr, S.COLOUR_BLACK if bg is None else bg)

    def view_size(self):
        return self.screen.width - VE_PANEL - 3, self.screen.height - 4

    def redraw_map(self):
        G = lambda fancy, plain: fancy if self.fancy else plain
        self.canvas = draw_map(self.grid, self.terrain, self.rivers, self.sites, VE_K, G,
                               random.Random(len(self.grid.hexes)), VE_ASPECT, self.unedited, self.labels,
                               not self.fancy, self.fertile)
        self.heights = edited_heights(self.height, self.unedited[0], self.terrain)

    def scroll(self):
        """Move the view only when the cursor's hex would leave it."""
        view_w, view_h = self.view_size()
        x0, y0 = hex_origin(*self.cursor, VE_K)
        w, h = 4 * VE_K + 2, 2 * VE_K + 1
        if self.ox is None:                     # at first, the cursor in the middle
            self.ox, self.oy = x0 + w // 2 - view_w // 2, y0 + h // 2 - view_h // 2
        ox, oy = self.ox, self.oy
        if x0 < ox:
            ox = x0 - 3 * VE_K
        if x0 + w > ox + view_w:
            ox = x0 + w - view_w + 3 * VE_K
        if y0 < oy:
            oy = y0 - 2 * VE_K
        if y0 + h > oy + view_h:
            oy = y0 + h - view_h + 2 * VE_K
        self.ox = max(0, min(ox, self.canvas.width - view_w))
        self.oy = max(0, min(oy, self.canvas.height - view_h))

    def hex_at(self, x, y):
        """The hex under screen square (x, y), or None outside the map."""
        view_w, view_h = self.view_size()
        if not (1 <= x < 1 + view_w and 2 <= y < 2 + view_h) or self.ox is None:
            return None
        cx, cy = x - 1 + self.ox, y - 2 + self.oy
        if cx >= self.canvas.width or cy >= self.canvas.height:
            return None
        # nearest centre; a row is sqrt(3) times as far as a column step in a real hexagon
        def distance(h):
            x0, y0 = hex_origin(*h, VE_K)
            return (cx - x0 - 2 * VE_K - 0.5) ** 2 + 3 * (cy - y0 - VE_K) ** 2
        return min(self.grid.hexes, key=distance)

    def draw(self, trace=None):
        S, screen = self.S, self.screen
        if self.canvas is None:
            self.redraw_map()
        self.scroll()
        w, h = screen.width, screen.height
        screen.clear_buffer(S.COLOUR_WHITE, S.A_NORMAL, S.COLOUR_BLACK)
        self.put(tr("ve_title", v=VERSION).ljust(w), 0, 0, S.COLOUR_BLACK, S.A_BOLD, S.COLOUR_YELLOW)
        seed = tr("ve_seed", s=self.seed)
        self.put(seed, max(0, w - len(seed) - 2), 0, S.COLOUR_BLACK, S.A_NORMAL, S.COLOUR_YELLOW)
        self.draw_map_view(trace[0] if trace else ())
        for y in range(1, h - 1):
            self.put("│" if self.fancy else "|", w - VE_PANEL - 2, y)
        if trace:
            self.draw_trace_panel(*trace)
        else:
            self.draw_panel()
        bar = tr("ve_trace_bar" if trace else "ve_bar")
        self.put(self.plain(bar)[:w].ljust(w), 0, h - 1, S.COLOUR_BLACK, S.A_NORMAL, S.COLOUR_WHITE)

    def draw_map_view(self, marks):
        S, canvas = self.S, self.canvas
        view_w, view_h = self.view_size()
        ox, oy = self.ox, self.oy
        terrain_fg = {FOREST: S.COLOUR_GREEN, HILLS: S.COLOUR_YELLOW, MOUNTAINS: S.COLOUR_WHITE,
                      DESERT: S.COLOUR_YELLOW, LAKE: S.COLOUR_CYAN, SWAMP: S.COLOUR_MAGENTA,
                      FERTILE: S.COLOUR_GREEN, "river": S.COLOUR_BLUE, "label": S.COLOUR_WHITE}
        box_bg = {CITY: S.COLOUR_RED, FORTRESS: S.COLOUR_MAGENTA, DUNGEON: S.COLOUR_WHITE}
        box_fg = {CITY: S.COLOUR_WHITE, FORTRESS: S.COLOUR_WHITE, DUNGEON: S.COLOUR_BLACK}
        rows, cols = min(view_h, canvas.height - oy), min(view_w, canvas.width - ox)
        for y in range(rows):
            for x in range(cols):
                X, Y = ox + x, oy + y
                ch, style, tag = canvas.chars[Y][X], canvas.styles[Y][X], canvas.tags[Y][X]
                if style in "gGH":              # the sea: one blue sheet with a few waves
                    if tag == "label":
                        self.put(ch, 1 + x, 2 + y, S.COLOUR_WHITE, S.A_BOLD, S.COLOUR_BLUE)
                    else:
                        ch = ch if style != "g" else ("~" if (X + Y) % 3 == 0 else " ")
                        self.put(ch, 1 + x, 2 + y, S.COLOUR_CYAN, S.A_NORMAL, S.COLOUR_BLUE)
                elif ch != " " and style != "B":
                    colour = S.COLOUR_WHITE if tag == "border" else terrain_fg.get(tag, S.COLOUR_WHITE)
                    bold = style == "b" and tag != "border"
                    self.put(ch, 1 + x, 2 + y, colour, S.A_BOLD if bold else S.A_NORMAL)
        for bx, by, bw, bh, g, tag in canvas.boxes:     # sites: one big symbol on their colour
            for yy in range(bh):
                for xx in range(bw):
                    X, Y = bx + xx - ox, by + yy - oy
                    if 0 <= X < cols and 0 <= Y < rows:
                        self.put(g if xx in (1, 2) else " ", 1 + X, 2 + Y, box_fg[tag], S.A_BOLD, box_bg[tag])
        border, inside = hex_template(VE_K)
        for h in marks:                         # the new river's hexes
            self.highlight(h, inside, (), S.COLOUR_CYAN)
        self.highlight(self.cursor, inside, border, S.COLOUR_YELLOW)

    def highlight(self, h, inside, border, colour):
        """The hex's inside on colour (site boxes stay on top), its outline in colour."""
        S, canvas = self.S, self.canvas
        view_w, view_h = self.view_size()
        x0, y0 = hex_origin(*h, VE_K)
        for yy, xx in inside:
            X, Y = x0 + xx - self.ox, y0 + yy - self.oy
            if 0 <= X < view_w and 0 <= Y < view_h and canvas.styles[y0 + yy][x0 + xx] != "B":
                ch = canvas.chars[y0 + yy][x0 + xx]
                ch = " " if canvas.styles[y0 + yy][x0 + xx] == "g" else ch
                self.put(ch, 1 + X, 2 + Y, S.COLOUR_BLACK, S.A_BOLD, colour)
        for yy, xx, ch in border:
            X, Y = x0 + xx - self.ox, y0 + yy - self.oy
            if 0 <= X < view_w and 0 <= Y < view_h:
                if canvas.tags[y0 + yy][x0 + xx] == "label":    # a name on the border stays as it is
                    self.put(canvas.chars[y0 + yy][x0 + xx], 1 + X, 2 + Y, S.COLOUR_WHITE, S.A_BOLD)
                else:
                    self.put(ch, 1 + X, 2 + Y, colour, S.A_BOLD)

    def wrap(self, text, width):
        return textwrap.wrap(self.plain(text), width) or [""]

    def draw_panel(self):
        S, h = self.S, self.cursor
        px, bottom = self.screen.width - VE_PANEL, self.screen.height - 2
        site = next((k for k, at in self.sites if at == h), None)
        river = next((rv for rv in self.rivers if h in rv["path"]), None)
        kind = self.terrain[h]
        terrain = tr("ve_farmland") if kind == PLAINS and h in self.fertile else pick(TERRAIN_NAMES[kind])
        none = "—" if self.fancy else "-"
        if river:
            d = river_direction(self.grid, river, h)
            river = tr("ve_river_dir", d=pick(TEXTS["ed_dirs"])[d]) if d is not None else tr("ed_yes")
        values = (terrain, pick(SITE_NAMES[site]) if site else none,
                  (self.labels.get(label_key(h)) or none) if site else none,
                  river or tr("ve_no"), f"{self.heights[h]:.2f}")
        self.put(tr("ve_hex", h=show_hex(h)), px, 2, S.COLOUR_YELLOW, S.A_BOLD)
        y = 3
        for name, value in zip(pick(TEXTS["ve_rows"]), values):
            self.put(f"{name:<8}", px, y, S.COLOUR_CYAN)
            self.put(value[:VE_PANEL - 10], px + 9, y, S.COLOUR_WHITE, S.A_BOLD)
            y += 1
        y += 1
        self.put(tr("ve_actions"), px, y, S.COLOUR_YELLOW, S.A_BOLD)
        y += 1
        key, text = tr("ve_enter").split(" ", 1)
        self.put(f" {key} ", px, y, S.COLOUR_BLACK, S.A_BOLD, S.COLOUR_WHITE)
        self.put(text.strip(), px + len(key) + 3, y)
        y += 1
        keys = pick(TEXTS["ve_keys"])
        for i in range(0, len(keys), 2):
            for j, (key, text) in enumerate(keys[i:i + 2]):
                x = px + j * 17
                self.put(f" {key} ", x, y, S.COLOUR_BLACK, S.A_BOLD, S.COLOUR_WHITE)
                self.put(text[:12], x + 4, y)
            y += 1
        y += 1
        self.put(tr("ve_changes", n=len(self.history)), px, y)
        y += 2
        for message in self.messages:
            for piece in self.wrap(message, VE_PANEL - 1):
                if y < bottom:
                    self.put(piece, px, y, S.COLOUR_GREEN, S.A_BOLD)
                y += 1
        self.draw_view_line()

    def draw_trace_panel(self, path, problem):
        S = self.S
        px, bottom = self.screen.width - VE_PANEL, self.screen.height - 2
        self.put(tr("ve_trace_title", h=show_hex(path[0])), px, 2, S.COLOUR_YELLOW, S.A_BOLD)
        y = 4
        for piece in self.wrap(tr("ve_trace_help"), VE_PANEL - 1):
            self.put(piece, px, y, S.COLOUR_CYAN)
            y += 1
        y += 1
        self.put(tr("ve_trace_path", n=len(path)), px, y)
        y += 1
        arrow = " → " if self.fancy else " > "
        for piece in self.wrap(arrow.join(show_hex(h) for h in path), VE_PANEL - 1):
            if y < bottom - 3:
                self.put(piece, px, y, S.COLOUR_WHITE, S.A_BOLD)
            y += 1
        y += 1
        for piece in self.wrap(problem, VE_PANEL - 1) if problem else ():
            if y < bottom:
                self.put(piece, px, y, S.COLOUR_RED, S.A_BOLD)
            y += 1
        self.draw_view_line()

    def draw_view_line(self):
        """Under the map: which columns and rows are in view."""
        view_w, view_h = self.view_size()
        cols = [c for c in range(self.grid.cols)
                if hex_origin(c, 0, VE_K)[0] < self.ox + view_w and hex_origin(c, 0, VE_K)[0] + 4 * VE_K > self.ox]
        rows = [r for r in range(self.grid.rows)
                if 2 * VE_K * r < self.oy + view_h and 2 * VE_K * (r + 1) > self.oy]
        text = tr("ve_view", c=self.grid.cols, r=self.grid.rows, a=cols[0] + 1, b=cols[-1] + 1,
                  d=rows[0] + 1, e=rows[-1] + 1)
        self.put(self.plain(text)[:view_w], 1, self.screen.height - 2, self.S.COLOUR_WHITE)

    # --- boxes over the map ---
    def box(self, title, lines, width=None):
        """A framed box over the map, with room for lines. Returns (x, y, width) of its inside."""
        S = self.S
        view_w, _ = self.view_size()
        width = min(view_w - 2, max(width or 0, len(title) + 6, *(len(line) + 4 for line in lines)))
        height = len(lines) + 2
        x, y = max(1, (view_w - width) // 2), 3
        h_line, v_line, corners = ("─", "│", "┌┐└┘") if self.fancy else ("-", "|", "++++")
        self.put(corners[0] + h_line * (width - 2) + corners[1], x, y, S.COLOUR_YELLOW)
        for i in range(1, height - 1):
            self.put(v_line + " " * (width - 2) + v_line, x, y + i, S.COLOUR_YELLOW)
        self.put(corners[2] + h_line * (width - 2) + corners[3], x, y + height - 1, S.COLOUR_YELLOW)
        self.put(f" {title[:width - 6]} ", x + 2, y, S.COLOUR_YELLOW, S.A_BOLD)
        return x + 2, y + 1, width - 4

    def menu_box(self, title, options, current=0):
        """Index of the chosen option, or None for Esc."""
        from asciimatics.event import KeyboardEvent, MouseEvent
        S = self.S
        numbered = [self.plain(f" {i + 1}  {text} " if len(options) < 10 else f" {text} ")
                    for i, text in enumerate(options)]
        keys = self.plain(tr("ve_popup_keys"))
        while True:
            self.draw()
            x, y, width = self.box(self.plain(title), [""] + ["  " + text for text in numbered] + ["", keys])
            for i, text in enumerate(numbered):
                if i == current:
                    self.put("▶" if self.fancy else ">", x, y + 1 + i, S.COLOUR_YELLOW, S.A_BOLD)
                    self.put(text[:width - 2].ljust(width - 2), x + 2, y + 1 + i, S.COLOUR_BLACK, S.A_NORMAL,
                             S.COLOUR_YELLOW)
                else:
                    self.put(text[:width - 2], x + 2, y + 1 + i, S.COLOUR_WHITE)
            self.put(keys[:width], x, y + len(options) + 2, S.COLOUR_CYAN)
            self.screen.refresh()
            event = self.next_event()
            if isinstance(event, KeyboardEvent):
                key = event.key_code
                if key in (S.KEY_UP, ord("k")):
                    current = (current - 1) % len(options)
                elif key in (S.KEY_DOWN, ord("j"), S.KEY_TAB):
                    current = (current + 1) % len(options)
                elif key in (10, 13):
                    return current
                elif key == S.KEY_ESCAPE:
                    return None
                elif ord("1") <= key <= ord("9") and key - ord("1") < len(options):
                    return key - ord("1")
            elif isinstance(event, MouseEvent) and event.buttons & MouseEvent.LEFT_CLICK:
                if y + 1 <= event.y < y + 1 + len(options) and x <= event.x < x + width:
                    return event.y - y - 1

    def confirm_box(self, question, yes, no, yes_first=False):
        options = [yes, no] if yes_first else [no, yes]
        answer = self.menu_box(question, options)
        return answer is not None and options[answer] == yes

    def text_box(self, title, text, limit):
        """A line typed in a box: the text, or None for Esc."""
        from asciimatics.event import KeyboardEvent
        S = self.S
        keys = self.plain(tr("ve_text_keys"))
        while True:
            self.draw()
            x, y, width = self.box(self.plain(title), ["", " " * (limit + 2), "", keys], limit + 6)
            self.put(" " * (limit + 2), x, y + 1, S.COLOUR_BLACK, S.A_NORMAL, S.COLOUR_WHITE)
            self.put(text, x + 1, y + 1, S.COLOUR_BLACK, S.A_BOLD, S.COLOUR_WHITE)
            self.put("_" if len(text) < limit else " ", x + 1 + len(text), y + 1, S.COLOUR_BLACK, S.A_BOLD,
                     S.COLOUR_WHITE)
            self.put(keys[:width], x, y + 3, S.COLOUR_CYAN)
            self.screen.refresh()
            event = self.next_event()
            if not isinstance(event, KeyboardEvent):
                continue
            key = event.key_code
            if key in (10, 13):
                return text
            if key == S.KEY_ESCAPE:
                return None
            if key in (S.KEY_BACK, S.KEY_DELETE, 8, 127):
                text = text[:-1]
            elif 32 <= key < 0x110000 and chr(key).isprintable() and len(text) < limit:
                text += chr(key)

    def help_box(self):
        room = self.view_size()[0] - 6
        lines = [""]
        for line in pick(TEXTS["ve_help"]) + ("", tr("ve_any_key")):
            lines += self.wrap(line.format(file=f"{self.seed}_edit.json"), room)
        self.draw()
        x, y, width = self.box(self.plain(tr("ve_help_title")), lines)
        for i, line in enumerate(lines):
            self.put(line[:width], x, y + i, self.S.COLOUR_CYAN if i == len(lines) - 1 else self.S.COLOUR_WHITE)
        self.screen.refresh()
        self.next_event()


def save_maps(params, grid, land, look, seed, number, log, layout_log):
    """Steps 11-12: draw the page and save the two maps (PNG + TXT).
    land is (terrain, rivers, sites, original, fertile): original is the
    unedited (terrain, rivers) for an edited map, None otherwise; fertile the
    farmable plains (only drawn where the hex is still plains)."""
    terrain, rivers, sites, original, fertile = land
    font_spec, bold_spec, advance_em, aspect, G, paper, k = look
    label = f"{seed} {tr('ed_edited')}" if original else seed
    layout, n_cols, n_rows, legend, subtitle = page_layout(
        params, grid, k, paper, label, font_spec, bold_spec, advance_em, aspect, G, layout_log)

    # glyphs get their own rng, independent from the land's
    drawing_rng = random.Random(number + 1)
    map_canvas = draw_map(grid, terrain, rivers, sites, k, G, drawing_rng, aspect, original,
                          params.get("labels"), params["ascii_only"], fertile)
    page, mx, my = compose_page(map_canvas, n_cols, n_rows, legend, params["title"], subtitle, G)
    plain_path, numbered_path = output_names(params["output"], seed, "_edit" if original else "")

    log.step(tr("step_plain", paper=paper, dpi=DPI))
    save(page, layout, plain_path, params)
    log.info(tr("saved", a=short_path(plain_path), b=short_path(plain_path[:-4] + ".txt")))
    if G.missing:
        log.warn(tr("warn_missing_glyphs", g=" ".join(sorted(G.missing))))

    log.step(tr("step_numbered", paper=paper, dpi=DPI))
    numbered = page.copy()
    write_hex_numbers(numbered, grid, k, mx, my)
    save(numbered, layout, numbered_path, params)
    log.info(tr("saved", a=short_path(numbered_path), b=short_path(numbered_path[:-4] + ".txt")))
    print_sites(grid, terrain, rivers, sites, params.get("labels"))


def main():
    first_run = make_maps_folder()
    interactive = len(sys.argv) == 1
    params = ask_settings() if interactive else settings_from_options(sys.argv[1:])
    # paper is asked even with options, unless --formato or no tty
    ask_format = params.pop("ask_paper", interactive)
    apply_edits = params.pop("apply_edits", False)
    show_conjuring()
    log = Log(12)

    # 1: settings
    log.step(tr("step_validate"))
    font_spec, bold_spec = find_font(params["font"])
    advance_em, line_em = font_metrics(font_spec)
    aspect = line_em / advance_em
    if "auto" in (params["columns"], params["rows"]):
        fill_page(params, font_spec, aspect, log)
    number = params["seed"] if params["seed"] is not None else new_seed()
    params.setdefault("version", SEED_VERSION)
    if params.pop("randomize", False):
        random_settings(params, number)
        log.info(tr("info_random"))
    counts = validate(params, log)
    rng = random.Random(number)
    seed = make_seed(params, number)
    if seed is None:
        seed = str(number)
        log.warn(tr("warn_old_seed", s=seed))
    edit_base = os.path.join(map_folder(params["output"], seed), f"{seed}_edit")
    if apply_edits and not has_edits(edit_base):       # --modificata: say so now, not after the land
        sys.exit(tr("err_no_edits", seed=seed, folder=short_path(map_folder(params["output"], seed))))
    log.info(tr("info_seed", s=seed))
    if first_run:
        log.info(tr("info_new_folder", folder=short_path(MAPS_FOLDER)))
    log.info(tr("info_folder", folder=short_path(map_folder(params["output"], seed))))

    # 2: font
    log.step(tr("step_font"))
    grid = HexGrid(params["columns"], params["rows"])
    log.info(tr("info_font", name=font_name(font_spec), fake="" if bold_spec else tr("fake_bold"), a=aspect))

    # 3-9: land
    terrain, rivers, sites, height, fertile = build_land(params, counts, grid, rng, log)
    original = None
    params.setdefault("labels", {})
    if params.pop("edit", False):
        original = (terrain, rivers)
        os.makedirs(map_folder(params["output"], seed), exist_ok=True)
        edited = edit_map(grid, terrain, rivers, sites, height, edit_base, params["labels"], fertile)
        if edited is None:
            return
        terrain, rivers, sites, params["edits"], on_map = edited
        if on_map:              # the names were given on the map, with N
            params.pop("ask_labels", None)
        elif params.get("ask_labels") == "later":
            params["ask_labels"] = input(tr("ask_labels_again")).strip().lower() in YES_WORDS
        log.info(tr("info_edits", path=short_path(edit_base + ".json")))
    elif apply_edits:
        data, source = load_edits(edit_base)
        where = edit_base + "_nonumber.png" if source == "png" else edit_base + ".json"
        if source == "png" and os.path.exists(edit_base + ".json"):
            log.warn(tr("warn_json_broken", path=short_path(edit_base + ".json")))
        try:
            if data is None:
                raise ValueError("unreadable")
            edited = edits_from_json(data, grid, terrain)
        except ValueError:
            sys.exit(tr("err_bad_edits", path=short_path(where)))
        original = (terrain, rivers)
        terrain, rivers, sites, skipped = edited
        params["edits"] = edits_to_json(original[0], terrain, rivers, sites)
        if edit_labels(data) is not None:         # names given in the editor
            params["labels"] = edit_labels(data)
        log.info(tr("info_edits_applied", path=short_path(where)))
        if skipped:
            log.warn(tr("warn_edits_dropped", n=skipped))
    elif has_edits(edit_base):
        log.info(tr("info_has_edits", s=seed))

    if params.pop("ask_labels", False) and sys.stdin.isatty() and sites:
        params["labels"] = ask_labels(grid, terrain, sites, params["labels"])
        if original and os.path.exists(edit_base + ".json"):
            save_edit_labels(edit_base, params["labels"])     # or the editor would bring back the old ones
    named = len(site_labels(sites, params["labels"]))
    if named:
        log.info(tr("info_labels", n=named))

    # 10: paper
    log.step(tr("step_paper"))
    G = Glyphs(open_font(font_spec, 40), params["ascii_only"])
    paper = ask_paper(params, grid, (font_spec, bold_spec, advance_em, aspect), G, ask_format, log)
    params["paper"] = paper
    k = hex_size(params, grid, paper, aspect)
    look = (font_spec, bold_spec, advance_em, aspect, G, paper, k)

    # 11-12: the two maps
    save_maps(params, grid, (terrain, rivers, sites, original, fertile), look, seed, number, log, log)
    log.done()

    # a map just made can be edited straight away, on the same paper
    if interactive and original is None and sys.stdin.isatty():
        if input(tr("ask_edit_now")).strip().lower().startswith(tr("yes_letter")):
            edited = edit_map(grid, terrain, rivers, sites, height, edit_base, params["labels"], fertile)
            if edited is None:
                return
            new_terrain, new_rivers, new_sites, params["edits"], _ = edited
            log = Log(12)
            log.step_number = 10            # only the last two steps are done again
            log.info(tr("info_edits", path=short_path(edit_base + ".json")))
            save_maps(params, grid, (new_terrain, new_rivers, new_sites, (terrain, rivers), fertile), look, seed, number,
                      log, QuietLog())
            log.done()


if __name__ == "__main__":
    # some consoles can't encode ♣ and friends: print ? instead of crashing
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(tr("interrupted"))
        sys.exit(1)
