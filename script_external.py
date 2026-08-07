from datetime import datetime, date, timedelta
from pathlib import Path
import json
import time
import random
import csv

from terminal_ui import TerminalArgumentParser, console

try:
    import requests
    from dateutil.relativedelta import relativedelta
except ModuleNotFoundError as errore_dipendenza:
    nome_pacchetto = {
        "dateutil": "python-dateutil",
        "requests": "requests",
    }.get(errore_dipendenza.name, errore_dipendenza.name)
    console.fatal(
        f"Dipendenza mancante: {nome_pacchetto} · "
        f"installa con 'pip install {nome_pacchetto}'"
    )
    raise SystemExit(1) from None


FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_DESC = "gg/mm/aaaa"

CARTELLA_DOCUMENTI = Path.home() / "Documents"

# Headers mi serve per fingermi affidabile, in questo caso googlebot
headers_default = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://pubblicitalegale.anticorruzione.it/",
    "Origin": "https://pubblicitalegale.anticorruzione.it"
}

# Dizionario con le chiavi di ogni categoria da scaricare
categorie = {
    "bandi_category": {
        "bandi": "4",
        "avvisi_di_indizione": "2"
    },
    "esiti_category": {
        "risultati": "7",
        "affidamenti_diretti_sotto_soglia": "8a",
        "preavvisi_di_aggiudicazione_diretta": "9"
    },
    "altri_avvisi":{
        "avvisi_di_pre_informazione_informativi": "1",
        "sistemi_di_qualificazione": "3",
        "indagini_di_mercato_pari_o_sopra_soglia": "5a",
        "indagini_di_mercato_sotto_soglia": "5b",
        "elenchi_operatori_economici": "6",
        "affidamenti_in_house": "8b",
        "modifiche_contrattuali": "10"

    }
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

def valida_parametri(data_inizio_str, data_fine_str, categoria_utente, struttura_categorie, dimensione_pagina):
    # Funzione che valida i parametri ricevuti da argparse.
    # Controllo valore e tetto massimo della dimensione pagina
    if not isinstance(dimensione_pagina, int) or dimensione_pagina <= 0:
        raise ValueError("La dimensione della pagina deve essere un numero intero positivo maggiore di 0.")
    
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
        raise ValueError("La data di inizio non può essere successiva alla data di fine.")

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

def valida_opzioni_download(granularita_mesi, attesa_pagine, attesa_periodi):
    if not isinstance(granularita_mesi, int) or granularita_mesi <= 0:
        raise ValueError("La granularità deve essere un numero intero maggiore di 0.")
    
    if attesa_pagine < 0:
         raise ValueError("L'attesa tra le pagine non può essere negativa.")
    
    if attesa_periodi < 0:
         raise ValueError("L'attesa tra i periodi non può essere negativa.")

def genera_periodi(data_inizio, data_fine, granularita_mesi=1):

    if not isinstance(granularita_mesi, int) or granularita_mesi <= 0:
        raise ValueError("La granularità deve essere un numero intero maggiore di 0.")

    periodi = []
    inizio_corrente = data_inizio

    while inizio_corrente <= data_fine:
        # Aggiungiamo N mesi e togliamo un giorno per trovare la fine del blocco
        fine_teorica = inizio_corrente + relativedelta(months=granularita_mesi) - timedelta(days=1)
        
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
    percorso = CARTELLA_DOCUMENTI / "dati" / macro_categoria / sotto_categoria / str(anno_cartella) / nome_file

    return percorso

def calcola_attesa_retry(response, backoff, backoff_massimo):
    retry_after = response.headers.get("Retry-After")

    if retry_after is None:
        return backoff
    
    try:
        secondi_retry_after = float(retry_after)
    except (TypeError, ValueError):
        return backoff
    
    if secondi_retry_after < 0:
        return backoff
    
    return min(max(backoff, secondi_retry_after), backoff_massimo)

def chiamata_con_retry(url, headers=None, params=None, max_tentativi=1000, backoff_iniziale=2,  backoff_massimo=600):
    # Funzione che si occupa di fare una richiesta, se qualcosa va storto aspetta invece di far crashare tutto
    if not isinstance(max_tentativi, int) or isinstance(max_tentativi, bool):
        raise TypeError("max_tentativi deve essere un numero intero.")
    
    if max_tentativi <= 0:
        raise ValueError("max_tentativi deve essere maggiore di 0.")

    if (not isinstance(backoff_iniziale, (int, float)) or isinstance(backoff_iniziale, bool)):
        raise TypeError("backoff_iniziale deve essere un numero.")

    if (not isinstance(backoff_massimo, (int, float)) or isinstance(backoff_massimo, bool)):
        raise TypeError("backoff_massimo deve essere un numero.")

    if backoff_iniziale < 0:
        raise ValueError("backoff_iniziale non può essere negativo.")

    if backoff_massimo < backoff_iniziale:
        raise ValueError("backoff_massimo non può essere inferiore a backoff_iniziale.")
    
    backoff = backoff_iniziale
    ultimo_motivo = "errore_sconosciuto"
    
    for tentativo in range(1, max_tentativi + 1):
        attesa_retry = backoff
        try:
            response = SESSIONE_HTTP.get(url, headers=headers, params=params, timeout=15)
            
            # 1. CASO SUCCESSO: Tutto ok, restituisco la risposta
            if response.status_code == 200:
                return response, None

            ultimo_motivo = f"http_{response.status_code}"    
            
            # 2. CASO ERRORI TEMPORANEI: Il server è pigro o congestionato, ha senso riprovare
            if response.status_code in [429, 500, 502, 503, 504]:
                attesa_retry = calcola_attesa_retry(
                    response,
                    backoff,
                    backoff_massimo
                )

                console.retry(
                    f"HTTP {response.status_code} al tentativo {tentativo} · "
                    f"nuovo tentativo tra {attesa_retry:.1f}s",
                    indentazione=1,
                )
            
            # 3. CASO ERRORI DEFINITIVI (403, 404, ecc.): Errore client o blocco. Fermiamo subito il ciclo!
            else:
                console.error(
                    f"HTTP {response.status_code} · richiesta non valida o non autorizzata; "
                    "nessun nuovo tentativo",
                    indentazione=1,
                )
                return None, ultimo_motivo
                
        except requests.exceptions.RequestException as errore:
            ultimo_motivo = "errore_rete"
            # Questo blocco ora scatterà SOLO per veri problemi di rete (timeout, DNS fallito, connessione persa)
            console.retry(
                f"Errore di rete al tentativo {tentativo}: {errore} · "
                f"nuovo tentativo tra {backoff:.1f}s",
                indentazione=1,
            )

        # Gestione del backoff esponenziale (eseguito solo per il Caso 2 o per eccezioni nel blocco except)
        if tentativo < max_tentativi:
            time.sleep(attesa_retry)
            backoff = min(backoff * 2, backoff_massimo)
            
    return None, ultimo_motivo

def ottieni_totale_elementi(url_base, id_categoria, data_inizio, data_fine, headers):
    # Funzione sonda per prelevare il totale degli elementi
    params = {
        "dataPubblicazioneStart": data_inizio.strftime("%d/%m/%Y"),
        "dataPubblicazioneEnd": data_fine.strftime("%d/%m/%Y"),
        "page": 0,
        "size": 1,
        "codiceScheda": id_categoria
    }
    risposta, motivo = chiamata_con_retry(url_base, headers=headers, params=params)

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

def scarica_pagina(url_base, id_categoria, data_inizio, data_fine, pagina, dimensione_pagina, headers):
    params = {
        "dataPubblicazioneStart": data_inizio.strftime("%d/%m/%Y"),
        "dataPubblicazioneEnd": data_fine.strftime("%d/%m/%Y"),
        "page": pagina,
        "size": dimensione_pagina,
        "codiceScheda": id_categoria
    }
    risposta, motivo = chiamata_con_retry(url_base, headers=headers, params=params)
    # Ritorna il dizionario JSON solo se l'oggetto risposta esiste esplicitamente
    if risposta is None:
        return None, motivo
    
    try:
        dati = risposta.json()
    except ValueError:
        return None, "json_non_valido"
    
    if not isinstance(dati, dict):
        return None, "struttura_non_valida"
    
    return dati, None

def record_ha_id_valido(record):
    if not isinstance(record, dict):
        return False
    
    id_avviso = record.get("idAvviso")

    return(isinstance(id_avviso, str) and bool(id_avviso.strip()))

def estrai_record_pagina(dati_pagina):
    if not isinstance(dati_pagina, dict):
        return None, "struttura_pagina_non_valida"
    
    if "content" not in dati_pagina:
        return None, "content_mancante"
    
    lista_record = dati_pagina["content"]

    if not isinstance(lista_record, list):
        return None, "content_non_lista"
    
    if any(not record_ha_id_valido(record)
    for record in lista_record
    ):
    
        return None, "record_non_validi"
    
    return lista_record, None

def valida_periodo_raccolto(record_raccolti, totale_atteso):
    if len(record_raccolti) != totale_atteso:
        return False, "numero_record_incompleto"
    
    id_raccolti = [
        record["idAvviso"]
        for record in record_raccolti
    ]

    if len(id_raccolti) != len(set(id_raccolti)):
        return False, "id_duplicati"
    
    return True, None

def salva_file_json(dati, percorso_file):
    # Crea le cartelle necessarie e scrive i dati preservando i caratteri speciali
    percorso_file.parent.mkdir(parents=True, exist_ok=True)
    
    percorso_temporaneo = percorso_file.with_suffix(".json.tmp")
    
    with open(percorso_temporaneo, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=4)
    
    percorso_temporaneo.replace(percorso_file)

def controlla_file_lista(percorso_file):
    if not percorso_file.exists():
        return False, "file_mancante"

    if not percorso_file.is_file():
        return False, "percorso_non_valido"
    
    try:
        dimensione_file = percorso_file.stat().st_size

        if dimensione_file < 2:
            return False, "file_vuoto_o_incompleto"

        with open(percorso_file, "rb") as file:
            primo_byte = file.read(1)

            file.seek(-1, 2)
            ultimo_byte = file.read(1)
    
    except OSError:
        return False, "errore_lettura_file"

    if primo_byte != b"[":
        return False, "struttura_iniziale_non_valida"

    if ultimo_byte != b"]":
        return False, "file_incompleto"

    return True, None

def prepara_periodi_da_scaricare(periodi, macro_categoria, sotto_categoria):

    periodi_da_scaricare = []
    percorsi_gia_visti = set()

    gia_presenti = 0
    file_non_validi = 0

    for data_inizio, data_fine in periodi:
        percorso_file = costruisci_percorso(macro_categoria, sotto_categoria, data_inizio, data_fine)

         # Protezione contro eventuali periodi duplicati
        if percorso_file in percorsi_gia_visti:
             console.skip(f"Periodo duplicato: {percorso_file.name}")
             continue
        
        percorsi_gia_visti.add(percorso_file)

        file_valido, motivo = controlla_file_lista(percorso_file)

        if file_valido:
            gia_presenti += 1
            continue

        if motivo != "file_mancante":
            file_non_validi += 1
            console.warning(
                f"File non valido: {percorso_file.name} · {motivo}; verrà riscaricato"
            )

        periodi_da_scaricare.append((data_inizio, data_fine, percorso_file))

    return (periodi_da_scaricare, gia_presenti, file_non_validi)

def registra_periodo_fallito(data_inizio, data_fine, macro_categoria, sotto_categoria, motivo, pagina=None):
    percorso_log = (
        CARTELLA_DOCUMENTI
        / "dati"
        / macro_categoria
        / sotto_categoria
        / "periodi_falliti.csv")
    try:
        percorso_log.parent.mkdir(parents=True, exist_ok=True)

        scrivi_intestazione = ( not percorso_log.exists() or percorso_log.stat().st_size == 0)
        with open(percorso_log, "a", encoding="utf-8", newline="") as file_log:
            scrittore = csv.writer(file_log, delimiter=";")
            if scrivi_intestazione:
                scrittore.writerow(
                    [
                        "data_inizio",
                        "data_fine",
                        "pagina",
                        "motivo",
                        "data_tentativo"
                    ]
                )

            scrittore.writerow(
                    [
                        data_inizio.strftime("%Y-%m-%d"),
                        data_fine.strftime("%Y-%m-%d"),
                        pagina if pagina is not None else "",
                        motivo,
                        datetime.now()
                        .astimezone()
                        .isoformat(timespec="seconds"),
                    ]
                )
            
            return True
    except OSError as errore_log:
        console.warning(
            f"Impossibile aggiornare il registro dei fallimenti: {errore_log}",
            indentazione=1,
        )
        return False

def attendi_prima_del_prossimo_periodo(attesa_periodi):

    attesa_effettiva = attesa_periodi + random.uniform(0, 1.5)

    console.wait(
        f"Prossimo periodo tra {attesa_effettiva:.1f}s",
        indentazione=1,
    )

    time.sleep(attesa_effettiva)

def main():
    console.banner("ANAC · INDICI", "Acquisizione massiva degli indici di gara")

    # Argomenti da passare allo script
    parser = TerminalArgumentParser(description="Script per il download esterno")
    parser.add_argument("--data-inizio", type=str, required=True, help="Data inizio (gg/mm/aaaa)")
    parser.add_argument("--data-fine", type=str, required=True, help="Data fine (gg/mm/aaaa)")
    parser.add_argument("--categoria", type=str, required=True, help="Sotto-categoria da scaricare")
    parser.add_argument("--dimensione-pagina", type=int, default=5000, help="Numero di elementi da scaricare per pagina (default: 5000)")
    parser.add_argument("--granularita-mesi", type=int, default=1, help="Ampiezza di ogni blocco in mesi (default: 1)")
    parser.add_argument("--attesa-pagine", type=float, default=4.0, help="Secondi di attesa tra pagine dello stesso periodo (default: 4.0)")
    parser.add_argument("--attesa-periodi", type=float, default=7.0, help="Secondi di attesa tra un periodo e il successivo (default: 7.0)")
    args = parser.parse_args()

    try:
        # Validiamo i parametri ed estraiamo le informazioni
        data_inizio, data_fine, macro_categoria, id_categoria = valida_parametri(
            args.data_inizio, args.data_fine, args.categoria, categorie, args.dimensione_pagina
        )

        valida_opzioni_download(args.granularita_mesi, args.attesa_pagine, args.attesa_periodi)
        
        console.section("Configurazione")
        console.metrics(
            [
                ("Categoria", f"{args.categoria}  ·  API {id_categoria}"),
                (
                    "Destinazione",
                    CARTELLA_DOCUMENTI / "dati" / macro_categoria / args.categoria,
                ),
                ("Intervallo", f"{data_inizio:%d/%m/%Y}  →  {data_fine:%d/%m/%Y}"),
            ]
        )
        
        periodi = genera_periodi(data_inizio, data_fine, args.granularita_mesi)
        
        (periodi_da_scaricare, gia_presenti, file_non_validi) = prepara_periodi_da_scaricare(periodi, macro_categoria, args.categoria)
        
        
        # === CONTATORI PER IL RIEPILOGO FINALE ===
        statistiche = {
            "totale_periodi": len(periodi),
            "gia_presenti": gia_presenti,
            "file_non_validi": file_non_validi,
            "da_scaricare": len(periodi_da_scaricare),
            "completati": 0,
            "falliti": 0,
            "elementi_raccolti": 0
        }
        
        console.section("Controllo preventivo", "completato")
        console.metrics(
            [
                ("Periodi complessivi", statistiche["totale_periodi"]),
                ("File validi già presenti", statistiche["gia_presenti"]),
                ("File esistenti non validi", statistiche["file_non_validi"]),
                ("Periodi da scaricare", statistiche["da_scaricare"]),
            ]
        )

        console.section(
            "Download indici",
            f"{statistiche['da_scaricare']} periodi in coda",
        )
        
        for indice_periodo, (p_inizio, p_fine, percorso_file) in enumerate(periodi_da_scaricare, start=1):
            # Avvolgiamo il singolo periodo in un try/except dedicato per isolare i fallimenti
            try:
                console.step(
                    indice_periodo,
                    statistiche["da_scaricare"],
                    f"{p_inizio:%d/%m/%Y}  →  {p_fine:%d/%m/%Y}",
                    percorso_file.name,
                )
                
                # 2. Chiamata sonda
                console.working("Conteggio degli elementi sul server", indentazione=1)
                totale_elementi, motivo = ottieni_totale_elementi(URL_API, id_categoria, p_inizio, p_fine, headers_default)
                
                if totale_elementi is None:
                    console.error(
                        f"Conteggio non riuscito · {motivo}; periodo saltato",
                        indentazione=1,
                    )

                    registra_periodo_fallito(
                        p_inizio,
                        p_fine,
                        macro_categoria,
                        args.categoria,
                        motivo
                    )

                    statistiche["falliti"] += 1
                    attendi_prima_del_prossimo_periodo(args.attesa_periodi)
                    continue
                    
                console.info(
                    f"Elementi rilevati sul server: {totale_elementi}",
                    indentazione=1,
                )
                
                # 3. Gestione periodo vuoto
                if totale_elementi == 0:
                    salva_file_json([], percorso_file)

                    console.success(
                        f"Periodo vuoto · creato {percorso_file.name}",
                        indentazione=1,
                    )

                    statistiche["completati"] += 1
                    attendi_prima_del_prossimo_periodo(args.attesa_periodi)
                    continue

                # 4. Calcolo delle pagine
                totale_pagine = calcola_numero_pagine(totale_elementi, args.dimensione_pagina)
                bandi_del_periodo = []
                errore_periodo = False

                # 5. Ciclo di scaricamento pagine
                for pagina in range(totale_pagine):
                    numero_pagina = pagina + 1

                    console.working(
                        f"Download pagina {numero_pagina}/{totale_pagine}",
                        indentazione=1,
                    )

                    inizio_pagina = time.perf_counter()

                    dati_pagina, motivo = scarica_pagina(URL_API, id_categoria, p_inizio, p_fine, pagina, args.dimensione_pagina, headers_default)
                    
                    if dati_pagina is None:
                        durata_pagina = (time.perf_counter() - inizio_pagina)
                        console.error(
                            f"Pagina {numero_pagina}/{totale_pagine} non scaricata "
                            f"in {durata_pagina:.2f}s · {motivo}",
                            indentazione=1,
                        )
                        
                        registra_periodo_fallito(
                            p_inizio,
                            p_fine,
                            macro_categoria,
                            args.categoria,
                            motivo,
                            pagina=numero_pagina,
                        )
                        
                        errore_periodo = True
                        break
                    
                    lista_bandi, motivo = estrai_record_pagina(dati_pagina)

                    if lista_bandi is None:
                        durata_pagina = (time.perf_counter() - inizio_pagina)

                        console.error(
                            f"Pagina {numero_pagina}/{totale_pagine} non valida "
                            f"dopo {durata_pagina:.2f}s · {motivo}",
                            indentazione=1,
                        )
                        
                        registra_periodo_fallito(
                            p_inizio,
                            p_fine,
                            macro_categoria,
                            args.categoria,
                            motivo,
                            pagina=numero_pagina,
                        )
                        
                        errore_periodo = True
                        break

                    bandi_del_periodo.extend(lista_bandi)

                    durata_pagina = (time.perf_counter() - inizio_pagina)

                    console.progress(
                        len(bandi_del_periodo),
                        totale_elementi,
                        f"Pagina {numero_pagina}/{totale_pagine} completata",
                        f"+{len(lista_bandi)} record · {durata_pagina:.2f}s",
                    )
                    
                    if pagina < (totale_pagine - 1):
                        time.sleep(args.attesa_pagine)

                if not errore_periodo:
                    periodo_valido , motivo = valida_periodo_raccolto(bandi_del_periodo, totale_elementi)

                    if not periodo_valido:
                        console.error(
                            f"Validazione fallita · {motivo}; periodo non salvato",
                            indentazione=1,
                        )
                        
                        registra_periodo_fallito(
                            p_inizio,
                            p_fine,
                            macro_categoria,
                            args.categoria,
                            motivo
                        )

                        errore_periodo = True

                # 6. Salvataggio su disco
                if not errore_periodo:
                    salva_file_json(bandi_del_periodo, percorso_file)
                    console.success(
                        f"{len(bandi_del_periodo)} record salvati · {percorso_file.name}",
                        indentazione=1,
                    )
                    statistiche["completati"] += 1
                    statistiche["elementi_raccolti"] += len(bandi_del_periodo)
                else:
                    console.error("Periodo fallito · nessun file salvato", indentazione=1)
                    statistiche["falliti"] += 1
                
                attendi_prima_del_prossimo_periodo(args.attesa_periodi)
            
            except OSError as errore_disco:
                console.fatal(
                    f"Impossibile salvare il periodo {p_inizio:%d/%m/%Y} → "
                    f"{p_fine:%d/%m/%Y}: {errore_disco}",
                    indentazione=1,
                )
                console.info(
                    "Esecuzione interrotta per proteggere l'integrità dei dati",
                    indentazione=1,
                )
                return
            
            except Exception as errore_imprevisto:
                # Lo scudo definitivo: cattura bug del codice, dischi pieni, JSON corrotti
                console.error(
                    f"Errore imprevisto nel periodo {p_inizio:%d/%m/%Y}: "
                    f"{errore_imprevisto}",
                    indentazione=1,
                )
                console.info("Il prossimo periodo verrà elaborato", indentazione=1)

                registra_periodo_fallito(
                            p_inizio,
                            p_fine,
                            macro_categoria,
                            args.categoria,
                            "crash_imprevisto"
                        )
                
                statistiche["falliti"] += 1
                attendi_prima_del_prossimo_periodo(args.attesa_periodi)
                continue

        # === FASE E: RIEPILOGO FINALE ===
        esito = "warning" if statistiche["falliti"] else "success"
        titolo = (
            "Elaborazione completata con errori"
            if statistiche["falliti"]
            else "Elaborazione completata"
        )
        console.summary(
            titolo,
            [
                ("Periodi pianificati", statistiche["totale_periodi"]),
                ("Già presenti e validi", statistiche["gia_presenti"]),
                ("File non validi rilevati", statistiche["file_non_validi"]),
                ("Scaricati con successo", statistiche["completati"]),
                ("Falliti o interrotti", statistiche["falliti"]),
                ("Record raccolti", statistiche["elementi_raccolti"]),
            ],
            stato=esito,
        )
            
    except ValueError as errore:
        console.error(f"Parametri iniziali non validi · {errore}")

# Controllo per far capire a python se questo file deve essere esguito immediatamente o deve importarsi in un altro script.
if __name__ == "__main__":
    main()
