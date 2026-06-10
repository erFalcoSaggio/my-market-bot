# 🤖 Trade Bot — analisi mercati + alert (24/7, gratis)

Bot che monitora i mercati 24/7 e ti avvisa su **Telegram** quando succede qualcosa
di rilevante (cali importanti, movimenti forti, indicatori tecnici). **Non compra e
non vende nulla**: legge solo dati pubblici e ti dà contesto. **Decidi sempre tu.**

> ⚠️ **Non è un consiglio finanziario.** Gli indicatori sono euristiche su dati storici,
> non previsioni. Nessun bot retail prevede i mercati in modo affidabile. La strategia
> più solida per la tua età resta il PAC su un ETF mondiale diversificato.

## Cosa controlla
- **Asset** (configurabili in `config.yaml`): il tuo ETF MSCI World, S&P 500, Bitcoin,
  Ethereum, EUR/USD, oro, petrolio.
- **Segnali**: calo % dai massimi a 52 settimane, movimento giornaliero forte, RSI(14),
  incrocio medie mobili 50/200 (golden/death cross), vicinanza a massimi/minimi annuali.
- **Report**: un riepilogo giornaliero + alert puntuali (con anti-spam).

## Come funziona (architettura)
| File | Ruolo |
|------|-------|
| `bot.py` | orchestratore: scarica, analizza, invia, salva stato |
| `data.py` | dati di mercato (Yahoo Finance, fallback CoinGecko per le crypto) |
| `signals.py` | calcolo indicatori e generazione alert |
| `notify.py` | formattazione messaggi + invio Telegram |
| `config.yaml` | watchlist e soglie (modificabile) |
| `state.json` | stato (per non inviare alert doppi) |
| `.github/workflows/bot.yml` | esecuzione automatica ogni 30 min su GitHub Actions |

## Setup (una volta sola)

### 1. Crea il bot Telegram
1. Su Telegram cerca **@BotFather**, invia `/newbot` e segui le istruzioni.
2. Copia il **token** che ti dà (una stringa tipo `123456:ABC-...`).
3. Apri la chat con il tuo nuovo bot, premi **START** e scrivigli un messaggio qualsiasi.
4. Ricava il tuo `chat_id`:
   ```bash
   TELEGRAM_TOKEN="il-tuo-token" python get_chat_id.py
   ```

### 2. Test in locale (non invia nulla con --dry-run)
```bash
pip install -r requirements.txt
python bot.py --dry-run            # stampa a video cosa farebbe
python bot.py --test --dry-run     # esempio di messaggi
```
Per provare l'invio vero su Telegram:
```bash
TELEGRAM_TOKEN="..." TELEGRAM_CHAT_ID="..." python bot.py --test
```

### 3. Pubblica su GitHub (gira 24/7 gratis)
1. Crea una repo su GitHub e carica questi file.
   > 💡 Conviene una repo **pubblica**: i minuti di GitHub Actions sono illimitati e
   > gratis. Il codice non contiene segreti (stanno nei *Secrets*), quindi è sicuro.
2. In **Settings → Secrets and variables → Actions** aggiungi:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Vai su **Actions**, abilita i workflow e lancia *trade-bot* a mano (Run workflow)
   per la prima volta. Poi parte da solo ogni 30 minuti.

## Personalizzare
Modifica `config.yaml`: aggiungi/togli ticker, cambia le soglie degli alert, l'ora del
digest. **Conferma il ticker esatto del tuo ETF MSCI World** (es. `SWDA.MI`, `EUNL.DE`).

## Limiti onesti
- I dati Yahoo sono ritardati di ~15–20 min e a volte si auto-limitano (c'è un fallback).
- GitHub Actions ha un intervallo minimo di 5 min e può ritardare di qualche minuto nei
  picchi: per alert "al secondo" servirebbe un server a pagamento (~5€/mese).
- Per restare attivo, il bot ricommitta `state.json` a ogni run (GitHub disabilita i cron
  dopo 60 giorni di inattività della repo).
