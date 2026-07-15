import json
import argparse
import time

from script_external import (
    chiamata_con_retry,
    salva_file_json,
    headers_default,
    CARTELLA_DOCUMENTI,
    categorie,
    URL_API,
)

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


def main():

    parser = argparse.ArgumentParser(description="Script per il download dei dettagli")
    parser.add_argument("--categoria", required=True, help="Sotto-categoria da elaborare, ad esempio: bandi")
    parser.add_argument("--attesa-chiamate", type=float, default=3.0, help="Secondi di attesa tra due chiamate dettaglio (default: 3)")
    args = parser.parse_args()

    if args.attesa_chiamate < 0:
        print("Errore: --attesa-chiamate non può essere negativa.")
        return

    macro_categoria = None

    for macro, sotto_categorie in categorie.items():
        if args.categoria in sotto_categorie:
            macro_categoria = macro
            break

    if macro_categoria is None:
        opzioni = [
            sotto_categoria
            for sotto_categorie in categorie.values()
            for sotto_categoria in sotto_categorie
        ]
        print(
            f"Errore: categoria '{args.categoria}' non valida. "
            f"Opzioni disponibili: {', '.join(opzioni)}"
        )
        return

    raccolta_id = raccogli_tutti_gli_id(macro_categoria, args.categoria)

    statistiche = {
        "file_lista": len(raccolta_id),
        "id_trovati": sum(len(id_set) for _, id_set in raccolta_id),
        "scaricati": 0,
        "saltati": 0,
        "falliti": 0,
    }

    print(f"[INFO] Categoria: {args.categoria}")
    print(f"[INFO] File lista trovati: {statistiche['file_lista']}")
    print(f"[INFO] ID unici nei rispettivi periodi: {statistiche['id_trovati']}")

    totale_id_processati = 0

    for percorso_lista, id_set in raccolta_id:
        anno = percorso_lista.parent.name
        periodo = percorso_lista.stem

        print(f"\n[INFO] Elaboro periodo: {periodo} ({len(id_set)} ID)")

        for indice, id_avviso in enumerate(id_set, start=1):

            totale_id_processati += 1

            print(f"[{indice}/{len(id_set)} periodo | "
            f"{totale_id_processati}/{statistiche['id_trovati']} totale] "
            f"ID: {id_avviso}")

            try:
                percorso_dettaglio = costruisci_percorso_dettaglio(
                    macro_categoria,
                    args.categoria,
                    anno,
                    periodo,
                    id_avviso,
                )

                if percorso_dettaglio.exists():
                    print(f"  [SKIP] Dettaglio già presente: {id_avviso}")
                    statistiche["saltati"] += 1
                    continue

                print(f"  [DOWNLOAD] ")
                dettaglio = scarica_dettaglio(
                    URL_API,
                    id_avviso,
                    headers_default,
                )

                if dettaglio is None:
                    print(f"  [ERRORE] Dettaglio non scaricato: {id_avviso}")
                    registra_id_fallito(id_avviso, macro_categoria, args.categoria)
                    statistiche["falliti"] += 1
                else:
                    salva_file_json(dettaglio, percorso_dettaglio)
                    statistiche["scaricati"] += 1

                time.sleep(args.attesa_chiamate)

            except Exception as errore_imprevisto:
                print(f"  [CRASH EVITATO] Errore imprevisto su {id_avviso}: {errore_imprevisto}")
                registra_id_fallito(id_avviso, macro_categoria, args.categoria)
                statistiche["falliti"] += 1

    print("\n" + "=" * 50)
    print("       DOWNLOAD DETTAGLI COMPLETATO")
    print("=" * 50)
    print(f"File lista elaborati:       {statistiche['file_lista']}")
    print(f"ID trovati:                 {statistiche['id_trovati']}")
    print(f"Dettagli scaricati:         {statistiche['scaricati']}")
    print(f"Dettagli già presenti:      {statistiche['saltati']}")
    print(f"Dettagli falliti:           {statistiche['falliti']}")
    print("=" * 50)

if __name__ == "__main__":
    main()