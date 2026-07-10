FIRST SCRIPT

# Roadmap di sviluppo

Questa checklist suddivide il progetto in tre fasi, partendo dalle funzioni indipendenti fino allo script principale. L'ordine suggerito permette di sviluppare e testare ogni componente prima di integrarlo con gli altri.

---

# ✅ Fase 1 — Funzioni isolate (senza dipendenze)

Queste funzioni possono essere implementate e testate singolarmente.

## ☐ 1.1 `valida_parametri(data_inizio_str, data_fine_str, categoria)`

**Scopo**

Validare i parametri ricevuti da `argparse` prima di effettuare qualsiasi chiamata.

**Controlli da effettuare**

- [ ] Verificare che `categoria` esista nel dizionario delle categorie.
- [ ] Verificare che `data_inizio_str` sia nel formato corretto (`datetime.strptime`).
- [ ] Verificare che `data_fine_str` sia nel formato corretto.
- [ ] Controllare che `data_inizio < data_fine`.
- [ ] Controllare che `data_fine` non sia successiva alla data odierna.

**Output**

- [ ] Restituire `True` oppure
- [ ] Sollevare un'eccezione con un messaggio d'errore chiaro (consigliato).

**Test**

- [ ] Parametri validi.
- [ ] Categoria inesistente.
- [ ] Data con formato errato.
- [ ] Data iniziale successiva alla data finale.
- [ ] Data finale nel futuro.

---

## ☐ 1.2 `mese_successivo(anno, mese)`

**Scopo**

Restituire anno e mese successivi.

**Test**

- [ ] Marzo → Aprile.
- [ ] Dicembre → Gennaio dell'anno successivo.

---

## ☐ 1.3 `genera_mesi(data_inizio_str, data_fine_str)`

**Dipendenza**

- Richiede `mese_successivo()`.

**Scopo**

Generare tutte le coppie `(anno, mese)` comprese nell'intervallo richiesto.

**Test**

- [ ] Intero anno → 12 tuple.
- [ ] Un solo mese → 1 tupla.
- [ ] Novembre 2025 → Febbraio 2026 → 4 tuple.

---

## ☐ 1.4 `costruisci_percorso(categoria, anno, mese)`

**Scopo**

Costruire il percorso del file JSON senza creare nulla su disco.

**Esempio**

```text
dati/bandi/2025/2025-01.json
```

**Test**

- [ ] Il mese deve essere sempre formattato con due cifre (`01`, `02`, ...).

---

## ☐ 1.5 `crea_cartelle_se_mancanti(percorso_file)`

**Scopo**

Creare automaticamente la cartella destinazione se non esiste.

**Suggerimento**

Utilizzare:

```python
os.path.dirname(percorso_file)
```

per ottenere la directory.

**Test**

- [ ] Chiamata su cartella inesistente.
- [ ] Chiamata ripetuta sulla stessa cartella (nessun errore).

---

## ☐ 1.6 `file_mese_esiste(percorso_file)`

**Scopo**

Wrapper di `os.path.exists()`.

**Test**

- [ ] File esistente.
- [ ] File inesistente.

---

## ☐ 1.7 `salva_json(dati, percorso_file)`

**Scopo**

Salvare una lista o un dizionario in formato JSON.

**Requisiti**

- [ ] Encoding UTF-8.
- [ ] Chiamare prima `crea_cartelle_se_mancanti()`.

**Test**

- [ ] Salvare una lista di esempio.
- [ ] Verificare che il file venga creato e sia leggibile.

---

## ☐ 1.8 `chiamata_con_retry(url, parametri, headers, tentativi_massimi, attesa_iniziale)`

**Scopo**

Effettuare una richiesta HTTP con retry e backoff esponenziale.

**Test**

- [ ] URL valido.
- [ ] URL inesistente con retry visibili.

---

# ✅ Fase 2 — Funzioni composte

Queste funzioni utilizzano quelle sviluppate nella Fase 1.

---

## ☐ 2.1 `ottieni_totale_elementi(url, categoria, anno, mese, headers)`

**Scopo**

Effettuare la chiamata "probe" (`size=1`) per conoscere il numero totale degli elementi del mese.

**Attività**

- [ ] Costruire le date di inizio e fine mese.
- [ ] Calcolare l'ultimo giorno del mese.
- [ ] Chiamare `chiamata_con_retry()`.
- [ ] Restituire `totalElements`.
- [ ] Restituire `None` in caso di fallimento.

**Test**

- [ ] Dicembre 2025 → atteso 3110 elementi.
- [ ] Mese futuro o vuoto → 0 elementi.

---

## ☐ 2.2 `calcola_numero_pagine(totale_elementi, dimensione_pagina)`

**Scopo**

Calcolare il numero di pagine necessarie.

**Test**

- [ ] Pochi elementi → 1 pagina.
- [ ] Molti elementi → numero corretto di pagine.

---

## ☐ 2.3 `scarica_pagina(url, categoria, anno, mese, numero_pagina, dimensione_pagina, headers)`

**Scopo**

Scaricare una singola pagina di risultati.

**Output**

- [ ] Restituire la lista `content`.

**Test**

- [ ] Dicembre 2025, pagina 0.
- [ ] Verificare che `len(content)` sia coerente.

---

## ☐ 2.4 `scarica_mese(url, categoria, anno, mese, dimensione_pagina, headers)`

**Scopo**

Funzione orchestratrice del download di un mese.

**Flusso**

- [ ] Chiamare `ottieni_totale_elementi()`.
- [ ] Calcolare il numero di pagine.
- [ ] Iterare su `scarica_pagina()`.
- [ ] Accumulare tutti gli elementi.
- [ ] Inserire `time.sleep()` tra le pagine quando necessario.

**Output**

- [ ] Lista completa degli elementi.
- [ ] Gestione esplicita dei casi:
  - [ ] `None`
  - [ ] 0 elementi
  - [ ] errore

**Test**

- [ ] Scaricare tutto dicembre 2025.

---

# ✅ Fase 3 — Script principale

---

## ☐ 3.1 `processa_mese(url, categoria, anno, mese, dimensione_pagina, headers)`

**Scopo**

Gestire il workflow completo di un singolo mese.

**Flusso**

- [ ] Verificare se il file esiste già.
- [ ] Saltare il download se presente.
- [ ] Scaricare il mese.
- [ ] Salvare il JSON.
- [ ] Scrivere il log.

**Gestione casi particolari**

- [ ] Zero elementi → salvare comunque una lista vuota.
- [ ] Fallimento definitivo → loggare l'errore e continuare.

---

## ☐ 3.2 `main()`

**Scopo**

Coordinare l'intero programma.

**Attività**

- [ ] Leggere gli argomenti da `argparse`.
- [ ] Chiamare `valida_parametri()`.
- [ ] Determinare le categorie da elaborare.
- [ ] Gestire il caso `"entrambi"`.
- [ ] Generare la lista dei mesi.
- [ ] Eseguire il doppio ciclo:
  - [ ] Categoria
  - [ ] Mese
- [ ] Chiamare `processa_mese()` per ogni combinazione.
- [ ] Inserire una pausa (`time.sleep()`) tra un mese e il successivo.

**Output finale**

Stampare un riepilogo con:

- [ ] Mesi processati.
- [ ] Mesi saltati.
- [ ] Mesi falliti.
- [ ] Totale elementi scaricati.

---

# 📋 Stato avanzamento

## Fase 1

- [ ] 1.1 Valida parametri
- [ ] 1.2 Mese successivo
- [ ] 1.3 Genera mesi
- [ ] 1.4 Costruisci percorso
- [ ] 1.5 Crea cartelle
- [ ] 1.6 Verifica esistenza file
- [ ] 1.7 Salva JSON
- [ ] 1.8 Chiamata con retry

## Fase 2

- [ ] 2.1 Ottieni totale elementi
- [ ] 2.2 Calcola numero pagine
- [ ] 2.3 Scarica pagina
- [ ] 2.4 Scarica mese

## Fase 3

- [ ] 3.1 Processa mese
- [ ] 3.2 Main

---

## 🎯 Obiettivo finale

Al completamento di tutte le attività, lo script sarà in grado di:

- validare gli input;
- generare automaticamente i mesi da elaborare;
- scaricare tutti i dati disponibili tramite API;
- salvare ogni mese in un file JSON organizzato per categoria e anno;
- riprendere l'esecuzione senza riscaricare i file già presenti;
- gestire errori di rete tramite retry;
- produrre un riepilogo finale dell'elaborazione.