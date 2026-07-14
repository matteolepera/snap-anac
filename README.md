# ANAC Public Tenders Downloader 🚀

Questo strumento automatizza il download massivo dei dati relativi a bandi ed esiti di gara direttamente dalle API ufficiali di **ANAC (Autorità Nazionale Anticorruzione)**. 

Lo script è progettato con criteri di livello enterprise: gestisce la rete in modo resiliente (con retry e backoff esponenziale), evita la corruzione dei dati tramite salvataggi atomici temporanei, supporta il caching locale (skip dei file già scaricati) e riduce l'impatto sui server ANAC grazie a delay configurabili e jitter casuale.

---

## 📂 Struttura dell'Output Generato

I file scaricati vengono organizzati automaticamente nella cartella `Documenti` dell'utente secondo una gerarchia logica e ordinata:

```text
📁 Documents/
└── 📁 dati/
    ├── 📁 bandi_category/
    │   ├── 📁 bandi/
    │   │   └── 📁 2025/
    │   │       └── 📄 2025-01-01_2025-01-31.json
    │   └── 📁 avvisi_di_indizione/
    └── 📁 esiti_category/
        ├── 📁 risultati/
        └── ...
```

---

## 🎯 Stato di Avanzamento del Progetto

Tutte le fasi di sviluppo sono state completate e integrate con successo. Lo script è pronto per l'uso in ambiente di produzione.

## 🟢 Fase 1 — Utility, Validazione e Gestione File

Componenti isolati per la sicurezza dei dati e la robustezza del codice.

### ✅ 1.1 Analisi e Validazione Date (`_analizza_data`)

- Parsing sicuro delle stringhe di data.
- Gestione delle eccezioni in caso di formato non conforme.

### ✅ 1.2 Validazione dei Parametri di Input (`valida_parametri`)

- Controllo di sicurezza sulla dimensione massima della pagina (tetto di sicurezza a **5000 record**).
- Verifica della corretta sequenzialità temporale:
  - la data di inizio non può essere successiva alla data di fine;
  - la data finale non può trovarsi nel futuro.
- Controllo dell'esistenza della categoria rispetto al dizionario di configurazione ANAC.

### ✅ 1.3 Generatore Dinamico dei Periodi (`genera_periodi`)

- Suddivisione del range temporale in blocchi mensili configurabili.
- Gestione automatica dei confini dell'anno solare (es. termine al **31/12**).

### ✅ 1.4 Generazione Percorsi Standardizzata (`costruisci_percorso`)

- Implementazione tramite `pathlib.Path`.
- Compatibilità cross-platform:
  - Windows
  - macOS
  - Linux

### ✅ 1.5 Scrittura Atomica e Sicura (`salva_file_json`)

- Creazione automatica delle cartelle mancanti.
- Salvataggio mediante file temporaneo (`.json.tmp`).
- Sovrascrittura atomica del file finale per evitare corruzioni in caso di crash improvvisi.

---

# 🟢 Fase 2 — Core Client & Logica di Rete (API ANAC)

Integrazione con gli endpoint ministeriali e gestione proattiva degli errori di rete.

### ✅ 2.1 Connessione Resiliente con Backoff Esponenziale (`chiamata_con_retry`)

- Fino a **5 tentativi** automatici.
- Gestione distinta degli errori:
  - **HTTP 429** e **5xx** → nuovo tentativo con attesa raddoppiata.
  - **HTTP 403** e **404** → interruzione immediata per evitare richieste inutili.

### ✅ 2.2 Chiamata Sonda di Controllo (`ottieni_totale_elementi`)

- Richiesta preliminare con `size=1`.
- Recupero del valore `totalElements` per conoscere il numero esatto dei record disponibili.

### ✅ 2.3 Calcolo Dinamico delle Pagine (`calcola_numero_pagine`)

- Calcolo matematico del numero di richieste necessarie in funzione della dimensione della pagina.

### ✅ 2.4 Scaricamento della Singola Pagina (`scarica_pagina`)

- Download parametrizzato dei dati.
- Gestione sicura di:
  - header HTTP;
  - parametri di paginazione;
  - sessione.

---

# 🟢 Fase 3 — Orchestrazione, CLI e Ciclo di Vita

Il cuore dell'applicazione: coordinamento dei moduli in un flusso continuo ed efficiente.

### ✅ 3.1 Interfaccia a Riga di Comando (`main` con `argparse`)

Configurazione completa tramite terminale di:

- intervallo temporale;
- categoria;
- granularità;
- tempi di attesa;
- dimensione delle pagine.

### ✅ 3.2 Sistema di Caching Locale ("Smart Skip")

- Riconoscimento automatico dei periodi già scaricati.
- Ripresa dei download interrotti senza duplicare i dati.

### ✅ 3.3 Isolamento dei Fallimenti dei Singoli Blocchi

- Gli errori relativi a un singolo periodo vengono intercettati e registrati.
- Lo script continua automaticamente con i periodi successivi.

### ✅ 3.4 Algoritmo di Jittering Anti-Bot

- Introduzione di una pausa casuale (`random.uniform`) al termine di ogni blocco.
- Simulazione di un comportamento umano.
- Riduzione del rischio di rate limiting o blocchi IP.

### ✅ 3.5 Reportistica Finale

Al termine dell'esecuzione viene mostrato un riepilogo contenente:

- blocchi completati;
- blocchi saltati;
- blocchi falliti;
- totale dei record salvati.

---

# 🛠️ Guida Rapida all'Uso

Lo script è completamente configurabile da riga di comando.

## Parametri disponibili

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `--data-inizio` | `str` | **Richiesto** | Data iniziale nel formato `gg/mm/aaaa` |
| `--data-fine` | `str` | **Richiesto** | Data finale nel formato `gg/mm/aaaa` |
| `--categoria` | `str` | **Richiesto** | Categoria ANAC da scaricare (es. `bandi`, `risultati`, `affidamenti_diretti_sotto_soglia`) |
| `--dimensione-pagina` | `int` | `5000` | Numero massimo di record per richiesta API |
| `--granularita-mesi` | `int` | `1` | Numero di mesi inclusi in ogni file JSON |
| `--attesa-pagine` | `float` | `4.0` | Secondi di attesa tra le pagine dello stesso periodo |
| `--attesa-periodi` | `float` | `7.0` | Attesa base prima del periodo successivo |

---

## Esempio di utilizzo

```bash
python nome_script.py \
  --data-inizio 01/01/2025 \
  --data-fine 31/12/2025 \
  --categoria bandi \
  --granularita-mesi 1 \
  --dimensione-pagina 1000
```
