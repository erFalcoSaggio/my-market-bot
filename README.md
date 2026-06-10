# 🤖 Radar Azioni (24/7, gratis)

Bot che tiene d'occhio una **watchlist di azioni** e ti avvisa su **Telegram** quando una
**crolla**, così sai dove andare a guardare. Non è un oracolo: è un **radar**. Il tuo PAC
sull'MSCI World resta **separato e intoccabile** — qui si parla solo di azioni singole.

> ⚠️ **Non è una previsione né un consiglio finanziario.** Un'azione crollata può essere
> un'occasione *o* una "trappola di valore" (è scesa perché l'azienda sta peggiorando).
> Il bot ti dice **dove guardare**, non cosa comprare: capisci *perché* è scesa prima di
> agire, usa solo soldi che puoi perderti, e tieni le posizioni piccole.

## Quando ti avvisa (solo cali forti → poche notifiche)
Un avviso scatta se un'azione della watchlist:
- **crolla ≥7% in un giorno**, oppure
- è a **−30% o più dai massimi** a 52 settimane, oppure
- è **sui minimi degli ultimi 12 mesi** (entro il 3%).

Più un **promemoria settimanale** (lunedì) con la fotografia della watchlist. Anti-spam:
lo stesso avviso non si ripete prima di 48 ore.

## Watchlist iniziale (modificabile in `config.yaml`)
Apple, Microsoft, Nvidia, Amazon, Alphabet (Google), Meta, Tesla.

## File principali
| File | Ruolo |
|------|-------|
| `bot.py` | orchestratore: scarica, valuta, avvisa |
| `signals.py` | calcolo cali (giornaliero, dai massimi, vicino ai minimi) |
| `data.py` | dati di mercato (Yahoo Finance) |
| `notify.py` | formattazione messaggi + invio Telegram |
| `config.yaml` | watchlist, soglie, anti-spam (modificabile) |
| `state.json` | stato (avvisi già inviati) |
| `.github/workflows/bot.yml` | esecuzione automatica ogni 30 min su GitHub Actions |

## Comandi utili
```bash
pip install -r requirements.txt
python bot.py --dry-run            # mostra a video cosa farebbe, senza inviare
python bot.py --test --dry-run     # esempi (benvenuto + watchlist + avviso di crollo)
python bot.py --status --dry-run   # forza il promemoria settimanale
TELEGRAM_TOKEN="..." python get_chat_id.py   # ricava il chat_id Telegram
```

## Personalizzare
In `config.yaml`: aggiungi/togli azioni (ticker Yahoo, es. `AAPL`, `KO`, `RACE.MI` per
Ferrari a Milano), cambia le soglie dei cali, accendi le crypto, sposta il promemoria.

## Limiti onesti
- Dati Yahoo ritardati ~15–20 min e a volte si auto-limitano.
- GitHub Actions: intervallo minimo 5 min, possibili ritardi di qualche minuto.
- Il radar ti dice *dove guardare*, non garantisce nulla: la decisione (e il rischio) sono tuoi.
