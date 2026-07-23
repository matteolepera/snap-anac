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
    record_ha_id_valido,
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
    try:
        with open(percorso_file, "r", encoding="utf-8") as file:
         #  legge il contenuto del file e lo converte da testo JSON a struttura dati Python.
            lista_avvisi = json.load(file)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, "json_non_valido"
    
    except OSError:
        return None, "errore_lettura_file"
    
    if not isinstance(lista_avvisi, list):
        return None, "struttura_non_valida"

    if any(
        not record_ha_id_valido(avviso)
        for avviso in lista_avvisi
    ):
        return None, "record_non_validi"
    # Set comprehension
    id_avvisi =  {
        avviso["idAvviso"]
        for avviso in lista_avvisi
    }

    return id_avvisi, None

def raccogli_tutti_gli_id(macro_categoria, sotto_categoria): 

    risultato = []

    for percorso_file in trova_file_lista(macro_categoria, sotto_categoria):
        id_del_file, motivo = estrai_id_da_file(percorso_file)

        if id_del_file is None:
            print(f"[AVVISO] File lista ignorato: " f"{percorso_file.name} ({motivo})")
            continue
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

def valida_dati_dettaglio(dati):

    if not isinstance(dati, dict):
        return False, "struttura_non_valida"

    if not dati:
        return False, "dettaglio_vuoto"

    return True, None

def controlla_file_dettaglio(percorso_file):

    if not percorso_file.exists():
        return False, "file_mancante"

    try:
        with open(percorso_file, "r", encoding="utf-8") as file:
            dati = json.load(file)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return False, "json_non_valido"

    except OSError:
        return False, "errore_lettura_file"

    return valida_dati_dettaglio(dati)

def scarica_dettaglio(url_base, id_avviso, headers):
    # rstrip rimuove eventuali caratteri / solo alla fine della stringa, da destra.
    url_dettaglio = f"{url_base.rstrip('/')}/{id_avviso}"

    risposta, motivo = chiamata_con_retry(url_dettaglio, headers=headers)

    if risposta is None:
        return None, motivo

    try:
        dati = risposta.json()
    except ValueError:
        return None, "json_non_valido"
    
    dettaglio_valido, motivo = valida_dati_dettaglio(dati)

    if not dettaglio_valido:
        return None, motivo

    return dati, None

def registra_id_fallito(id_avviso, macro_categoria, sotto_categoria, motivo):
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
                riga.strip().split(";", 1)[0]
                for riga in file_log
                if riga.strip()
            }

    if str(id_avviso) not in id_gia_registrati:
        with open(percorso_log, "a", encoding="utf-8") as file_log:
            file_log.write(f"{id_avviso};{motivo}\n")


def main():

    parser = argparse.ArgumentParser(description="Script per il download dei dettagli")
    parser.add_argument("--categoria", required=True, help="Sotto-categoria da elaborare, ad esempio: bandi")
    parser.add_argument("--attesa-chiamate", type=float, default=1.6, help="Secondi di attesa tra due chiamate dettaglio (default: 2.0)")
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

    lavoro_da_scaricare = []
    totale_gia_presenti = 0

    for percorso_lista, id_set in raccolta_id:
        anno = percorso_lista.parent.name
        periodo = percorso_lista.stem

        id_mancanti = []

        for id_avviso in id_set:
            percorso_dettaglio = costruisci_percorso_dettaglio(
                macro_categoria,
                args.categoria,
                anno,
                periodo,
                id_avviso,
            )

            dettaglio_valido, motivo = controlla_file_dettaglio(
                percorso_dettaglio
            )

            if dettaglio_valido:
                totale_gia_presenti += 1
            else:
                if motivo != "file_mancante":
                    print(f"[AVVISO] Dettaglio non valido: " f"{percorso_dettaglio.name} ({motivo}). " f"Verrà riscaricato.")

                id_mancanti.append(id_avviso)

        lavoro_da_scaricare.append((percorso_lista, len(id_set), id_mancanti))

    statistiche = {
    "file_lista": len(raccolta_id),
    "id_trovati": sum(len(id_set) for _, id_set in raccolta_id),
    "da_scaricare": sum(
        len(id_mancanti)
        for _, _, id_mancanti in lavoro_da_scaricare
    ),
    "scaricati": 0,
    "saltati": totale_gia_presenti,
    "falliti": 0,
}

    print(f"[INFO] Categoria: {args.categoria}")
    print(f"[INFO] File lista trovati: {statistiche['file_lista']}")
    print(f"[INFO] ID unici nei rispettivi periodi: {statistiche['id_trovati']}")

    totale_id_processati = 0

    for percorso_lista, totale_periodo, id_da_scaricare in lavoro_da_scaricare:
        anno = percorso_lista.parent.name
        periodo = percorso_lista.stem
        gia_presenti_periodo = totale_periodo - len(id_da_scaricare)

        print(f"\n[INFO] Periodo {periodo}: {totale_periodo} totali, {gia_presenti_periodo} già presenti, {len(id_da_scaricare)} da scaricare")

        for indice, id_avviso in enumerate(id_da_scaricare, start=1):

            totale_id_processati += 1

            print(f"[{indice}/{len(id_da_scaricare)} da scaricare nel periodo "
            f"{periodo} | {totale_id_processati}/{statistiche['da_scaricare']} totale] "
            f"ID: {id_avviso}")

            try:
                percorso_dettaglio = costruisci_percorso_dettaglio(
                    macro_categoria,
                    args.categoria,
                    anno,
                    periodo,
                    id_avviso,
                )

                print(f"  [DOWNLOAD] ")
                dettaglio, motivo = scarica_dettaglio(
                    URL_API,
                    id_avviso,
                    headers_default,
                )

                if dettaglio is None:
                    print(f"  [ERRORE] Dettaglio non scaricato: {id_avviso}")
                    registra_id_fallito(id_avviso, macro_categoria, args.categoria, motivo)
                    statistiche["falliti"] += 1
                else:
                    salva_file_json(dettaglio, percorso_dettaglio)
                    statistiche["scaricati"] += 1

                time.sleep(args.attesa_chiamate)

            except Exception as errore_imprevisto:
                print(f"  [CRASH EVITATO] Errore imprevisto su {id_avviso}: {errore_imprevisto}")
                registra_id_fallito(id_avviso, macro_categoria, args.categoria, "crash_imprevisto")
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