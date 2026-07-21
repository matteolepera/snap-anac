import argparse
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
import json
import time
import requests
import random

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_DESC = "gg/mm/aaaa"

CARTELLA_DOCUMENTI = Path.home() / "Documents"

# Header HTTP usati per richiedere risposte JSON
# e dichiarare un client compatibile con il portale.
headers_default = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://pubblicitalegale.anticorruzione.it/",
    "Origin": "https://pubblicitalegale.anticorruzione.it",
}

# Dizionario con le chiavi di ogni categoria da scaricare
categorie = {
    "bandi_category": {"bandi": "4", "avvisi_di_indizione": "2"},
    "esiti_category": {
        "risultati": "7",
        "affidamenti_diretti_sotto_soglia": "8a",
        "preavvisi_di_aggiudicazione_diretta": "9",
    },
}

# === CONFIGURAZIONE ENDPOINT ANAC ===
URL_API = "https://pubblicitalegale.anticorruzione.it/api/v0/avvisi"
SESSIONE_HTTP = requests.Session()


# Funzione con_ sarebbe funzione privata
def _analizza_data(data_str, nome_campo):
    try:
        return datetime.strptime(data_str, FORMATO_DATA).date()
    except ValueError:
        raise ValueError(
            f"La data di {nome_campo} deve essere nel formato {FORMATO_DATA_DESC}."
        )


def valida_parametri(
    data_inizio_str,
    data_fine_str,
    categoria_utente,
    struttura_categorie,
    dimensione_pagina,
):
    # Funzione che valida i parametri ricevuti da argparse.
    # Controllo valore e tetto massimo della dimensione pagina
    if not isinstance(dimensione_pagina, int) or dimensione_pagina <= 0:
        raise ValueError(
            "La dimensione della pagina deve essere un numero intero positivo maggiore di 0."
        )

    TETTO_MASSIMO = 5000  # Limite provvisorio per i test
    if dimensione_pagina > TETTO_MASSIMO:
        raise ValueError(
            f"La dimensione della pagina richiesta ({dimensione_pagina}) supera il tetto massimo "
            f"prudenziale di {TETTO_MASSIMO}. Riduci il valore per evitare rifiuti dal server ANAC."
        )

    # Controllo e conversione delle date
    data_inizio = _analizza_data(data_inizio_str, "inizio")
    data_fine = _analizza_data(data_fine_str, "fine")

    if data_inizio > data_fine:
        raise ValueError(
            "La data di inizio non può essere successiva alla data di fine."
        )

    oggi = datetime.today().date()
    if data_fine > oggi:
        raise ValueError("La data di fine non può essere successiva alla data odierna.")

    # Ricerca della sotto-categoria nel dizionario nidificato
    macro_categoria = None
    id_categoria = None

    for macro, sotto_dizionario in struttura_categorie.items():
        if categoria_utente in sotto_dizionario:
            macro_categoria = macro
            id_categoria = sotto_dizionario[categoria_utente]
            break

    # Se non troviamo l'ID, la categoria inserita dall'utente è errata
    if not id_categoria:
        tutte_disponibili = []
        for sotto_dizionario in struttura_categorie.values():
            tutte_disponibili.extend(sotto_dizionario.keys())
        raise ValueError(
            f"Categoria '{categoria_utente}' non valida.\n"
            f"Opzioni disponibili: {', '.join(tutte_disponibili)}"
        )

    return data_inizio, data_fine, macro_categoria, id_categoria


def genera_periodi(data_inizio, data_fine, granularita_mesi=1):

    if not isinstance(granularita_mesi, int) or granularita_mesi <= 0:
        raise ValueError("La granularità deve essere un intero maggiore di 0.")

    periodi = []
    inizio_corrente = data_inizio

    while inizio_corrente <= data_fine:
        # Aggiungiamo N mesi e togliamo un giorno per trovare la fine del blocco
        fine_teorica = (
            inizio_corrente + relativedelta(months=granularita_mesi) - timedelta(days=1)
        )

        # Applichiamo i nostri due limiti di sicurezza
        fine_corrente = min(fine_teorica, data_fine)
        fine_anno = date(inizio_corrente.year, 12, 31)
        fine_corrente = min(fine_corrente, fine_anno)

        periodi.append((inizio_corrente, fine_corrente))

        # Il giorno successivo diventa l'inizio del nuovo blocco
        inizio_corrente = fine_corrente + timedelta(days=1)

    return periodi


def costruisci_percorso(macro_categoria, sotto_categoria, data_inizio, data_fine):
    anno_cartella = data_inizio.year

    # Trasformiamo le date in stringhe pulite (formato ISO: AAAA-MM-GG)
    str_inizio = data_inizio.strftime("%Y-%m-%d")
    str_fine = data_fine.strftime("%Y-%m-%d")

    nome_file = f"{str_inizio}_{str_fine}.json"

    # Costruisce il percorso finale
    percorso = (
        CARTELLA_DOCUMENTI
        / "dati"
        / macro_categoria
        / sotto_categoria
        / str(anno_cartella)
        / nome_file
    )

    return percorso


def chiamata_con_retry(
    url, headers=None, params=None, max_tentativi=1000, backoff_iniziale=2
):
    # Funzione che si occupa di fare una richiesta, se qualcosa va storto aspetta invece di far crashare tutto
    backoff = backoff_iniziale
    ultimo_motivo = "errore_sconosciuto"

    for tentativo in range(1, max_tentativi + 1):
        try:
            response = SESSIONE_HTTP.get(
                url, headers=headers, params=params, timeout=15
            )

            # 1. CASO SUCCESSO: Tutto ok, restituisco la risposta
            if response.status_code == 200:
                return response, None

            ultimo_motivo = f"http_{response.status_code}"

            # 2. CASO ERRORI TEMPORANEI: Il server è pigro o congestionato, ha senso riprovare
            if response.status_code in [429, 500, 502, 503, 504]:
                print(
                    f"    [AVVISO] HTTP {response.status_code} al tentativo {tentativo}. Pausa di {backoff}s..."
                )

            # 3. CASO ERRORI DEFINITIVI (403, 404, ecc.): Errore client o blocco. Fermiamo subito il ciclo!
            else:
                print(
                    f"    [ERRORE BLOCCANTE] HTTP {response.status_code} rilevato (Invalido o Negato). Inutile riprovare. Interrompo."
                )
                return None, ultimo_motivo

        except requests.exceptions.RequestException as errore:
            ultimo_motivo = "errore_rete"
            # Questo blocco ora scatterà SOLO per veri problemi di rete (timeout, DNS fallito, connessione persa)
            print(
                f"    [AVVISO] Errore di rete/Timeout al tentativo {tentativo}: {errore}. Pausa di {backoff}s..."
            )

        # Gestione del backoff esponenziale (eseguito solo per il Caso 2 o per eccezioni nel blocco except)
        if tentativo < max_tentativi:
            time.sleep(backoff)
            backoff *= 2

    return None, ultimo_motivo


def ottieni_totale_elementi(url_base, id_categoria, data_inizio, data_fine, headers):
    # Funzione sonda per prelevare il totale degli elementi
    params = {
        "dataPubblicazioneStart": data_inizio.strftime("%d/%m/%Y"),
        "dataPubblicazioneEnd": data_fine.strftime("%d/%m/%Y"),
        "page": 0,
        "size": 1,
        "codiceScheda": id_categoria,
    }
    risposta, motivo = chiamata_con_retry(url_base, headers=headers, params=params)
    # Validazione esplicita: controlla che l'oggetto non sia None (evita ambiguità su response.ok)
    if risposta is None:
        return None, motivo

    try:
        dati = risposta.json()
    except ValueError:
        return None, "json_non_valido"

    if not isinstance(dati, dict):
        return None, "struttura_non_valida"

    if "totalElements" not in dati:
        return None, "totalElements_mancante"

    try:
        totale = int(dati["totalElements"])
    except (TypeError, ValueError):
        return None, "totalElements_non_valido"

    if totale < 0:
        return None, "totalElements_negativo"

    return totale, None


def calcola_numero_pagine(totale_elementi, dimensione_pagina):
    if totale_elementi <= 0:
        return 0
    return (totale_elementi + dimensione_pagina - 1) // dimensione_pagina


def scarica_pagina(
    url_base, id_categoria, data_inizio, data_fine, pagina, dimensione_pagina, headers
):
    params = {
        "dataPubblicazioneStart": data_inizio.strftime("%d/%m/%Y"),
        "dataPubblicazioneEnd": data_fine.strftime("%d/%m/%Y"),
        "page": pagina,
        "size": dimensione_pagina,
        "codiceScheda": id_categoria,
    }

    risposta, motivo = chiamata_con_retry(
        url_base,
        headers=headers,
        params=params,
    )

    if risposta is None:
        return None, motivo

    try:
        dati = risposta.json()
    except ValueError:
        return None, "json_non_valido"

    if not isinstance(dati, dict):
        return None, "struttura_non_valida"

    return dati, None


def salva_file_json(dati, percorso_file):
    # Crea le cartelle necessarie e scrive i dati preservando i caratteri speciali
    percorso_file.parent.mkdir(parents=True, exist_ok=True)

    percorso_temporaneo = percorso_file.with_suffix(".json.tmp")

    with open(percorso_temporaneo, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=4)

    percorso_temporaneo.replace(percorso_file)


def file_lista_valido(percorso_file):
    try:
        with open(percorso_file, "r", encoding="utf-8") as file:
            dati = json.load(file)

        return isinstance(dati, list)

    except (OSError, json.JSONDecodeError):
        return False


def main():
    print("########## AVVIO SCRIPT ESTERNO ##########")

    # Argomenti da passare allo script
    parser = argparse.ArgumentParser(description="Script per il download esterno")
    parser.add_argument(
        "--data-inizio", type=str, required=True, help="Data inizio (gg/mm/aaaa)"
    )
    parser.add_argument(
        "--data-fine", type=str, required=True, help="Data fine (gg/mm/aaaa)"
    )
    parser.add_argument(
        "--categoria", type=str, required=True, help="Sotto-categoria da scaricare"
    )
    parser.add_argument(
        "--dimensione-pagina",
        type=int,
        default=5000,
        help="Numero di elementi da scaricare per pagina (default: 5000)",
    )
    parser.add_argument(
        "--granularita-mesi",
        type=int,
        default=1,
        help="Ampiezza di ogni blocco in mesi (default: 1)",
    )
    parser.add_argument(
        "--attesa-pagine",
        type=float,
        default=4.0,
        help="Secondi di attesa tra pagine dello stesso periodo (default: 4.0)",
    )
    parser.add_argument(
        "--attesa-periodi",
        type=float,
        default=7.0,
        help="Secondi di attesa tra un periodo e il successivo (default: 7.0)",
    )
    args = parser.parse_args()

    try:
        # Validiamo i parametri ed estraiamo le informazioni
        data_inizio, data_fine, macro_categoria, id_categoria = valida_parametri(
            args.data_inizio,
            args.data_fine,
            args.categoria,
            categorie,
            args.dimensione_pagina,
        )

        print(f"\n[INFO] Configurazione avviata correttamente:")
        print(
            f"  - Sotto-categoria richiesta: '{args.categoria}' (ID API: {id_categoria})"
        )
        print(
            f"  - Salvataggio in: {CARTELLA_DOCUMENTI / 'dati' / macro_categoria / args.categoria}"
        )
        print(f"  - Range temporale totale: {data_inizio} -> {data_fine}\n")

        periodi = genera_periodi(data_inizio, data_fine, args.granularita_mesi)

        # === CONTATORI PER IL RIEPILOGO FINALE ===
        statistiche = {
            "totale_periodi": len(periodi),
            "completati": 0,
            "saltati": 0,
            "falliti": 0,
            "elementi_raccolti": 0,
        }

        print(
            f"--- Pianificazione Download ({statistiche['totale_periodi']} file previsti) ---"
        )

        for p_inizio, p_fine in periodi:
            percorso_file = costruisci_percorso(
                macro_categoria, args.categoria, p_inizio, p_fine
            )

            # Avvolgiamo il singolo periodo in un try/except dedicato per isolare i fallimenti
            try:
                # 1. Controllo di esistenza
                if percorso_file.exists():
                    if file_lista_valido(percorso_file):
                        print(
                            f"[SKIP] Periodo "
                            f"{p_inizio.strftime('%d/%m/%Y')} -> "
                            f"{p_fine.strftime('%d/%m/%Y')} già scaricato."
                        )
                        statistiche["saltati"] += 1
                        continue

                print(
                    f"[AVVISO] Il file {percorso_file.name} esiste, "
                    f"ma non è un JSON lista valido. Verrà riscaricato."
                )

                print(
                    f"-> Analisi periodo: {p_inizio.strftime('%d/%m/%Y')} al {p_fine.strftime('%d/%m/%Y')}"
                )

                # 2. Chiamata sonda
                totale_elementi, motivo = ottieni_totale_elementi(
                    URL_API, id_categoria, p_inizio, p_fine, headers_default
                )

                if totale_elementi is None:
                    print(
                        f"    [ERRORE] Sonda fallita: {motivo}. " f"Salto il periodo."
                    )
                    statistiche["falliti"] += 1
                    continue

                print(f"    Elementi totali rilevati sul server: {totale_elementi}")

                # 3. Gestione periodo vuoto
                if totale_elementi == 0:
                    print(f"    Nessun elemento presente. Creo file vuoto di spunta.")
                    salva_file_json([], percorso_file)
                    statistiche["completati"] += 1
                    continue

                # 4. Calcolo delle pagine
                totale_pagine = calcola_numero_pagine(
                    totale_elementi, args.dimensione_pagina
                )
                bandi_del_periodo = []
                errore_periodo = False

                # 5. Ciclo di scaricamento pagine
                for pagina in range(0, totale_pagine):
                    print(f"    Scarico pagina {pagina + 1}/{totale_pagine}...")

                    dati_pagina, motivo = scarica_pagina(
                        URL_API,
                        id_categoria,
                        p_inizio,
                        p_fine,
                        pagina,
                        args.dimensione_pagina,
                        headers_default,
                    )

                    if dati_pagina is None:
                        print(
                            f"    [ERRORE GRAVE] Pagina {pagina + 1} "
                            f"non scaricata: {motivo}."
                        )
                        errore_periodo = True
                        break

                    # Verifica esplicita che la struttura attesa sia presente, invece di un fallback silenzioso
                    if (
                        not isinstance(dati_pagina, dict)
                        or "content" not in dati_pagina
                    ):
                        print(
                            f"    [ERRORE STRUTTURA] La risposta non contiene la chiave 'content' attesa. Interrompo questo periodo."
                        )
                        errore_periodo = True
                        break

                    lista_bandi = dati_pagina["content"]
                    if not isinstance(lista_bandi, list):
                        print(
                            "    [ERRORE STRUTTURA] La chiave 'content' "
                            "non contiene una lista."
                        )
                        errore_periodo = True
                        break

                    record_non_validi = [
                        avviso
                        for avviso in lista_bandi
                        if (not isinstance(avviso, dict) or not avviso.get("idAvviso"))
                    ]

                    if record_non_validi:
                        print(
                            f"    [ERRORE STRUTTURA] Trovati "
                            f"{len(record_non_validi)} record senza un idAvviso valido."
                        )
                        errore_periodo = True
                        break

                    if record_non_validi:
                        print(
                            f"    [ERRORE STRUTTURA] Trovati "
                            f"{len(record_non_validi)} record senza un idAvviso valido."
                        )
                    errore_periodo = True
                    break

                    bandi_del_periodo.extend(lista_bandi)

                    if pagina < (totale_pagine - 1):
                        time.sleep(args.attesa_pagine)

                    if len(bandi_del_periodo) != totale_elementi:
                        print(
                            f"    [ERRORE COMPLETEZZA] Il server dichiarava "
                            f"{totale_elementi} record, ma ne sono stati raccolti "
                            f"{len(bandi_del_periodo)}."
                        )
                    errore_periodo = True

                # 6. Salvataggio su disco
                if not errore_periodo:
                    id_raccolti = [avviso["idAvviso"] for avviso in bandi_del_periodo]
                    if len(id_raccolti) != len(set(id_raccolti)):
                        print(
                            "    [ERRORE DUPLICATI] Sono presenti ID duplicati "
                            "tra le pagine. Il periodo non verrà salvato."
                        )
                    errore_periodo = True
                if not errore_periodo:
                    salva_file_json(bandi_del_periodo, percorso_file)
                    print(
                        f"    [OK] Blocco salvato con successo: "
                        f"{percorso_file.name}"
                    )
                    statistiche["completati"] += 1
                    statistiche["elementi_raccolti"] += len(bandi_del_periodo)
                else:
                    statistiche["falliti"] += 1

                print(f"    Attesa di assestamento prima del prossimo periodo...\n")
                time.sleep(args.attesa_periodi + random.uniform(0, 1.5))

            except Exception as errore_imprevisto:
                # Lo scudo definitivo: cattura bug del codice, dischi pieni, JSON corrotti
                print(
                    f"    [CRASH EVITATO] Errore imprevisto nel periodo {p_inizio.strftime('%d/%m/%Y')}: {errore_imprevisto}"
                )
                print(f"    Procedo comunque con il prossimo blocco temporale...\n")
                statistiche["falliti"] += 1
                continue

        # === FASE E: RIEPILOGO FINALE ===
        print("=" * 50)
        print("           ELABORAZIONE COMPLETATA")
        print("=" * 50)
        print(f" Periodi totali pianificati: {statistiche['totale_periodi']}")
        print(f"   - Completati con successo: {statistiche['completati']}")
        print(f"   - Saltati (già su disco):  {statistiche['saltati']}")
        print(f"   - Falliti / Interrotti:    {statistiche['falliti']}")
        print(f" Totale record ANAC raccolti: {statistiche['elementi_raccolti']}")
        print("=" * 50)

    except ValueError as errore:
        print(f"Errore nei parametri iniziali: {errore}")


# Controllo per far capire a python se questo file deve essere esguito immediatamente o deve importarsi in un altro script.
if __name__ == "__main__":
    main()
