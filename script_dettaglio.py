from pathlib import Path
import json

from script_external import (
    chiamata_con_retry,
    salva_file_json,
    headers_default,
    CARTELLA_DOCUMENTI,
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

