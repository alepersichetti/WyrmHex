# WyrmHex

<div align="center">

[Italiano](README.it.md) · **English**

<img src="img_examples/OSR%20LOGO.png" alt="OSR logo" width="50%"><br>
Compatible with any "OSR" tabletop RPG.
</div>

```
 _       __                     __  __
| |     / /_  ___________ ___  / / / /__  _  __
| | /| / / / / / ___/ __ `__ \/ /_/ / _ \| |/_/
| |/ |/ / /_/ / /  / / / / / / __  /  __/>  <
|__/|__/\__, /_/  /_/ /_/ /_/_/ /_/\___/_/|_|
       /____/

                    v0.0.2
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

```

**WyrmHex** is a small program that draws a random hex map for old-school (OSR) role-playing campaigns. The map is made only of letters and symbols, like the video games Dwarf Fortress, NetHack, and Moonring:

- **forests** `♣♠`, **mountains** `▲^`, **hills** `∩n`, **deserts** `░·`, **lakes** `≈`;
- **plains** stay empty and the **sea** is a flat gray area;
- **rivers** are double lines `═║╔╗`;
- **cities**, **fortresses** and **dungeons** are black boxes with a white symbol.

The map comes out black on white, ready to print on **A4, A3 or A2** paper at 600 dpi. The program suggests the best paper size for the number of hexes, and turns the sheet upright or sideways by itself to match the shape of the map. Every time you get two pictures of the same map: one **without numbers** (to show your players) and one **with a number in every hex** (for the game master).

---

## 1. What you need

Put these files in the **same folder**, for example a folder called `maps` on your Desktop:

- `wyrmhex.py` (the program)
- `requirements.txt`
- `README.md` (this guide) and `README.it.md` (the same guide in Italian)

You don't need to create anything else: the program creates the `maps_generated` folder, where your maps are saved, the first time you use it.

You also need **Python 3.14**, the program that runs `.py` files. Slightly older versions work too, from 3.11 up.

---

## 2. Installation (you only do this once)

### Step 1 — Install Python

- **Windows and macOS:** go to <https://www.python.org/downloads/>, download Python 3.14 and install it like any other program.
  - On Windows, if the installer shows a box called **"Add python.exe to PATH"**, tick it.
- **Linux:** Python is usually already installed. If your distribution doesn't have 3.14, the version you have is fine, as long as it's 3.11 or newer.

### Step 2 — Open the terminal in the folder with the files

The terminal is a window where you type commands.

- **Windows 11:** open the `maps` folder, right-click an empty spot and choose **"Open in Terminal"**.
- **Windows 10:** open the `maps` folder, click the address bar at the top, type `cmd` and press Enter.
- **macOS:** open the **Terminal** app (in Applications → Utilities). Type `cd` followed by a space, drag the `maps` folder into the window and press Enter.
- **Linux:** open the folder, right-click an empty spot and choose **"Open in Terminal"**.

### Step 3 — Get the program ready

Copy the commands below **one at a time** and press Enter after each one. The first one creates a private space for the program inside the folder: a hidden subfolder called `.venv`, which you should leave alone. The second one downloads **Pillow**, the library that creates the pictures.

**Windows**
```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**macOS and Linux**
```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If you see a line starting with `Successfully installed` at the end, you're all set.

---

## 3. Making a map

Open the terminal in the folder, as in step 2, and type:

**Windows**
```
.venv\Scripts\python wyrmhex.py
```

**macOS and Linux**
```
.venv/bin/python wyrmhex.py
```

First the program asks for the **language**: type `1` for Italian or `2` for English (pressing Enter keeps Italian). From then on the questions, the messages and even the texts printed on the map (legend, scale, starting title) are in the language you chose.

Then the welcome screen appears, with the title and a picture: press **ENTER** to begin. The program asks you a few questions. **Every question has a ready-made answer in square brackets: if you're happy with it, just press Enter.**

1. **What do you want to do?** Type `1` for a new map, `2` to rebuild a map you already made (see chapter 4).
2. **Hexes across and down:** how many columns and rows of hexes you want. The ready-made answer is `auto`: the program works out by itself how many hexes fill an A4 sheet and stay easy to read (33 × 15).
3. **Number of dungeons, cities and fortresses** to put on the map.
4. **Terrain percentages:** how much of the map is plains, sea, lakes, hills, mountains, forests and deserts. They can't add up to more than 100; anything left over becomes plains. If you get it wrong, the program tells you and asks for the numbers again.
5. **Number of rivers:** with `-1` the program decides by itself.
6. **Title** printed at the top of the map.
7. Whether to use **only basic keyboard characters** (no symbols like ♣ ▲ ≈). You'll usually answer no: just press Enter.

Once the questions are done, a wizard appears with the words **"The conjuring spell begins!"**: from here the program gets to work.

While it works, it shows each step it's taking, each with a **progress bar** that fills up step by step:

```
[████░░░░░░░░]  4/12  Sea: flooding from the lowest edge hex towards lower ground
```

While it draws the two pictures, which is the longest part, a second bar shows the percentage and updates in place until it reaches `100%  done`. When the map is ready, it asks you one last thing:

8. **Print format** for the two maps: `A4`, `A3` or `A2`. The program weighs up the format based on the number of hexes: before the question you'll see, for each format, how big the hexes and the letters will be and whether they'll be easy to read. The ready-made answer in brackets is the **suggested format**: the smallest one where the map reads well; the more hexes you chose, the bigger it gets. **The final choice is yours:** press Enter for the suggested format, or type another one. For example:

   ```
   · Grid of 12 x 30 hexes: this is how it would print on each format (hex measured from flat side to flat side)
   · A4 portrait    small hexes  8 mm, letters 1.07 mm wide (too small)
   · A3 portrait    small hexes 12 mm, letters 1.53 mm wide (easy to read)   <- suggested
   · A2 portrait    large hexes 18 mm, letters 1.50 mm wide (easy to read)
     The final choice is yours: press Enter for the suggested format, or type another one.
     Print format for both maps (A4, A3, A2) [A3]:
   ```

   On big sheets, if there's room, the program uses bigger hexes, so the map keeps good proportions.

At the end it lists where the cities, fortresses and dungeons are, with their hex numbers: handy for the game master's notes.

---

## 4. Rebuilding a map you already made

Every map has a **seed**: it's the name of the map's folder inside `maps_generated` and the number at the start of its file names. For example, the seed of `maps_generated/482913/482913_nonumber.png` is `482913`.

To rebuild exactly that map, start the program, choose the language, answer `2` to "What do you want to do?" and type the seed. Every picture keeps the settings it was made with hidden inside it, and the program reads them back from there: that's why the file `<seed>_nonumber.png` must still be in its folder `maps_generated/<seed>`. Maps made with earlier versions, which were saved straight into the program's folder, are found too. The rebuilt map goes into the `maps_generated/<seed>` folder and replaces the files that were there. The program only asks again whether to use basic characters and, at the end, the print format (the ready-made answer is the format you used last time): so you can rebuild the same map in A3 instead of A4, for example.

If you rebuild the map in a different language from the first time, the starting title and scale are translated (for example "Terre Selvagge" becomes "Wild Lands"); a title you chose yourself stays as it is.

If the file is gone, the program asks you to type in **the same settings** you used the first time. The seed alone isn't enough: different settings make a different map.

---

## 5. The files you get

The first time you use it, the program creates a folder called **`maps_generated`** next to `wyrmhex.py`. Inside it, every map gets a folder of its own, named after the map's seed, holding its four files:

```
maps_generated/
  482913/
    482913_nonumber.png
    482913_nonumber.txt
    482913_number.png
    482913_number.txt
```

At the end, the program tells you which folder it saved the files in.

| File | What it is |
|---|---|
| `482913_nonumber.png` | The map without numbers, for the players |
| `482913_number.png` | The same map with a number in every hex, for the game master |
| `482913_nonumber.txt`, `482913_number.txt` | The map as text, which you can open with Notepad or TextEdit |

Hex numbers have four digits: the first two are the column, the last two the row. `0101` is the top-left hex; `0305` is in the third column, fifth row.

---

## 6. Printing

The pictures already have the exact size of the paper you chose (A4, A3 or A2), at 600 dpi: they print sharp even on big sheets.

- Print on **the paper size you chose**, in black and white, with the sheet the same way round as the picture (portrait or landscape).
- In the print options choose **"Actual size"** or **"100%"**. Avoid "Fit to page", which shrinks the map.
- If your printer only goes up to A4, a print shop can do A3 and A2: bring the PNG file as it is.

---

## 7. For people in a hurry: the options

Instead of answering the questions, you can type everything on one line. Any setting you leave out keeps its starting value. Examples (on Windows use `.venv\Scripts\python` instead of `.venv/bin/python`):

```
.venv/bin/python wyrmhex.py --language en --grid 30x15 --cities 4 --dungeons 6
.venv/bin/python wyrmhex.py --language en --grid 50x30 --format A2
.venv/bin/python wyrmhex.py --language en --sea 30 --plains 15 --title "Isle of Winds"
.venv/bin/python wyrmhex.py --language en --reproduce 482913
```

Without `--language en` the messages and the texts on the map are in Italian. Every option also has an Italian name (in the table after the slash `/`), and you can mix them as you like.

| Option | What it does | Example |
|---|---|---|
| `--language` / `--lingua` | Language of the messages and of the texts on the map: `en` or `it` | `--language en` |
| `--grid` / `--griglia` | Columns x rows of hexes (`auto` = fills an A4) | `--grid 20x15` |
| `--cities`, `--fortresses`, `--dungeons` / `--citta`, `--fortezze`, `--dungeon` | How many sites of each kind | `--cities 4` |
| `--plains`, `--sea`, `--lakes`, `--hills`, `--mountains`, `--forests`, `--deserts` / `--pianura`, `--mare`, `--laghi`, `--colline`, `--montagne`, `--foreste`, `--deserti` | Percentage of each terrain | `--sea 25` |
| `--rivers` / `--fiumi` | Number of rivers (`-1` = automatic) | `--rivers 3` |
| `--title` / `--titolo` | Title at the top of the map | `--title "Northern Lands"` |
| `--scale` / `--scala` | Scale text | `--scale "5 km"` |
| `--seed` / `--seme` | Use a specific seed instead of a random one | `--seed 42` |
| `--reproduce` / `--riproduci` | Rebuilds the map with that seed, reading the settings from its file (looked for in `maps_generated/<seed>`, or in the `--output` folder) | `--reproduce 482913` |
| `--format` / `--formato` | Print format: `A4`, `A3` or `A2`. If you leave it out, the program asks you at the end, offering the suggested one (or, with `--reproduce`, the one from last time) | `--format A3` |
| `--orientation` / `--orientamento` | Usually not needed: the sheet direction follows the shape of the map. You can force it with `portrait` or `landscape` (`verticale` or `orizzontale`) | `--orientation portrait` |
| `--output` | Folder to save the maps in instead of `maps_generated`; there too, every map gets its own folder named after its seed | `--output maps` |
| `--ascii-only` / `--solo-ascii` | Use only plain keyboard letters and signs | `--ascii-only` |
| `--size` / `--dimensione` | `small` or `large` hexes (`piccola` or `grande`) | `--size large` |
| `--font` | Use a font file of your choice (all its letters must be the same width) | `--font consola.ttf` |

To see the full list of options, add `--help` after the file name (with `--language en --help` it's in English); to find out which version you have, add `--version`.

---

## 8. Common problems

**"py" / "python3" is not recognized as a command.**
Python isn't installed, or on Windows it wasn't added to the PATH. Reinstall it with "Add python.exe to PATH" ticked, then close and reopen the terminal.

**"Pillow is missing".**
You skipped step 3, or you're starting the program with `py` or `python3` instead of `.venv\Scripts\python` (Windows) or `.venv/bin/python` (macOS/Linux).

**Linux: `python3 -m venv .venv` gives an error that mentions `ensurepip` or `venv`.**
A piece of Python is missing. On Ubuntu and Debian install it with `sudo apt install python3-venv`, then repeat step 3.

**"The terrain percentages add up to ...%, more than 100%".**
The percentages you typed add up to more than 100. Lower some of them.

**"the sites need N land hexes, but the map has only M".**
You asked for too many sites for a small map, or one with too much water. Ask for fewer sites, make the grid bigger, or lower the sea and lakes.

**The program says "Very small letters".**
The grid is too big for the format you chose: the map will print, but it'll be hard to read. Choose a bigger format (the suggested one) or use fewer hexes.

**Some symbols turned into plain letters.**
The font installed on your computer doesn't have those symbols. The program swaps them by itself and tells you. You can pick another font with `--font`, for example `--font DejaVuSansMono.ttf`, if it's installed.

**The printed map is smaller than the sheet, or off-center.**
In the print options choose "Actual size" or "100%", not "Fit to page".

**I don't see the percentage bar while it draws the pictures.**
That bar updates on the same line, and it only shows up when the program runs in a terminal window. If you start it some other way (for example sending the messages to a file) it stays hidden, but the map is made all the same. The step bar (`4/12`, `5/12`…) always shows.

**The welcome screen picture looks cut off on the right.**
The terminal window is too narrow: the picture is 94 characters wide, and the program trims it so it doesn't get scrambled. Make the window wider and start the program again.

**I have an old map with a black background.**
Earlier versions allowed a black background; now maps are always on white. Rebuild the map from its seed (chapter 4) or use `--reproduce` with the seed: it comes back the same, on a white background.

---

## 9. Output examples

### 12 × 10 hexes

![12 x 10 map without numbers](img_examples/example_12x10_nonumber.png)
![12 x 10 map with numbers](img_examples/example_12x10_number.png)

### 20 × 5 hexes

![20 x 5 map without numbers](img_examples/example_20x5_nonumber.png)
![20 x 5 map with numbers](img_examples/example_20x5_number.png)

### 80 × 80 hexes

![80 x 80 map without numbers](img_examples/example_80x80_nonumber.png)
![80 x 80 map with numbers](img_examples/example_80x80.png)
