# WyrmHex

```
 _       __                     __  __
| |     / /_  ___________ ___  / / / /__  _  __
| | /| / / / / / ___/ __ `__ \/ /_/ / _ \| |/_/
| |/ |/ / /_/ / /  / / / / / / __  /  __/>  <
|__/|__/\__, /_/  /_/ /_/ /_/_/ /_/\___/_/|_|
       /____/

                    v0.0.1
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

**WyrmHex** è un piccolo programma che disegna a caso una mappa a esagoni per campagne di gioco di ruolo old school (OSR). La mappa è fatta solo di lettere e simboli, come nei vecchi videogiochi Dwarf Fortress e Moonring:

- **foreste** `♣♠`, **montagne** `▲^`, **colline** `∩n`, **deserti** `░·`, **laghi** `≈`;
- la **pianura** resta vuota e il **mare** è una campitura grigia;
- i **fiumi** sono doppie linee `═║╔╗`;
- **città**, **fortezze** e **dungeon** sono riquadri neri con un simbolo bianco.

La mappa esce in bianco e nero, pronta da stampare su un foglio A4. Ogni volta ottieni due immagini della stessa mappa: una **senza numeri** (da mostrare ai giocatori) e una **con il numero in ogni esagono** (per il master).

---

## 1. Cosa ti serve

Metti questi file nella **stessa cartella**, per esempio una cartella `mappe` sul Desktop:

- `wyrmhex.py` (il programma)
- `requirements.txt`
- questo `README.md`

Ti serve anche **Python 3.14**, il programma che fa funzionare i file `.py`. Vanno bene anche versioni un po' più vecchie, dalla 3.11 in su.

---

## 2. Installazione (si fa una volta sola)

### Passo 1 — Installa Python

- **Windows e macOS:** vai su <https://www.python.org/downloads/>, scarica Python 3.14 e installalo come un normale programma.
  - Su Windows, se durante l'installazione compare la casella **"Add python.exe to PATH"**, spuntala.
- **Linux:** Python di solito è già installato. Se la tua distribuzione non ha la 3.14, va bene anche la versione che hai, purché sia la 3.11 o successiva.

### Passo 2 — Apri il terminale nella cartella dei file

Il terminale è una finestra in cui si scrivono comandi.

- **Windows 11:** apri la cartella `mappe`, fai clic destro in uno spazio vuoto e scegli **"Apri nel Terminale"**.
- **Windows 10:** apri la cartella `mappe`, fai clic sulla barra dell'indirizzo in alto, scrivi `cmd` e premi Invio.
- **macOS:** apri l'app **Terminale** (in Applicazioni → Utility). Scrivi `cd` seguito da uno spazio, trascina la cartella `mappe` dentro la finestra e premi Invio.
- **Linux:** apri la cartella, fai clic destro in uno spazio vuoto e scegli **"Apri nel terminale"**.

### Passo 3 — Prepara il programma

Copia i comandi qui sotto **uno alla volta** e premi Invio dopo ciascuno. Il primo crea, dentro la cartella, uno spazio riservato al programma: una sottocartella nascosta `.venv`, che non devi toccare. Il secondo scarica **Pillow**, la libreria che serve a creare le immagini.

**Windows**
```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**macOS e Linux**
```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Se alla fine compare una riga che inizia con `Successfully installed`, è tutto pronto.

---

## 3. Creare una mappa

Apri il terminale nella cartella, come al passo 2, e scrivi:

**Windows**
```
.venv\Scripts\python wyrmhex.py
```

**macOS e Linux**
```
.venv/bin/python wyrmhex.py
```

All'avvio compare la schermata di benvenuto, con il titolo e un disegno: premi **INVIO** per cominciare. Poi il programma ti fa alcune domande. **Ogni domanda ha una risposta già pronta tra parentesi quadre: se ti va bene, premi solo Invio.**

1. **Cosa vuoi fare?** Scrivi `1` per una mappa nuova, `2` per rifare una mappa già fatta (vedi il capitolo 4).
2. **Esagoni in base e in altezza:** quante colonne e quante righe di esagoni vuoi. La risposta pronta è `auto`: il programma sceglie da solo quanti esagoni riempiono il foglio restando leggibili (33 × 15).
3. **Numero di dungeon, città e fortezze** da mettere sulla mappa.
4. **Percentuali di terreno:** quanta parte della mappa è pianura, mare, laghi, colline, montagne, foreste e deserti. La somma non può superare 100; se resta qualcosa, diventa pianura. Se sbagli, il programma te lo dice e ti fa reinserire i numeri.
5. **Numero di fiumi:** con `-1` il programma decide da solo.
6. **Titolo** stampato in cima alla mappa.
7. Due domande sull'aspetto: se usare **solo i caratteri base della tastiera** (senza simboli come ♣ ▲ ≈) e se fare la mappa con lo **sfondo nero** e i segni bianchi. Per una mappa da stampare rispondi **no** (basta premere Invio) a tutte e due: lo sfondo nero è pensato per lo schermo e in stampa consuma moltissimo inchiostro.

Mentre lavora, il programma mostra i passaggi che sta facendo. Alla fine elenca dove sono le città, le fortezze e i dungeon, con il numero del loro esagono: comodo per gli appunti del master.

---

## 4. Rifare una mappa già fatta

Ogni mappa ha un **seme**: il numero all'inizio del nome del file. Per esempio, il seme di `482913_nonumber.png` è `482913`.

Per rifare esattamente quella mappa, avvia il programma, alla prima domanda rispondi `2` e scrivi il seme. Il file della mappa deve trovarsi nella cartella in cui avvii il programma: ogni immagine conserva al suo interno le impostazioni con cui è stata creata, e il programma le rilegge da lì. Ti chiede solo di nuovo le due domande sull'aspetto (caratteri base e sfondo nero), perché non cambiano la mappa: così puoi, per esempio, rifare con lo sfondo bianco una mappa creata per sbaglio con lo sfondo nero.

Se il file non c'è più, il programma ti chiede di reinserire a mano **le stesse impostazioni** usate la prima volta. Il seme da solo non basta: con impostazioni diverse esce una mappa diversa.

---

## 5. I file che ottieni

I file vengono salvati nella cartella in cui hai avviato il programma:

| File | Cos'è |
|---|---|
| `482913_nonumber.png` | La mappa senza numeri, per i giocatori |
| `482913_number.png` | La stessa mappa con il numero in ogni esagono, per il master |
| `482913_nonumber.txt`, `482913_number.txt` | La mappa come testo, apribile con il Blocco note |

I numeri degli esagoni hanno quattro cifre: le prime due indicano la colonna, le ultime due la riga. `0101` è l'esagono in alto a sinistra; `0305` è nella terza colonna, quinta riga.

---

## 6. Stampare

Le immagini sono già della misura esatta di un foglio A4 a 300 dpi, in orizzontale.

- Stampa su **A4 orizzontale**, in bianco e nero.
- Nelle opzioni di stampa scegli **"Dimensioni effettive"** o **"100%"**. Evita "Adatta alla pagina", che rimpicciolisce la mappa.

---

## 7. Per chi vuole andare più veloce: le opzioni

Invece di rispondere alle domande, puoi scrivere tutto su una riga. Le impostazioni che non scrivi prendono il valore di partenza. Esempi (su Windows usa `.venv\Scripts\python` al posto di `.venv/bin/python`):

```
.venv/bin/python wyrmhex.py --griglia 30x15 --citta 4 --dungeon 6
.venv/bin/python wyrmhex.py --mare 30 --pianura 15 --titolo "Isola dei Venti"
.venv/bin/python wyrmhex.py --riproduci 482913
```

| Opzione | Cosa fa | Esempio |
|---|---|---|
| `--griglia` | Colonne x righe di esagoni (`auto` = riempie il foglio) | `--griglia 20x15` |
| `--citta`, `--fortezze`, `--dungeon` | Quanti siti di ogni tipo | `--citta 4` |
| `--pianura`, `--mare`, `--laghi`, `--colline`, `--montagne`, `--foreste`, `--deserti` | Percentuale di ogni terreno | `--mare 25` |
| `--fiumi` | Numero di fiumi (`-1` = automatico) | `--fiumi 3` |
| `--titolo` | Titolo in cima alla mappa | `--titolo "Terre del Nord"` |
| `--scala` | Testo della scala | `--scala "8 km"` |
| `--seme` | Usa un seme preciso invece di uno a caso | `--seme 42` |
| `--riproduci` | Rifà la mappa con quel seme, leggendo le impostazioni dal suo file (cercato nella cartella di `--output` e in quella corrente) | `--riproduci 482913` |
| `--orientamento` | `orizzontale` (predefinito), `verticale` o `auto` | `--orientamento verticale` |
| `--output` | Cartella in cui salvare i file | `--output mappe` |
| `--solo-ascii` | Usa solo lettere e segni semplici della tastiera | `--solo-ascii` |
| `--invertito` | Sfondo nero con segni bianchi, per lo schermo (anche con `--riproduci`: senza questa opzione la mappa rifatta ha lo sfondo bianco) | `--invertito` |
| `--dimensione` | Esagoni `piccola` o `grande` | `--dimensione grande` |
| `--font` | Usa un file di carattere a tua scelta (deve avere tutte le lettere della stessa larghezza) | `--font consola.ttf` |

Per vedere l'elenco completo delle opzioni, aggiungi `--help` dopo il nome del file; per sapere quale versione hai, aggiungi `--version`.

---

## 8. Problemi comuni

**"py" / "python3" non è riconosciuto come comando.**
Python non è installato, oppure su Windows non è stato aggiunto al PATH. Reinstallalo spuntando "Add python.exe to PATH", poi chiudi e riapri il terminale.

**"Manca la libreria Pillow".**
Non hai fatto il passo 3, oppure stai avviando il programma con `py` o `python3` invece che con `.venv\Scripts\python` (Windows) o `.venv/bin/python` (macOS/Linux).

**Linux: `python3 -m venv .venv` dà un errore che parla di `ensurepip` o `venv`.**
Manca un pezzo di Python. Su Ubuntu e Debian installalo con `sudo apt install python3-venv`, poi ripeti il passo 3.

**"La somma delle percentuali di terreno è ...%, supera il 100%".**
Le percentuali che hai scritto, sommate, fanno più di 100. Abbassane qualcuna.

**"servono N esagoni di terra per i siti, ma la mappa ne ha solo M".**
Hai chiesto troppi siti per una mappa piccola o con troppa acqua. Riduci il numero di siti, ingrandisci la griglia o diminuisci mare e laghi.

**Il programma dice "Caratteri molto piccoli".**
La griglia è troppo grande per un A4: la mappa si stampa, ma sarà difficile da leggere. Usa meno esagoni, oppure lascia la griglia su `auto`.

**Alcuni simboli sono diventati lettere semplici.**
Il carattere installato sul computer non ha quei simboli. Il programma li sostituisce da solo e te lo segnala. Puoi indicare un altro carattere con `--font`, per esempio `--font DejaVuSansMono.ttf`, se è installato.

**La mappa stampata è più piccola del foglio o spostata.**
Nelle opzioni di stampa scegli "Dimensioni effettive" o "100%", non "Adatta alla pagina".

**Il disegno della schermata di benvenuto appare tagliato a destra.**
La finestra del terminale è troppo stretta: il disegno è largo 94 caratteri e il programma lo taglia per non scombinarlo. Allarga la finestra e riavvia il programma.

**Le immagini hanno lo sfondo nero.**
Alla domanda sullo sfondo nero è stato risposto sì. Rifai la mappa dal suo seme (capitolo 4) e rispondi no, oppure usa `--riproduci` con il seme: la mappa torna uguale, con lo sfondo bianco.
