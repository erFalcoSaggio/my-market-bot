# 🤖 Market Bot — "compra quando è in sconto" (24/7, gratis)

Bot **semplice e diretto**: controlla 24/7 quanto il mercato mondiale (MSCI World) è
sceso dai suoi massimi e, quando c'è uno **sconto** rilevante, ti scrive su **Telegram**
dicendoti in modo netto **cosa comprare e quanto**. Pochi messaggi, niente rumore.

> ⚠️ **Non è una previsione né un consiglio finanziario.** È una *regola di disciplina*
> ("accumula di più quando il mercato è a sconto"), non un oracolo. Nessun bot prevede i
> mercati. Compra solo con liquidità che non ti serve per anni, e continua sempre il PAC.

## Come funziona
1. Misura il calo del mercato mondiale dai massimi a 52 settimane (`SWDA.MI`, MSCI World in €).
2. Lo confronta con una **scala di sconti** (`config.yaml`):

   | Calo dai massimi | Segnale | Acquisto extra indicativo |
   |---|---|---|
   | −10% | 🟢 SCONTO | ~50€ |
   | −15% | 🟢🟢 BUON SCONTO | ~100€ |
   | −20% | 🟢🟢🟢 OCCASIONE | ~150€ |
   | −30% | 🟢🟢🟢🟢 OCCASIONE RARA | ~200€ |

3. Ti avvisa **solo quando lo sconto si approfondisce** (es. entri nel −15%), così non
   ricevi messaggi inutili. Più un **promemoria tranquillo una volta a settimana**.
4. Un calo viene presentato come **opportunità** (🟢 sconto), non come perdita: utile e
   senza ansia.

Crypto (BTC/ETH) opzionale e spento di default: si attiva da `config.yaml` ed è etichettato
come più rischioso ("soldi che puoi perderti").

## File principali
| File | Ruolo |
|------|-------|
| `bot.py` | orchestratore: misura lo sconto, decide il segnale, invia |
| `signals.py` | calcolo del calo dai massimi + scala degli sconti |
| `data.py` | dati di mercato (Yahoo Finance, fallback CoinGecko per le crypto) |
| `notify.py` | formattazione messaggi + invio Telegram |
| `config.yaml` | termometro, scala degli sconti, importi (modificabile) |
| `state.json` | stato (a che gradino di sconto siamo) |
| `.github/workflows/bot.yml` | esecuzione automatica ogni 30 min su GitHub Actions |

## Comandi utili
```bash
pip install -r requirements.txt
python bot.py --dry-run            # mostra a video cosa farebbe, senza inviare
python bot.py --test --dry-run     # esempi dei messaggi (benvenuto + segnale d'acquisto)
python bot.py --status --dry-run   # forza il promemoria settimanale
TELEGRAM_TOKEN="..." python get_chat_id.py   # ricava il tuo chat_id Telegram
```

## Setup (già fatto, qui per riferimento)
1. Bot Telegram con **@BotFather** → token; `python get_chat_id.py` per il chat_id.
2. Su GitHub: **Settings → Secrets and variables → Actions** → `TELEGRAM_TOKEN`,
   `TELEGRAM_CHAT_ID`. Repo **pubblica** = minuti Actions gratis e illimitati.
3. **Actions** → esegui *trade-bot* una volta a mano; poi parte da solo ogni 30 min.

## Personalizzare
In `config.yaml`: cambia le soglie e gli importi (`dip_ladder`), accendi le crypto,
sposta il giorno/ora del promemoria. Gli importi adattali a quanta liquidità hai da parte.

## Limiti onesti
- Dati Yahoo ritardati ~15–20 min (c'è un fallback per le crypto).
- GitHub Actions: intervallo minimo 5 min, possibili ritardi di qualche minuto.
- La regola "compra gli sconti" è sensata e storicamente solida, **ma non garantisce**
  guadagni: il mercato può scendere ancora dopo che hai comprato. Serve orizzonte lungo.
