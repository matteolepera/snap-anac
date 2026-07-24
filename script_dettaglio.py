import json
import argparse
import time
import math
import re
import stat

from script_external import (
    chiamata_con_retry,
    salva_file_json,
    headers_default,
    CARTELLA_DOCUMENTI,
    categorie,
    URL_API,
    record_ha_id_valido,
)

PATTERN_ID_AVVISO = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)

def id_avviso_sicuro(id_avviso):
    if not isinstance(id_avviso, str):
        return False

    if len(id_avviso) > 240:
        return False
    
    return PATTERN_ID_AVVISO.fullmatch(id_avviso) is not None

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

    if any(
        not id_avviso_sicuro(avviso["idAvviso"])
        for avviso in lista_avvisi
    ):
        return None, "id_avviso_non_sicuro"
    
    # Set comprehension
    id_avvisi =  {
        avviso["idAvviso"]
        for avviso in lista_avvisi
    }

    return id_avvisi, None

def raccogli_tutti_gli_id(macro_categoria, sotto_categoria): 

    risultato = []

    file_ignorati = 0

    percorsi_file = trova_file_lista(macro_categoria, sotto_categoria)

    totale_file = len(percorsi_file)

    print(f"[INFO] File lista individuati: "f"{totale_file}")

    for indice_file, percorso_file in enumerate(percorsi_file, start=1):
        print(f"[LETTURA LISTE] "f"{indice_file}/{totale_file}: "f"{percorso_file.name}")

        id_del_file, motivo = estrai_id_da_file(percorso_file)
        if id_del_file is None:
            file_ignorati += 1
            print(f"[AVVISO] File lista ignorato: "f"{percorso_file.name} ({motivo})")
            continue

        risultato.append((percorso_file, id_del_file))

    return risultato, file_ignorati

def costruisci_percorso_dettaglio(macro_categoria, sotto_categoria, anno, periodo, id_avviso):
    if not id_avviso_sicuro(id_avviso):
        raise ValueError(f"ID avviso non utilizzabile nel percorso: "f"{id_avviso!r}")

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

def valida_dati_dettaglio(dati, id_avviso_atteso=None):

    if not isinstance(dati, dict):
        return False, "struttura_non_valida"

    if not dati:
        return False, "dettaglio_vuoto"

    if (id_avviso_atteso is not None and "idAvviso" in dati):
        id_avviso_ricevuto = dati["idAvviso"]

        if (not isinstance(id_avviso_ricevuto, str) or id_avviso_ricevuto != id_avviso_atteso):
            return False, "id_avviso_non_coerente"

    return True, None

def controlla_file_dettaglio(percorso_file):
    try:
        informazioni_file = percorso_file.stat()

    except FileNotFoundError:
        return False, "file_mancante"
    
    except OSError:
        return False, "errore_lettura_file"

    if not stat.S_ISREG(informazioni_file.st_mode):
        return False, "percorso_non_file"

    if informazioni_file.st_size == 0:
        return False, "file_vuoto"

    return True, None

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
    
    dettaglio_valido, motivo = valida_dati_dettaglio(dati, id_avviso)

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

    try:
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
        return True
    
    except(OSError, UnicodeError) as errore_log:

        print(f"  [AVVISO LOG] Impossibile registrare " f"il fallimento di {id_avviso}: {errore_log}")

        return False

def main():

    print("########## AVVIO SCRIPT DETTAGLIO ##########")

    parser = argparse.ArgumentParser(description="Script per il download dei dettagli")
    parser.add_argument("--categoria", required=True, help="Sotto-categoria da elaborare, ad esempio: bandi")
    parser.add_argument("--attesa-chiamate", type=float, default=1.6, help="Secondi di attesa tra due chiamate dettaglio (default: 1.6)")
    args = parser.parse_args()

    if (not math.isfinite(args.attesa_chiamate) or args.attesa_chiamate < 0):
        print("Errore: --attesa-chiamate deve essere un numero " "finito maggiore o uguale a 0.")
        return 2

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
        return 2

    raccolta_id, file_lista_ignorati = raccogli_tutti_gli_id(macro_categoria, args.categoria)
    if not raccolta_id:
        print("[AVVISO] Nessun file lista valido trovato " "per la categoria richiesta.")
        return 1
    totale_id_da_controllare = sum(len(id_set) for _, id_set in raccolta_id)
    totale_id_controllati = 0
    print(f"[INFO] Avvio controllo rapido di "f"{totale_id_da_controllare} dettagli.")
    
    lavoro_da_scaricare = []
    totale_gia_presenti = 0
    totale_dettagli_non_validi = 0

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

            dettaglio_valido, motivo = controlla_file_dettaglio(percorso_dettaglio)

            if dettaglio_valido:
                totale_gia_presenti += 1
            else:
                if motivo != "file_mancante":
                    totale_dettagli_non_validi += 1

                    print(f"[AVVISO] Dettaglio non valido: " f"{percorso_dettaglio.name} ({motivo}). " f"Verrà riscaricato.")

                id_mancanti.append(id_avviso)

            totale_id_controllati += 1
            
            if(totale_id_controllati % 1000 == 0 or totale_id_controllati== totale_id_da_controllare):
                percentuale = (totale_id_controllati / totale_id_da_controllare * 100)
                print(f"[CONTROLLO] " f"{totale_id_controllati}/" f"{totale_id_da_controllare} dettagli " f"verificati ({percentuale:.1f}%)")

        lavoro_da_scaricare.append((percorso_lista, len(id_set), id_mancanti))

    statistiche = {
    "file_lista": len(raccolta_id),
    "file_lista_ignorati": file_lista_ignorati,
    "dettagli_non_validi": totale_dettagli_non_validi,
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
    print(f"[INFO] File lista validi: " f"{statistiche['file_lista']}")
    print(f"[INFO] File lista ignorati: " f"{statistiche['file_lista_ignorati']}")
    print(f"[INFO] ID unici nei rispettivi periodi: {statistiche['id_trovati']}")

    print(f"[INFO] Dettagli già presenti e validi: " f"{statistiche['saltati']}")
    print(f"[INFO] Dettagli esistenti non validi: " f"{statistiche['dettagli_non_validi']}")
    print(f"[INFO] Dettagli da scaricare: " f"{statistiche['da_scaricare']}")

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

            except OSError as errore_disco:
                print(f"  [ERRORE FATALE DISCO] Impossibile salvare " f"il dettaglio {id_avviso}: {errore_disco}")
                print( "  Interrompo lo script per evitare altri " "download che non possono essere salvati.")

                registra_id_fallito(id_avviso, macro_categoria, args.categoria, "errore_disco")

                statistiche["falliti"] += 1
                return 1
            
            except Exception as errore_imprevisto:
                print(f"  [CRASH EVITATO] Errore imprevisto su {id_avviso}: {errore_imprevisto}")
                registra_id_fallito(id_avviso, macro_categoria, args.categoria, "crash_imprevisto")
                statistiche["falliti"] += 1
                time.sleep(args.attesa_chiamate)

    elaborati_durante_esecuzione = (statistiche["scaricati"] + statistiche["falliti"])
    esito_con_errori = (statistiche["falliti"] > 0 or statistiche["file_lista_ignorati"] > 0)

    print("\n" + "=" * 50)
    if esito_con_errori:
        print("   DOWNLOAD DETTAGLI COMPLETATO CON ERRORI")
    else:
        print("       DOWNLOAD DETTAGLI COMPLETATO")
    
    print("=" * 50)
    print(f"File lista elaborati:       "f"{statistiche['file_lista']}")
    print(f"File lista ignorati:        "f"{statistiche['file_lista_ignorati']}")
    print(f"ID trovati:                 "f"{statistiche['id_trovati']}")
    print(f"Dettagli già presenti:        "f"{statistiche['saltati']}")
    print(f"Dettagli esistenti invalidi:      "f"{statistiche['dettagli_non_validi']}")
    print(f"Dettagli da scaricare:      "f"{statistiche['da_scaricare']}")
    print(f"Dettagli elaborati ora:     "f"{elaborati_durante_esecuzione}")
    print(f"Dettagli scaricati:           "f"{statistiche['scaricati']}")
    print(f"Dettagli falliti:           "f"{statistiche['falliti']}")
    print("=" * 50)

    if esito_con_errori:
        return 1
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())