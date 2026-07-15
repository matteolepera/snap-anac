# ANAC SCRIPT 🚀

Questo progetto è un tool di estrazione dati resiliente progettato per l'acquisizione massiva e l'archiviazione locale dei dati di gara dalle API ufficiali di ANAC (Autorità Nazionale Anticorruzione).

Il sistema è diviso in due fasi sequenziali:

1. script_external.py (Download Indici): Scarica l'elenco dei metadati dei bandi/esiti per intervalli temporali e genera i file di indice.
2. script_dettaglio.py (Download Dettagli): Legge gli indici scaricati, estrae gli ID univoci e scarica la scheda dettagliata di ogni singolo provvedimento.

```text
[API ANAC] ──(1. Indici)──> script_external.py ──> 📁 dati/ (JSON Mensili)
                                                         │ (Legge gli ID)
                                                         ▼
[API ANAC] ──(2. Schede)──> script_dettaglio.py <────────┘
                                 │
                                 ├──> 📁 dettagli/ (JSON Singoli)
                                 └──> 📄 id_falliti.txt (Log Errori)
```


## 🛠️ Requisiti e Setup

Il progetto utilizza moduli standard di Python e la libreria requests per le chiamate HTTP.

```bash
  pip install requests python-dateutil
```

**Nota di portabilità:** I percorsi utilizzano pathlib.Path, garantendo la piena compatibilità cross-platform tra Windows (dove punta a C:\Users\Nome\Documents), macOS e Linux.

## 📂 Architettura dei Dati

La struttura delle cartelle viene creata dinamicamente all'interno della directory Documenti dell'utente:

```text
📁 Documents/
├── 📁 dati/                      <-- Generato da script_external.py
│   └── 📁 bandi_category/
│       └── 📁 bandi/
│           └── 📁 2025/
│               └── 📄 2025-01-01_2025-01-31.json  <-- Indici mensili
└── 📁 dettagli/                  <-- Generato da script_dettaglio.py
    └── 📁 bandi_category/
        └── 📁 bandi/
            └── 📁 2025/
                └── 📁 2025-01-01_2025-01-31/
                    ├── 📄 1234567.json            <-- Scheda dettaglio singola
                    └── 📄 id_falliti.txt          <-- ID non scaricati (es. 404 o timeout persistenti)
```

## 🚀 Guida Operativa

Per completare un'acquisizione, gli script vanno eseguiti in ordine.

### Step 1: Scarica gli Indici dei Bandi
Scarica l'elenco dei bandi per il periodo desiderato. Lo script suddivide automaticamente il range in blocchi mensili.

### Parametri disponibili

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `--data-inizio` | `str` | **Richiesto** | Data iniziale nel formato `gg/mm/aaaa` |
| `--data-fine` | `str` | **Richiesto** | Data finale nel formato `gg/mm/aaaa` |
| `--categoria` | `str` | **Richiesto** | Categoria ANAC da scaricare (es. `bandi`, `risultati`, `affidamenti_diretti_sotto_soglia`) |
| `--dimensione-pagina` | `int` | `5000` | Numero massimo di record per richiesta API |
| `--granularita-mesi` | `int` | `1` | Numero di mesi inclusi in ogni file JSON |
| `--attesa-pagine` | `float` | `4.0` | Secondi di attesa tra le pagine dello stesso periodo |
| `--attesa-periodi` | `float` | `7.0` | Attesa base prima del periodo successivo |


### Esempio di utilizzo

```bash
python script_external.py \
  --data-inizio 01/01/2025 \
  --data-fine 31/12/2025 \
  --categoria bandi \
```

### Step 2: Scarica i Dettagli delle Schede
Una volta completato il primo script, avvia il secondo per scaricare i file di dettaglio di tutti gli ID trovati negli indici.

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `--categoria` | `str` | **Richiesto** | Categoria ANAC da scaricare (es. `bandi`, `risultati`, `affidamenti_diretti_sotto_soglia`) |
| `--attesa-chiamate` | `float` | `3.0` | Attesa base prima di passare allo scaricamento del id successvio |


### Esempio di utilizzo

```bash
python script_dettaglio.py \
  --categoria bandi \
```

## 🔧 Guida alla Manutenzione

Se devi modificare, aggiornare o estendere questo codice, tieni a mente questi punti chiave:

1. Come aggiungere una nuova categoria o aggiornare l'endpoint
Le configurazioni dell'API ANAC sono centralizzate in `script_external.py`. Lo `script_dettaglio.py` le importa direttamente per evitare disallineamenti.

- Endpoint Base: Modifica la costante `URL_API` se ANAC cambia l'indirizzo delle sue API.

- Mappatura Categorie: Se ANAC introduce una nuova tipologia di bando o esito, aggiorna il dizionario `categorie`:

```bash
# script_external.py
categorie = {
    "bandi_category": {
        "bandi": "4",
        "avvisi_di_indizione": "2",
        "nuova_sotto_categoria": "99"  # <-- Aggiungi qui (Chiave: ID_Scheda_ANAC)
    },
    # ...
}
```

2. Gestione degli errori di rete e rate limiting
Per evitare che l'IP venga bloccato o che lo script si blocchi a metà notte:

- Backoff Esponenziale: La funzione `chiamata_con_retry` esegue fino a 1000 tentativi in caso di errori di rete o HTTP `429` (Too Many Requests) e `5xx`. Il tempo di attesa raddoppia ad ogni tentativo fallito.

- Fast Failure: In caso di errore `403` (Forbidden) o `404` (Not Found), lo script si ferma immediatamente per quel blocco per evitare cicli infiniti di chiamate non autorizzate o inesistenti.

- Jittering: Alla fine di ogni periodo, lo script applica un delay casuale (`random.uniform(0, 1.5)`) per imitare un comportamento umano ed eludere i sistemi anti-bot.

3. Sicurezza dei dati
Entrambi gli script utilizzano una tecnica di scrittura atomica per evitare la corruzione dei file JSON in caso di interruzione improvvisa della corrente o arresto dello script:

- I dati vengono scritti in un file temporaneo .json.tmp.

- Solo se la scrittura si conclude con successo, il file viene rinominato (replace) nel percorso definitivo.

- Se lo script si interrompe a metà, non troverai mai un file .json corrotto o parziale.

## 🩹 Gestione dei Fallimenti

Durante il download dei dettagli, se una scheda fallisce sistematicamente (es. dopo tutti i tentativi di retry), l'ID viene registrato nel file id_falliti.txt all'interno della cartella della categoria.

- Cosa fare con gli ID falliti? Il file viene aggiornato in modalità append evitando duplicati. In futuro, è possibile creare uno script di recupero che legga direttamente questo file di testo per tentare un download mirato solo delle schede mancanti.