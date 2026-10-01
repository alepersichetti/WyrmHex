#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WyrmHex v0.0.3 - random hexcrawl maps for OSR games, all in ASCII.

Looks like an old terminal game (Dwarf Fortress, NetHack): hexes drawn with
_ / \\, terrain as CP437 symbols (forest ♣♠, mountains ▲^, hills ∩n, lakes ≈,
deserts ░·, swamps ⌠"), empty plains, gray sea, rivers in ═║╔╗, and sites as
white glyphs in black boxes. Prints black on white, A4/A3/A2 at 600 dpi;
the sheet turns to match the map and the best paper size is suggested.

Output goes to maps_generated/<seed>/ next to this file (or --output):
  <seed>_nonumber.png/.txt   for the players
  <seed>_number.png/.txt     same map, hexes numbered CCRR (0101 = top left)

The seed (e.g. 475T-4KM4-MY0B-JNDJ-ZYEQ-K164) holds the whole land, so the
same seed always gives the same map. The PNG also keeps the settings.

Usage. Every option has an Italian and an English name, use whichever:
  python wyrmhex.py                              interactive
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
  python wyrmhex.py --formato A3                 / --format A3
  python wyrmhex.py --titolo "Terre del Nord" --scala 12
                    / --title "Northern Lands" --scale 12
      (miles per hex: 2, 6, 12, 24 or any number; free text like "5 km" works too)
  python wyrmhex.py --solo-ascii                 / --ascii-only
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
import time
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

VERSION = "0.0.3"

PLAINS, SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT = (
    "plains", "sea", "lake", "swamp", "hills", "mountains", "forest", "desert")
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
    "mode_new": ("    1 = creare una mappa nuova", "    1 = make a new map"),
    "mode_rebuild": ("    2 = riprodurre una mappa già fatta, a partire dal suo seme",
                     "    2 = rebuild a map you already made, from its seed"),
    "choice": ("Scelta", "Choice"),
    "values_how": ("\n  Città, fortezze, dungeon, percentuali di terreno e fiumi:",
                   "\n  Cities, fortresses, dungeons, terrain percentages and rivers:"),
    "values_manual": ("    1 = li scelgo io", "    1 = I'll choose them"),
    "values_random": ("    2 = a caso", "    2 = random"),
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
    "scale_other": ("altro, lo scrivo io", "other, I'll type it"),
    "ask_custom_scale": ("  Miglia per esagono (un numero, oppure un testo come \"5 km\"): ",
                         "  Miles per hex (a number, or a text like \"5 km\"): "),
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
# v1 seeds (no swamps) still decode. Before that the seed was a plain number
# that only worked together with the settings stored in the PNG.
SEED_VERSION = 2                     # 2 = swamps
SEED_SYMBOLS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # no I, L, O, U: too easy to misread
SEED_LENGTH = 24
MAX_SITES = 99                       # per kind
MAX_RIVERS = 100
RANDOM_NUMBERS = 2 ** 20             # old 6-digit seeds (<= 999999) still fit
# no plains: they're whatever is left
SEED_TERRAINS = {1: (SEA, LAKE, HILLS, MOUNTAINS, FOREST, DESERT),
                 2: (SEA, LAKE, SWAMP, HILLS, MOUNTAINS, FOREST, DESERT)}
SEED_CHECK_SYMBOLS = {1: 3, 2: 2}


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
    packed = 0
    for value, choices in seed_fields(p, number):
        if value != int(value) or not 0 <= value < choices:
            return None
        packed = packed * choices + int(value)
    data = to_symbols(packed, SEED_LENGTH - SEED_CHECK_SYMBOLS[SEED_VERSION])
    code = data + seed_check(data)
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
    land = {"columns": columns + 2, "rows": rows + 2, "dungeons": dungeons, "cities": cities,
            "fortresses": fortresses, "rivers": rivers,
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
        return saved
    unpacked = read_seed(text)
    if unpacked is None:
        return None
    land, number = unpacked
    picture = find_settings(base, make_seed(land, number)) or {}
    settings = {key: picture[key] for key in ("title", "scale", "paper", "size", "font") if key in picture}
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


def output_names(base, seed, extension="png"):
    folder = map_folder(base, seed)
    os.makedirs(folder, exist_ok=True)
    return (os.path.join(folder, f"{seed}_nonumber.{extension}"),
            os.path.join(folder, f"{seed}_number.{extension}"))


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
    for key, value in (("ascii_only", False), ("size", "auto"), ("font", None), ("paper", None),
                       ("title", tr("default_title")), ("scale", tr("default_scale"))):
        p.setdefault(key, value)
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


def ask_scale():
    print(tr("scale_how"))
    for i, miles in enumerate(SCALE_PRESETS, 1):
        print(f"    {i} = {scale_text(str(miles))}")
    other = len(SCALE_PRESETS) + 1
    print(f"    {other} = {tr('scale_other')}")
    choice = ask(tr("choice"), SCALE_PRESETS.index(6) + 1, int, 1, other)
    if choice < other:
        return scale_text(str(SCALE_PRESETS[choice - 1]))
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


# --- welcome screen, wizard, questions ---
TITLE_ART = r"""
 _       __                     __  __
| |     / /_  ___________ ___  / / / /__  _  __
| | /| / / / / / ___/ __ `__ \/ /_/ / _ \| |/_/
| |/ |/ / /_/ / /  / / / / / / __  /  __/>  <
|__/|__/\__, /_/  /_/ /_/ /_/_/ /_/\___/_/|_|
       /____/
"""

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
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError):
        return None


def show_welcome():
    art = WYVERN_CASTLE.strip("\n").split("\n")
    title = TITLE_ART.strip("\n").split("\n")
    subtitle = f"v{VERSION}  ·  " + tr("welcome_subtitle")
    width = max(len(line) for line in art)
    # wrapped lines would scramble the drawing, so cut it at the window edge
    columns = terminal_width()
    if columns and columns <= width:
        width = columns - 1
    title_width = max(len(line) for line in title)
    screen = [
        "═" * width,
        "",
        # centre it as one block or the letters won't line up
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
    """None for a new map, otherwise (number, settings). settings is None only
    for an old number seed whose PNG is gone: then everything is asked again."""
    print(tr("what_to_do"))
    print(tr("mode_new"))
    print(tr("mode_rebuild"))
    choice = ask(tr("choice"), 1, int, 1, 2)
    if choice == 1:
        return None
    while True:
        answer = input(tr("ask_seed", example=example_seed())).strip()
        if is_old_seed(answer) or read_seed(answer):
            break
        print(tr("seed_invalid", example=example_seed()))

    if not is_old_seed(answer):
        saved = rebuild_settings(answer, folder)
        print(tr("found_seed", seed=make_seed(saved, saved["seed"]), desc=describe_settings(complete_settings(saved))))
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
    return number, saved


def ask_look(p):
    """Doesn't change the land, so it's asked again when rebuilding a map."""
    p["ascii_only"] = input(tr("ask_ascii")).strip().lower().startswith(tr("yes_letter"))


def ask_settings():
    ask_language()
    show_welcome()
    print(tr("enter_accepts"))
    mode = ask_mode()
    if mode and mode[1]:
        # land already known: only the look is left to ask (paper comes later)
        saved = mode[1]
        saved["output"] = MAPS_FOLDER
        print()
        ask_look(saved)
        return complete_settings(saved)
    print()
    p = {}
    p["columns"] = ask(tr("q_columns"), "auto", int, 2, 80)
    p["rows"] = ask(tr("q_rows"), "auto", int, 2, 80)
    print(tr("values_how"))
    print(tr("values_manual"))
    print(tr("values_random"))
    # random values need the grid size, which may still be "auto": main() fills them in
    p["randomize"] = ask(tr("choice"), 1, int, 1, 2) == 2
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
    else:
        p["seed"] = None             # a new map gets a new random number
    p["title"] = input(tr("q_title", default=tr("default_title"))).strip() or tr("default_title")
    p["scale"] = ask_scale()
    print()
    p["output"] = MAPS_FOLDER
    p["orientation"] = "auto"
    ask_look(p)
    p["size"], p["font"], p["paper"] = "auto", None, None   # paper: asked after the map is built
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
    sizes = {"it": ["auto", "piccola", "grande"], "en": ["auto", "small", "large"]}
    ap.add_argument(*names("dimensione", "size"), dest="size", choices=list(SIZE_FROM_USER), default="auto",
                    metavar=shown(sizes), help=tr("h_size"))
    ap.add_argument("--version", action="version", version=f"WyrmHex v{VERSION}", help=tr("h_version"))
    ap.add_argument("--font", default=None, metavar="FILE", help=tr("h_font"))
    a = ap.parse_args(argv)
    orientation = ORIENTATION_FROM_USER[a.orientation]
    ask_for_paper = a.paper is None and sys.stdin.isatty()
    size = SIZE_FROM_USER[a.size]

    # --seed with a full code means "rebuild that one"
    if a.reproduce is None and a.seed is not None and not is_old_seed(a.seed):
        a.reproduce, a.seed = a.seed, None
    if a.seed is not None and not (is_old_seed(a.seed) and int(a.seed) < RANDOM_NUMBERS):
        ap.error(tr("err_seed_number", max=RANDOM_NUMBERS - 1, example=example_seed()))

    if a.reproduce is not None:
        saved = rebuild_settings(a.reproduce, a.output)
        if not saved:
            if is_old_seed(a.reproduce):
                ap.error(tr("err_no_saved", seed=a.reproduce, folder=short_path(a.output)))
            ap.error(tr("err_bad_seed", seed=a.reproduce, example=example_seed()))
        saved["output"] = a.output
        # the look comes from this command line, not from the old PNG
        saved.update(ascii_only=a.ascii_only)
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
        "ascii_only": a.ascii_only, "size": size, "font": a.font,
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
# hills on top. Then swamps in the low wet bits, a second noise map for
# forest (wet) / desert (dry), rivers downhill, sites last.
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


def place_swamps(grid, height, n, rng, terrain):
    """Lowest free hexes, nearer to water first. Patches come out by themselves."""
    if n <= 0:
        # don't touch rng here: maps without swamps must match pre-0.0.3 ones
        return
    to_water = grid.distances_from([h for h in grid.hexes if terrain[h] in WATER])
    score = {}
    for h in grid.hexes:
        if terrain[h] is None:
            d = to_water[h] if to_water[h] is not None else 4
            score[h] = height[h] + 0.06 * min(d, 4) + 0.05 * rng.random()
    for h in sorted(score, key=score.get)[:n]:
        terrain[h] = SWAMP


def place_forests_and_deserts(grid, n_forests, n_deserts, rng, terrain):
    wetness = {h: 0.7 * v for h, v in noise_field(grid, rng, max(2, (grid.cols + grid.rows) // 7)).items()}
    fine = noise_field(grid, rng, 1)
    to_water = grid.distances_from([h for h in grid.hexes if terrain[h] in WATER])
    for h in grid.hexes:
        wetness[h] += 0.3 * fine[h]
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
        # keep it only if it's >= 3 hexes and ends somewhere sensible
        if end and len(path) >= 3:
            rivers.append({"path": path, "end": end})
            river_hexes.update(path)
    return rivers


def place_sites(grid, terrain, rivers, wanted, rng, log):
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
    """Steps 3-9. Returns (terrain of every hex, rivers, sites)."""
    log.step(tr("step_heights"))
    height = make_heights(grid, rng)
    log.info(tr("info_heights", n=len(grid.hexes)))

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
    place_swamps(grid, height, counts[SWAMP], rng, terrain)
    place_forests_and_deserts(grid, counts[FOREST], counts[DESERT], rng, terrain)
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

    log.step(tr("step_sites"))
    sites = place_sites(grid, terrain, rivers,
                        {CITY: params["cities"], FORTRESS: params["fortresses"], DUNGEON: params["dungeons"]},
                        rng, log)

    return terrain, rivers, sites


def print_sites(grid, terrain, rivers, sites):
    digits = max(2, len(str(max(grid.cols, grid.rows))))
    print(tr("sites_header"))
    for kind in (CITY, FORTRESS, DUNGEON):
        for i, (_, h) in enumerate([s for s in sites if s[0] == kind], 1):
            extra = tr("on_river") if any(h in r["path"] for r in rivers) else ""
            print(f"  {pick(SITE_NAMES[kind]):<9} {i:>2}  →  {hex_code(h, digits)}  ({pick(TERRAIN_NAMES[terrain[h]])}{extra})")


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
        self.boxes = []            # site boxes: (x, y, width, height, symbol)

    def put(self, x, y, ch, style="n"):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.chars[y][x], self.styles[y][x] = ch, style

    def write(self, x, y, text, style="n"):
        for i, c in enumerate(text):
            self.put(x + i, y, c, style)

    def paste(self, other, ox, oy):
        for y in range(other.height):
            for x in range(other.width):
                self.put(ox + x, oy + y, other.chars[y][x], other.styles[y][x])
        self.boxes += [(ox + x, oy + y, w, h, g) for x, y, w, h, g in other.boxes]

    def copy(self):
        c = Canvas(self.width, self.height)
        c.chars = [row[:] for row in self.chars]
        c.styles = [row[:] for row in self.styles]
        c.boxes = list(self.boxes)
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
def draw_map(grid, terrain, rivers, sites, k, G, rng, aspect):
    """Terrain, then hex borders, then rivers, then sites; each layer can
    overwrite the previous one."""
    width, height = map_size(grid.cols, grid.rows, k)
    canvas = Canvas(width, height)
    border, inside = hex_template(k)

    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        kind = terrain[(c, r)]
        if kind == SEA:
            for (yy, xx) in inside:
                # the ≈ only shows in the .txt
                canvas.put(x0 + xx, y0 + yy, G("≈", "~"), "g")
            continue
        choices = TERRAIN_GLYPHS[kind]
        if not choices:
            continue
        for (yy, xx) in inside:
            canvas.put(x0 + xx, y0 + yy, pick_symbol(rng, choices, G))

    # borders between two sea hexes get the gray too, or the sea looks tiled
    shared = {}    # for each border square: [letter, "only sea hexes share it so far"]
    for c, r in grid.hexes:
        x0, y0 = hex_origin(c, r, k)
        for (yy, xx, ch) in border:
            shared.setdefault((x0 + xx, y0 + yy), [ch, True])
            shared[(x0 + xx, y0 + yy)][1] &= terrain[(c, r)] == SEA
    for (x, y), (ch, sea_only) in shared.items():
        canvas.put(x, y, ch, "H" if sea_only else "b")

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

    # sites: [⌂⌂] in the .txt, a black box with one big white glyph in the PNG
    cx = 2 * k + 1
    for kind, (c, r) in sites:
        x0, y0 = hex_origin(c, r, k)
        g = G(*SITE_GLYPHS[kind])
        for yy in (k, k + 1):
            canvas.write(x0 + cx - 2, y0 + yy, "[" + g + g + "]", "B")
        canvas.boxes.append((x0 + cx - 2, y0 + k, 4, 2, g))
    return canvas


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
        # white background even in the sea, cheap printers turn gray digits to mush
        code = hex_code((c, r), digits)
        x_num = ox + x0 + 2 * k + 1 - len(code) // 2
        for i, digit in enumerate(code):
            page.put(x_num + i, y, digit, "n")


# --- page: frame, title, legend ---
def legend_entries(G):
    terrains = [
        (G("▲^", "^A"), tr("leg_mountains"), "b"), (G("∩n", "nm"), tr("leg_hills"), "b"),
        (G("♣♠", "TY"), tr("leg_forest"), "b"), ("", tr("leg_plains"), "b"), (G("░·", ".:"), tr("leg_desert"), "b"),
        (G("≈≈", "~~"), tr("leg_sea"), "g"),   # "g": this sample is drawn as a gray patch
        (G("≈≈", "~~"), tr("leg_lake"), "b"), (G('⌠"', '",'), tr("leg_swamp"), "b"),
        (G("═╗", "=+"), tr("leg_river"), "b"),
    ]
    sites = [(G(*SITE_GLYPHS[kind]), pick(SITE_NAMES[kind])) for kind in (CITY, FORTRESS, DUNGEON)]
    if G.ascii_only:
        sites = [(g, name.replace("à", "a'")) for g, name in sites]
    return terrains, sites


def pack_legend(G, max_width):
    terrains, sites = legend_entries(G)
    entries = [[(g, style), (" " + name, "n")] if g else [(name, "n")] for g, name, style in terrains]
    entries += [[("[" + g + "]", "i"), (" " + name, "n")] for g, name in sites]
    lines, line, length = [], [], 0
    for entry in entries:
        w = sum(len(text) for text, _ in entry)
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
        length = sum(sum(len(text) for text, _ in entry) for entry in line) + 4 * (len(line) - 1)
        x = (n_cols - length) // 2
        for j, entry in enumerate(line):
            if j:
                x += 4
            for text, style in entry:
                page.write(x, y_legend_line + 1 + i, text, style)
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
    legend_lines = len(pack_legend(Glyphs(open_font(font_spec, 40), params["ascii_only"]), n_cols - 4))
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
    default = params.get("paper") or suggested
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


def render(canvas, regular, bold, char_w, char_h, size, width, height, ox, oy, progress=None):
    """Rasterise the canvas. progress(fraction) is called after each row."""
    img = Image.new("L", (width, height), 255)   # white grayscale picture
    d = ImageDraw.Draw(img)
    thicken = max(1, size // 22)                 # shift used to fake a bold letter
    real_bold = bold is not None and bold is not regular
    probe = bold.font_variant(size=40) if real_bold else None
    bold_can_draw = {}                           # remembers which symbols the bold font has

    def draw_bold(px, py, ch):
        # Menlo Bold (macOS) has no ═║╔╗: it drew empty boxes for the rivers.
        # Fake bold with the regular font drawn twice instead.
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
            if style == "B" or (ch == " " and style not in "igGH"):
                continue
            px = ox + x * char_w
            if style in "gGH":
                d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=SEA_GRAY)
                if style == "G":
                    d.text((px, py), ch, font=regular, fill=0, anchor="la")
                elif style == "H":
                    draw_bold(px, py, ch)
                continue
            if style == "i":
                # the [ ] only make sense in the .txt
                d.rectangle([px, py, px + char_w + 0.5, py + char_h + 0.5], fill=0)
                if ch not in "[] ":
                    d.text((px, py), ch, font=regular, fill=255, anchor="la")
            elif style == "b":
                draw_bold(px, py, ch)
            else:
                d.text((px, py), ch, font=regular, fill=0, anchor="la")
        if progress:
            progress((y + 1) / canvas.height)
    big = regular.font_variant(size=int(size * 1.7))
    for bx, by, bw, bh, g in canvas.boxes:
        x1, y1 = ox + bx * char_w, oy + by * char_h
        d.rectangle([x1, y1, x1 + bw * char_w, y1 + bh * char_h], fill=0)
        d.text((x1 + bw * char_w / 2, y1 + bh * char_h / 2), g, font=big, fill=255, anchor="mm")
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
    img = render(canvas, regular, bold, char_w, char_h, size, work_w, work_h, ox, oy,
                 progress=lambda done: live.update(0.9 * done, drawing))
    if (work_w, work_h) != (width, height):
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
        legend = pack_legend(G, n_cols - 4)
        if len(legend) <= legend_guess and n_rows >= map_h + len(legend) + 7:
            break
        legend_guess = max(len(legend), legend_guess + 1)
    values = dict(scale=params["scale"], dot=G("·", "-"), c=grid.cols, x=G("×", "x"), r=grid.rows, seed=seed)
    versions = [tr(key, **values) for key in ("subtitle", "subtitle_tight", "subtitle_short", "subtitle_seed")]
    subtitle = next((v for v in versions if len(v) + 4 <= n_cols), versions[-1])
    legend = pack_legend(G, n_cols - 4)
    # still doesn't fit (very long title?): grow the page, save() shrinks it back
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


def main():
    first_run = make_maps_folder()
    interactive = len(sys.argv) == 1
    params = ask_settings() if interactive else settings_from_options(sys.argv[1:])
    # paper is asked even with options, unless --formato or no tty
    ask_format = params.pop("ask_paper", interactive)
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
    if params.pop("randomize", False):
        random_settings(params, number)
        log.info(tr("info_random"))
    counts = validate(params, log)
    rng = random.Random(number)
    seed = make_seed(params, number)
    if seed is None:
        seed = str(number)
        log.warn(tr("warn_old_seed", s=seed))
    log.info(tr("info_seed", s=seed))
    if first_run:
        log.info(tr("info_new_folder", folder=short_path(MAPS_FOLDER)))
    log.info(tr("info_folder", folder=short_path(map_folder(params["output"], seed))))

    # 2: font
    log.step(tr("step_font"))
    grid = HexGrid(params["columns"], params["rows"])
    log.info(tr("info_font", name=font_name(font_spec), fake="" if bold_spec else tr("fake_bold"), a=aspect))

    # 3-9: land
    terrain, rivers, sites = build_land(params, counts, grid, rng, log)

    # 10: paper
    log.step(tr("step_paper"))
    G = Glyphs(open_font(font_spec, 40), params["ascii_only"])
    paper = ask_paper(params, grid, (font_spec, bold_spec, advance_em, aspect), G, ask_format, log)
    params["paper"] = paper
    k = hex_size(params, grid, paper, aspect)
    layout, n_cols, n_rows, legend, subtitle = page_layout(
        params, grid, k, paper, seed, font_spec, bold_spec, advance_em, aspect, G, log)

    # glyphs get their own rng, independent from the land's
    drawing_rng = random.Random(number + 1)
    map_canvas = draw_map(grid, terrain, rivers, sites, k, G, drawing_rng, aspect)
    page, mx, my = compose_page(map_canvas, n_cols, n_rows, legend, params["title"], subtitle, G)
    plain_path, numbered_path = output_names(params["output"], seed)

    # 11-12: the two maps
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

    print_sites(grid, terrain, rivers, sites)
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
