# Checklist di revisione — commonbrain

Questa è la lista di **tutto ciò che viene controllato su ogni Pull Request**, sempre.
Serve a chi mantiene il repo (anche senza essere tecnico) per capire cosa è già stato
verificato in automatico e cosa resta da decidere a una persona.

> Su ogni PR un bot pubblica un **commento in italiano** che applica questa checklist:
> cosa ha verificato la macchina (✅/❌), cosa dice la lezione, un parere AI consultivo, e
> le domande che decidi tu. Il commento è solo un aiuto: **la decisione di merge è governata
> dai controlli automatici** (il check obbligatorio `gate-passed`) e, per i contributi
> esterni, dal tuo merge manuale.

## 1. Controlli automatici — la macchina (bloccanti)

Ogni voce è un job della CI; se anche solo una fallisce, la PR **non** può essere mergiata.
Girano dalla versione del repo (non dalla copia della PR), quindi una PR non può indebolirli.

| Controllo | Cosa garantisce |
|---|---|
| `path-allowlist` | La PR tocca **solo** `lessons/` e `html/` (non può alterare gate, schema o workflow). |
| `schema-validate` | La lezione ha il **formato** corretto (campi, tipi, lunghezze). |
| `secret-scan` | **Nessun segreto** (token, chiavi, password); non viene nemmeno stampato in chiaro. |
| `injection-sanitize` | **Nessuna manipolazione** del lettore-agente (prompt injection, ruoli, comandi). |
| `html-scan` | L'eventuale HTML è **senza script** o gestori di eventi. |
| `generality-lint` | **Nessun dato privato**: niente path personali (`/Users/...`), nomi riservati, email reali. |
| `generality-scorecard` | La lezione è **generale e di qualità** sopra soglia (anti-slop). |
| `dedup` | **Non è un doppione** di una lezione già presente. |
| `build-artifact` | Il pacchetto dati (`lessons.jsonl`) **si ricostruisce** correttamente. |
| `gate-passed` | Job riassuntivo: verde **solo** se tutti i precedenti passano. È l'unico check obbligatorio. |

## 2. Parere AI — consultivo (NON decide)

Se è configurata una chiave AI, un modello legge la lezione (**trattata come dato non fidato,
mai come istruzioni**) e dà un parere in italiano:

- È una lezione di coding **reale** e plausibile?
- È **generale** o specifica di un progetto?
- È **chiara** e riproducibile?
- Sembra **slop / spam / fuori tema**?

⚠️ L'AI **non può approvare né mergiare**: è solo un secondo paio d'occhi che spiega. Anche se
un contributo malevolo provasse a "convincerla", non avrebbe alcun potere sul merge.

## 3. Decidi tu — l'umano

Quello che la macchina non può giudicare:

1. **Mi fido della fonte?** (chi/cosa ha aperto la PR — un tuo agent? uno sconosciuto?)
2. **È sensata e in tema?** (un consiglio di coding reale, non pubblicità/fuori tema/assurdità)
3. **La voglio pubblicata col mio nome?** (sei tu il responsabile di ciò che diventa pubblico)

## 4. Come si arriva al merge

- **PR dei tuoi agent** (stesso repo, autore fidato) che passano il gate → **auto-merge**: si
  mergiano da sole, ma **solo** dopo che `gate-passed` è verde.
- **PR esterne** (da fork / sconosciuti) → **non** si auto-mergiano mai: leggi il commento del
  bot, applica le 3 domande qui sopra, e **mergi tu**.
- Una PR rossa non si merge: i controlli automatici hanno trovato un problema.
