from pathlib import Path
import json

from script_external import (
    chiamata_con_retry,
    salva_file_json,
    headers_default,
    CARTELLA_DOCUMENTI,
    categorie,
    URL_API,
)

from script_external import chiamata_con_retry, salva_file_json, headers_default, CARTELLA_DOCUMENTI

print("########## AVVIO SCRIPT DETTAGLIO ##########")

def trova_file_lista(macro_categoria, sotto_categoria):
    # Costruisce il percorso della cartella dove cercare.
    cartella = (
        CARTELLA_DOCUMENTI
        / "dati"
        / macro_categoria
        / sotto_categoria
    )

    # Controllo se quella cartella non esiste restituisci una lista vuota.
    if not cartella.exists():
        return []

    # Cerca ricorsivamente tutti i file che finiscono in .json, sorted() li ordina alfabeticamente.
    return sorted(cartella.rglob("*.json"))

def estrai_id_da_file(percorso_file):
    with open(percorso_file, "r", encoding="utf-8") as file:
        #  legge il contenuto del file e lo converte da testo JSON a struttura dati Python.
        lista_avvisi = json.load(file)

    # Set comprehension
    return {
        avviso["idAvviso"]
        for avviso in lista_avvisi
        # Per ogni avviso, applica due controlli in sequenza
        # isinstance(avviso, dict) verifica che avviso sia effettivamente un dizionario
        # "idAvviso" in avviso verifica che quel dizionario contenga la chiave "idAvviso" 
        if isinstance(avviso, dict) and "idAvviso" in avviso
    }

def raccogli_tutti_gli_id(macro_categoria, sotto_categoria): 

    risultato = []

    for percorso_file in trova_file_lista(macro_categoria, sotto_categoria):
        id_del_file = estrai_id_da_file(percorso_file)
        risultato.append((percorso_file, id_del_file))

    return risultato

def costruisci_percorso_dettaglio(macro_categoria, sotto_categoria, anno, periodo, id_avviso):
    nome_file = f"{id_avviso}.json"

    return (
        CARTELLA_DOCUMENTI
        / "dettagli"
        / macro_categoria
        / sotto_categoria
        / anno
        / periodo
        / nome_file
    )

def scarica_dettaglio(url_base, id_avviso, headers):
    # rstrip rimuove eventuali caratteri / solo alla fine della stringa, da destra.
    url_dettaglio = f"{url_base.rstrip('/')}/{id_avviso}"

    risposta = chiamata_con_retry(url_dettaglio, headers=headers)

    return risposta.json() if risposta is not None else None

def registra_id_fallito(id_avviso, macro_categoria, sotto_categoria):
    percorso_log = (
        CARTELLA_DOCUMENTI
        / "dettagli"
        / macro_categoria
        / sotto_categoria
        / "id_falliti.txt"
    )

    percorso_log.parent.mkdir(parents=True, exist_ok=True)

    id_gia_registrati = set()

    if percorso_log.exists():
        with open(percorso_log, "r", encoding="utf-8") as file_log:
            id_gia_registrati = {
                riga.strip()
                for riga in file_log
                if riga.strip()
            }

    if str(id_avviso) not in id_gia_registrati:
        with open(percorso_log, "a", encoding="utf-8") as file_log:
            file_log.write(f"{id_avviso}\n")


if __name__ == "__main__":
    risultati = raccogli_tutti_gli_id("bandi_category", "bandi")
    
    print(f"Trovati {len(risultati)} file di lista")
    
    for percorso_file, id_set in risultati:
        anno = percorso_file.parent.name
        periodo = percorso_file.stem
        print(f"  {periodo} (anno {anno}): {len(id_set)} ID trovati")
    
    totale_id = sum(len(id_set) for _, id_set in risultati)
    print(f"\nTotale ID complessivi (con eventuali duplicati tra file): {totale_id}")

    risultati = raccogli_tutti_gli_id("bandi_category", "bandi")
    percorso_lista, id_set = risultati[0]   # il primo file trovato
    un_id = next(iter(id_set))               # un ID qualsiasi da quel set, solo per test

    anno = percorso_lista.parent.name
    periodo = percorso_lista.stem
    percorso_dettaglio = costruisci_percorso_dettaglio("bandi_category", "bandi", anno, periodo, un_id)

    print(percorso_dettaglio)

    url_base = "https://pubblicitalegale.anticorruzione.it/api/v0/avvisi"

    risultati = raccogli_tutti_gli_id("bandi_category", "bandi")
    percorso_lista, id_set = risultati[0]
    un_id = next(iter(id_set))

    dettaglio = scarica_dettaglio(url_base, un_id, headers_default)

    if dettaglio is not None:
        print(f"Scaricato con successo, chiavi principali: {list(dettaglio.keys())}")
    else:
        print("Scarico fallito")