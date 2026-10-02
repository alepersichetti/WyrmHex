# WyrmHex

<div align="center">

[Italiano](README.it.md) · **English**

</div>

<table align="center"><tr><td><pre>
\ ___                     \       /   /)                 ___ /
 \    \_______________     \\ _ //   // _______________/    /
  \      //-  -    / \\__,- .\ /. -,((_// \   -  - \\      /
   \    //   ****************) (*****************   \\    /
    \  //   /****************,_,*****************\   \\  /
     \// __/ *             WyrmHex              * \__ \\/
     /       *              v0.1.0              *       \
             *************M********M*************
&nbsp;
       /\         /\                    .           /\
      /  \       /  \                   |@&gt;        /  \
     /    \     / .  \                  |         /    \
    /      \   /  |@&gt; \       /\       / \       /      \
   /     /\ \ /   |    \     /  \     /   \     /        \
  /     /  \ /  _ | _   \   /    \    | O |    /          _   _   _
 /     /    \  |_|_|_|   \ /      \   |___|   /          | |_| |_| |
/     /      \  | O |     /        \  | |_|  /      /\   |         |
    _   _   _ \ |___|    /          \ |__|| /      /  \  |  O   O  |
   | |_| |_| |  | |_|   /             | |_|       /    \ |   __ _  |
   |         |  |__||  /              |_| |      /       |     |   |
   | O  O  O |  | |_| /               |__ |     /        | O  O  O |
   |  _      |  _   _   _        ______   |   _   _   _  |  _      |
   | |__|_ | |_| |_| |_| |______|      |_____| |_| |_| |_| |__|_ |_|
   |  |   _| |        _  |  | _|  ____     _||        _  |  |    | |
   |   _| _  ||_|   _|_  | _|_   |||||| |_| _||_|   _|_  |   _| _| |
   |  __|  |_|  |_       | | |__ |++++|   |_||  |_      ||  __|  |_|
   |_________|___________|-------------------|___________|_________|
                                 /_/_/
                                /_/_/
</pre></td></tr></table>

<div align="center">

<img src="img_examples/OSR%20LOGO.png" alt="OSR logo" width="25%"><br>
Compatible with any "OSR" tabletop RPG.

Maps in different sizes are in the [Map Gallery](#10-map-gallery).

</div>

**WyrmHex** is a small program that draws a random hex map for old-school (OSR) role-playing campaigns. The map is made only of letters and symbols, like the video games Dwarf Fortress, ADOM, NetHack or Caves of Qud:

- **forests** `♣♠`, **mountains** `▲^`, **hills** `∩n`, **deserts** `░·`, **lakes** `≈`, **swamps** `⌠"` (reeds and tufts of marsh grass, as in Dwarf Fortress);
- **plains** stay empty and the **sea** is a flat gray area;
- **rivers** are double lines `═║╔╗`;
- **cities**, **fortresses** and **dungeons** are black boxes with a white symbol.

The map comes out black on white, ready to print on **A4, A3 or A2** paper at 600 dpi, or, if you prefer, **in colour** on a white or black background. The program suggests the best paper size for the number of hexes, and turns the sheet upright or sideways by itself to match the shape of the map. Every time you get two pictures of the same map: one **without numbers** (to show your players) and one **with a number in every hex** (for the game master).

---

## 1. What you need

Put these files in the **same folder**, for example a folder called `maps` on your Desktop:

- `wyrmhex.py` (the program)
- `requirements.txt`
- `README.md` (this guide) and `README.it.md` (the same guide in Italian)

You don't need to create anything else: the program creates the `maps_generated` folder, where your maps are saved, the first time you use it.

You also need **Python 3.14**, the program that runs `.py` files. Slightly older versions work too, from 3.11 up.

---

## 2. Installation

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

### Step 3 — Create the virtual environment

The program gets a private space inside the folder, called a *virtual environment*: a hidden subfolder named `.venv`, which you should leave alone. That way the libraries it needs don't mix with the rest of your computer. Type:

**Windows**
```
py -m venv .venv
```

**macOS and Linux**
```
python3 -m venv .venv
```

Nothing shows up on screen: that's normal. You only do this once.

### Step 4 — Activate the virtual environment

Activating it tells the terminal to use the Python inside `.venv`. Type:

**Windows**
```
.venv\Scripts\activate
```

**macOS and Linux**
```
source .venv/bin/activate
```

From now on, the line where you type starts with `(.venv)`: that's how you know it's active. You need to activate it again every time you open a new terminal (see chapter 3).

### Step 5 — Install the libraries

With the virtual environment active, download **Pillow**, the library that creates the pictures. The command is the same on every system:

```
pip install -r requirements.txt
```

If you see a line starting with `Successfully installed` at the end, you're all set. You only do this once.

---

## 3. Making a map

Open the terminal in the folder, as in step 2. First activate the virtual environment (as in step 4), then start the program:

**Windows**
```
.venv\Scripts\activate
python wyrmhex.py
```

**macOS and Linux**
```
source .venv/bin/activate
python wyrmhex.py
```

You only need to activate it once each time you open a terminal: while the line starts with `(.venv)`, it is active and you can make as many maps as you like with `python wyrmhex.py`. When you're done, type `deactivate` or just close the terminal. If you've just finished the installation in the same window, the environment is already active.

First the program asks for the **language**: type `1` for Italian or `2` for English (pressing Enter keeps Italian). From then on the questions, the messages and even the texts printed on the map (legend, scale, starting title) are in the language you chose.

Then the welcome screen appears, with the title and a picture: press **ENTER** to begin. The program asks you a few questions. **Every question has a ready-made answer in square brackets: if you're happy with it, just press Enter.**

1. **What do you want to do?** Type `1` for a new map, `2` to rebuild a map you already made (see chapter 4), `3` to edit a map by hand, hex by hex (see chapter 5).
2. **Hexes across and down:** how many columns and rows of hexes you want. The ready-made answer is `auto`: the program works out by itself how many hexes fill an A4 sheet and stay easy to read (33 × 15).
3. **Choose yourself or at random?** Type `1` to answer the next three questions yourself, or `2` to let the program pick the number of sites, the terrain percentages and the rivers at random, sized to the map. With `2` it skips straight to the title. The values it picks are shown while it works, and they end up in the seed like any other.
4. **Number of dungeons, cities and fortresses** to put on the map (up to 99 of each).
5. **Terrain percentages:** how much of the map is plains, sea, lakes, swamps, hills, mountains, forests and deserts, as whole numbers. Swamps form in low ground, mostly along the coast and around lakes. If the sea is over 50%, the map becomes a ragged coastline: a mainland along one side, with peninsulas reaching out into the sea, bays between them, and islands offshore. Over 80% sea the mainland disappears and what is left is an archipelago of islands. Every map also has a **prevailing wind**, picked at random and shown while the map is being made (for example "from the west"): it brings rain to the hill and mountain slopes facing it, where forests grow, while the land on the other side of the high ground stays dry, so that is where deserts tend to form. They can't add up to more than 100; anything left over becomes plains. If you get it wrong, the program tells you and asks for the numbers again.
6. **Number of rivers** (up to 100): with `-1` the program decides by itself.
7. **Title** printed at the top of the map.
8. **Scale:** how many miles each hex covers. `1` = 2 miles, `2` = 6 miles (the ready-made answer), `3` = 12 miles, `4` = 24 miles, `5` = your own: type a number of miles, or any text such as `5 km` or `1 day`. It's printed under the title, as "1 hex = 6 miles".
9. Whether to use **only basic keyboard characters** (no symbols like ♣ ▲ ≈). You'll usually answer no: just press Enter.
10. **Colours:** `1` = black and white, for printing (the ready-made answer); `2` = colour: forests green, sea and lakes blue, deserts sandy, swamps purple, cities red and so on. Only for a colour map does the program then ask for the **background**: `1` = white, `2` = black.

Once the questions are done, a wizard appears with the words **"The conjuring spell begins!"**: from here the program gets to work.

While it works, it shows each step it's taking, each with a **progress bar** that fills up step by step:

```
[████░░░░░░░░]  4/12  Sea: flooding from the lowest edge hex towards lower ground
```

While it draws the two pictures, which is the longest part, a second bar shows the percentage and updates in place until it reaches `100%  done`. When the map is ready, it asks you one last thing:

11. **Print format** for the two maps: `A4`, `A3` or `A2`. The program weighs up the format based on the number of hexes: before the question you'll see, for each format, how big the hexes and the letters will be and whether they'll be easy to read. The ready-made answer in brackets is the **suggested format**: the smallest one where the map reads well; the more hexes you chose, the bigger it gets. **The final choice is yours:** press Enter for the suggested format, or type another one. For example:

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

Last of all it asks whether you want to **edit this map now**. Answer `y` to go straight into the editor (chapter 5) without making the map again: the edited version is saved next to the original, on the same paper.

---

## 4. Rebuilding a map you already made

Every map has a **seed**: a code of 24 letters and digits in groups of four, like `475T-4KM4-MY0B-JNDJ-ZYEQ-K164`. The program shows it while it works and prints it under the title of the map. It's also the name of the map's folder inside `maps_generated` and the start of its file names.

The seed holds everything that shapes the land: the number of hexes, the cities, fortresses and dungeons, the terrain percentages, the rivers and all the random choices. So **the same seed always gives the same map**, on any computer, even if the map's files are gone. To share a map with someone, just give them its seed.

To rebuild a map, start the program, choose the language, answer `2` to "What do you want to do?" and type the seed. Capitals, dashes and spaces don't matter, and if you mistype a character the program tells you, instead of quietly making a different map. The program then shows the map's current title and scale and asks whether you want to **rename the map** and whether you want to **change the scale** (miles per hex: the same choices as for a new map, plus keeping a custom one as it is). Just press Enter to keep them. Then it asks again whether to use basic characters, black and white or colour and, at the end, the print format: so you can rebuild the same map under another name, at 24 miles per hex, or in A3 instead of A4, for example.

The title, the scale and the paper size aren't part of the seed, because they don't change the land. If the map's PNG is still in its folder `maps_generated/<seed>`, the program takes them from there (the paper size becomes the ready-made answer); otherwise it uses the starting title and scale. From the command line you can choose them yourself, for example `--reproduce <seed> --title "Northern Lands"`.

If you rebuild the map in a different language from the first time, the starting title and scale are translated (for example "Terre Selvagge" becomes "Wild Lands"); a title you chose yourself stays as it is.

The rebuilt map goes into the `maps_generated/<seed>` folder and replaces the files that were there. The letters are drawn with a font found on your computer: on a different computer they may look a little different, but hexes, terrains, rivers and sites are exactly the same.

**Maps made with earlier versions.** The first seeds of this kind, made before swamps existed, still work: they give the same map as before, without swamps. The same goes for seeds made before the prevailing wind or before peninsulas and archipelagos: they give the same map as before, laid out as it was then. Even earlier, the seed was a plain number, like `482913`, and it only worked together with the settings saved in the map's PNG. You can still type that number: if the PNG is found (in `maps_generated/482913` or in the program's folder), the map comes back the same and gets a seed of the new kind. If the PNG is gone, the program asks you to type in the same settings you used the first time.

---

## 5. Editing a map

You can change a map by hand, hex by hex, starting from its seed. If you've just made it, answer `y` when the program asks whether to edit it now (chapter 3). Otherwise start the program, choose the language, answer `3` to "What do you want to do?" and type the seed. As when rebuilding a map, it asks about the title, the scale and the look; then it builds the map and shows a table with one line per hex:

```
  Hex    Terrain   Dungeon  City  River  Direction   Fortress
  -----  --------  -------  ----  -----  ----------  --------
  03.07  forest    -        -     yes    south       -
```

The direction is where the river flows from that hex. Hexes have a flat top, so the six directions are north, north-east, south-east, south, south-west and north-west: there's no straight east or west.

On maps with more than 80 hexes the table only lists the hexes with sites, rivers or changes, plus the ones around the hex you just edited, so it doesn't fill the screen. Type `T` instead of a hex to see the full table.

Then:

1. Type the hex you want to change as column.row, for example `03.07` (`3.7` and `0307` work too).
2. Choose what to do with it: change the terrain; add or remove a dungeon, a city or a fortress; add a river that springs from that hex (the program traces it downhill, or you trace it yourself) or, if a river already flows through it, remove the whole river, move that stretch by one hex (the program only offers the directions the river doesn't already come from or flow to: if it runs from north to south, north and south aren't listed), or shorten the river so that it ends or springs right there.
3. The table comes back, updated. Choose whether to change another hex, make the map with the changes, **undo** the last change (you can undo several, one at a time), or **quit** without making the map.

When it asks for a hex you can also type `T` (full table), `U` (undo the last change) or `Q` (quit). In Italian they are `T`, `A` and `E`.

A few rules keep the map consistent:

- A hex holds at most one site: adding a city where there's a dungeon replaces the dungeon.
- Sites and rivers can't start on the sea or on lakes. If you turn a hex into water, its site is removed and a river flowing through it now ends there.
- A moved stretch of river is joined back to the rest through the nearby hexes. If that's not possible (there's water or another river, or the river would break apart), the program says so and changes nothing.
- A new river traced by the program flows downhill like the others. Heights follow your changes: if you've turned a plain into a mountain, the river starts as high up as the other mountains on the map.
- On low ground the program often can't find a way downhill. It then offers to let you **trace the river yourself**, which you can also choose straight away. Type the hexes after the spring, in order, separated by spaces, for example `03.08 04.08 05.09`: each one must touch the one before. To make the river flow into the water, end with a sea or lake hex; to make it join another river, end with a hex of that river. Otherwise it ends at the last hex you typed (or leaves the map, if that hex is on the edge).
- If a change alters how *another* river ends (you filled in the lake it flowed into, or removed the river it joined), the program tells you with a note, for example "the river that springs at 09.08 now ends at 08.06 without reaching water". Undo puts it back.
- Everything you didn't touch looks exactly as on the original map.

The edited map is saved in the same folder as the original, which stays as it is: `<seed>_edit_nonumber.png` and `<seed>_edit_number.png` (plus the .txt files), with "(edited)" after the seed under the title. The changes are saved in `<seed>_edit.json` after every single change, so you don't lose them if you quit or close the program halfway. The seed alone still gives the original map, but if you choose `3` again with the same seed, the program offers to pick up the saved changes: you can carry on editing, or just make the edited map again, for example on another paper size or in colour.

The changes are also stored inside the edited PNG: if `<seed>_edit.json` gets lost, the program finds them there. And if you rebuild a map that has an edited version (choice `2`, or `--reproduce`), it reminds you that the edited version exists and how to get it.

`<seed>_edit.json` is plain text, so you can also change it by hand. When the program reads it, it skips anything that doesn't make sense (a hex off the map, a city on the sea, a river with a gap in it) and tells you how many entries it skipped. If the file can't be read at all, the program doesn't write over it: it renames it `<seed>_edit_broken.json`, so nothing is lost, and starts again from the edits in the edited PNG or, if there are none, from the original map.

The editor itself only works through the questions. Once the changes are saved, though, you can make the edited map again from the command line with `--reproduce <seed> --edited` (chapter 8), for example on another paper size or in colour.

---

## 6. The files you get

The first time you use it, the program creates a folder called **`maps_generated`** next to `wyrmhex.py`. Inside it, every map gets a folder of its own, named after the map's seed (see chapter 4), holding its four files:

```
maps_generated/
  475T-4KM4-MY0B-JNDJ-ZYEQ-K164/
    475T-4KM4-MY0B-JNDJ-ZYEQ-K164_nonumber.png
    475T-4KM4-MY0B-JNDJ-ZYEQ-K164_nonumber.txt
    475T-4KM4-MY0B-JNDJ-ZYEQ-K164_number.png
    475T-4KM4-MY0B-JNDJ-ZYEQ-K164_number.txt
```

At the end, the program tells you which folder it saved the files in.

| File | What it is |
|---|---|
| `<seed>_nonumber.png` | The map without numbers, for the players |
| `<seed>_number.png` | The same map with a number in every hex, for the game master |
| `<seed>_nonumber.txt`, `<seed>_number.txt` | The map as text, which you can open with Notepad or TextEdit |
| `<seed>_edit_…`, `<seed>_edit.json` | Only if you edited the map (chapter 5): the edited map, and the list of changes |

Hex numbers have four digits: the first two are the column, the last two the row. `0101` is the top-left hex; `0305` is in the third column, fifth row.

---

## 7. Printing

The pictures already have the exact size of the paper you chose (A4, A3 or A2), at 600 dpi: they print sharp even on big sheets.

- Print on **the paper size you chose**, with the sheet the same way round as the picture (portrait or landscape). Black-and-white maps print fine on any printer; colour maps need a colour printer.
- A colour map with a **black background** uses a lot of ink: it's meant for screens (tablets, virtual tabletops) rather than paper.
- In the print options choose **"Actual size"** or **"100%"**. Avoid "Fit to page", which shrinks the map.
- If your printer only goes up to A4, a print shop can do A3 and A2: bring the PNG file as it is.

---

## 8. For people in a hurry: the options

Instead of answering the questions, you can type everything on one line. Any setting you leave out keeps its starting value. Examples, with the virtual environment active (see chapter 3):

```
python wyrmhex.py --language en --grid 30x15 --cities 4 --dungeons 6
python wyrmhex.py --language en --grid 50x30 --format A2
python wyrmhex.py --language en --sea 30 --plains 15 --title "Isle of Winds"
python wyrmhex.py --language en --reproduce 475T-4KM4-MY0B-JNDJ-ZYEQ-K164
python wyrmhex.py --language en --reproduce 475T-4KM4-MY0B-JNDJ-ZYEQ-K164 --edited --format A3
python wyrmhex.py --language en --grid 40x25 --random
```

Without `--language en` the messages and the texts on the map are in Italian. Every option also has an Italian name (in the table after the slash `/`), and you can mix them as you like.

| Option | What it does | Example |
|---|---|---|
| `--language` / `--lingua` | Language of the messages and of the texts on the map: `en` or `it` | `--language en` |
| `--grid` / `--griglia` | Columns x rows of hexes (`auto` = fills an A4) | `--grid 20x15` |
| `--cities`, `--fortresses`, `--dungeons` / `--citta`, `--fortezze`, `--dungeon` | How many sites of each kind (0 to 99) | `--cities 4` |
| `--plains`, `--sea`, `--lakes`, `--swamps`, `--hills`, `--mountains`, `--forests`, `--deserts` / `--pianura`, `--mare`, `--laghi`, `--paludi`, `--colline`, `--montagne`, `--foreste`, `--deserti` | Percentage of each terrain, as a whole number | `--sea 25` |
| `--rivers` / `--fiumi` | Number of rivers, up to 100 (`-1` = automatic) | `--rivers 3` |
| `--random` / `--casuale` | Picks the number of sites, the terrain percentages and the rivers at random, sized to the map. The options above for sites, terrains and rivers are then ignored. With the same `--seed` number you always get the same values | `--random` |
| `--title` / `--titolo` | Title at the top of the map | `--title "Northern Lands"` |
| `--scale` / `--scala` | Miles per hex: 2, 6 (default), 12, 24 or any other number. Free text, such as `"5 km"`, works too | `--scale 12` |
| `--seed` / `--seme` | With a full seed, rebuilds that map (like `--reproduce`). With a number from 0 to 1048575, makes a new map with your settings and that number for the random choices | `--seed 42` |
| `--reproduce` / `--riproduci` | Rebuilds the map of that seed. Title, scale and paper size come from its PNG if it's in `maps_generated/<seed>` (or in the `--output` folder); an old number seed needs its PNG | `--reproduce 475T-4KM4-MY0B-JNDJ-ZYEQ-K164` |
| `--edited` / `--modificata` | Together with `--reproduce` (or `--seed` with a full seed): makes the edited version of the map again, with the changes saved by the editor (chapter 5). If the map has no saved changes, the program says so and stops | `--reproduce <seed> --edited` |
| `--format` / `--formato` | Print format: `A4`, `A3` or `A2`. If you leave it out, the program asks you at the end, offering the suggested one (or, with `--reproduce`, the one from last time) | `--format A3` |
| `--orientation` / `--orientamento` | Usually not needed: the sheet direction follows the shape of the map. You can force it with `portrait` or `landscape` (`verticale` or `orizzontale`) | `--orientation portrait` |
| `--output` | Folder to save the maps in instead of `maps_generated`; there too, every map gets its own folder named after its seed | `--output maps` |
| `--ascii-only` / `--solo-ascii` | Use only plain keyboard letters and signs | `--ascii-only` |
| `--colors` / `--colori` | Colour map instead of black and white | `--colors` |
| `--background` / `--sfondo` | Background of the colour map: `white` (default) or `black` (`bianco` or `nero`). Only works together with `--colors` | `--colors --background black` |
| `--size` / `--dimensione` | `small` or `large` hexes (`piccola` or `grande`) | `--size large` |
| `--font` | Use a font file of your choice (all its letters must be the same width) | `--font consola.ttf` |

To see the full list of options, add `--help` after the file name (with `--language en --help` it's in English); to find out which version you have, add `--version`.

---

## 9. Common problems

**"py" / "python3" is not recognized as a command.**
Python isn't installed, or on Windows it wasn't added to the PATH. Reinstall it with "Add python.exe to PATH" ticked, then close and reopen the terminal.

**"Pillow is missing".**
The virtual environment isn't active: the line where you type doesn't start with `(.venv)`. Activate it (step 4 of the installation) and start the program again. If it still happens, the libraries aren't installed yet: do step 5.

**Windows: activating gives an error saying that "running scripts is disabled on this system".**
Windows' PowerShell terminal blocks scripts until you allow them. Type `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then activate again. You only need to do this once.

**macOS: `python wyrmhex.py` says "command not found: python".**
The virtual environment isn't active. On macOS the `python` command only exists inside the virtual environment (outside it there's only `python3`). Activate it (step 4) and try again.

**macOS and Linux: `source .venv/bin/activate` gives an error, or the line doesn't start with `(.venv)`.**
Your terminal may use a less common shell, which needs its own activation command. With **fish** type `source .venv/bin/activate.fish`; with **csh** or **tcsh** type `source .venv/bin/activate.csh`. The usual terminals of macOS (zsh) and Linux (bash) use `source .venv/bin/activate`, as in step 4.

**Linux: `python3 -m venv .venv` gives an error that mentions `ensurepip` or `venv`.**
A piece of Python is missing. On Ubuntu and Debian install it with `sudo apt install python3-venv`, then repeat step 3.

**"The terrain percentages add up to ...%, more than 100%".**
The percentages you typed add up to more than 100. Lower some of them.

**"... is not a valid seed".**
One of the characters of the seed is wrong or missing. Compare it with the name of the map's folder or with the line under the map's title. Capitals, dashes and spaces don't matter, and O and 0, or I, L and 1, count as the same character.

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
Versions before 0.0.2 could draw the black-and-white map as white on black; that's gone, and a black background is now only for colour maps. Rebuild the map from its seed (chapter 4): it comes back the same, black on white, or in colour on black if you choose colour and a black background.

---

## 10. Map Gallery

### 12 × 10 hexes

![12 x 10 map without numbers](img_examples/example_12x10_nonumber.png)
![12 x 10 map with numbers](img_examples/example_12x10_number.png)

### 20 × 5 hexes

![20 x 5 map without numbers](img_examples/example_20x5_nonumber.png)
![20 x 5 map with numbers](img_examples/example_20x5_number.png)

### 80 × 80 hexes

![80 x 80 map without numbers](img_examples/example_80x80_nonumber.png)
![80 x 80 map with numbers](img_examples/example_80x80.png)
