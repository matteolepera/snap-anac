print("########## AVVIO SCRIPT ##########")
import argparse
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_DESC = "gg/mm/aaaa"

# Funzione con_ sarebbe funzione privata
def _analizza_data(data_str, nome_campo):
    try:
        return datetime.strptime(data_str, FORMATO_DATA).date()
    except ValueError:
        raise ValueError(
            f"La data di {nome_campo} deve essere nel formato {FORMATO_DATA_DESC}."
        )


def valida_parametri(data_inizio_str, data_fine_str, categoria_utente, struttura_categorie):
    # Funzione che valida i parametri ricevuti da argparse.   
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


def genera_periodi(data_inizio, data_fine, granularita_mesi=1):
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


def costruisci_percorso(macro_categoria, data_inizio, data_fine):
    anno_cartella = data_inizio.year

    # Trasformiamo le date in stringhe pulite (formato ISO: AAAA-MM-GG)
    str_inizio = data_inizio.strftime("%Y-%m-%d")
    str_fine = data_fine.strftime("%Y-%m-%d")
    
    nome_file = f"{str_inizio}_{str_fine}.json"

    # Costruisce il percorso finale
    percorso = Path("dati") / macro_categoria / str(anno_cartella) / nome_file

    return percorso




def main():
    # Dizionario con le chiavi di ogni categoria da scaricare
    categorie = {
    "bandi": {
        "bandi": "4",
        "avvisi_di_indizione": "2"
    },
    "esiti": {
        "risultati": "7",
        "affidamenti_diretti_sotto soglia": "8a",
        "preavvisi_di_aggiudicazione_diretta": "9"
    }
  }

    # Argomenti da passare allo script
    parser = argparse.ArgumentParser(description="Script per il download")
    parser.add_argument("--data-inizio", type=str, required=True, help="Data inizio (gg/mm/aaaa)")
    parser.add_argument("--data-fine", type=str, required=True, help="Data fine (gg/mm/aaaa)")
    parser.add_argument("--categoria", type=str, required=True, help="Sotto-categoria da scaricare")
    parser.add_argument("--granularita-mesi", type=int, default=1, help="Ampiezza di ogni blocco in mesi")
    args = parser.parse_args()

    try:
        # Validiamo i parametri ed estraiamo le informazioni sulla categoria nidificata
        data_inizio, data_fine, macro_categoria, id_categoria = valida_parametri(
            args.data_inizio, args.data_fine, args.categoria, categorie
        )
        
        print(f"\n[INFO] Configurazione avviata correttamente:")
        print(f"  - Sotto-categoria richiesta: '{args.categoria}' (ID API: {id_categoria})")
        print(f"  - Salvataggio nella macro-cartella: dati/{macro_categoria}/")
        print(f"  - Range temporale totale: {data_inizio} -> {data_fine}\n")
        
        # Generiamo la lista dei blocchi temporali da scaricare
        periodi = genera_periodi(data_inizio, data_fine, args.granularita_mesi)
        
        print(f"--- Pianificazione Download ({len(periodi)} file previsti) ---")
        for p_inizio, p_fine in periodi:
            percorso_file = costruisci_percorso(macro_categoria, p_inizio, p_fine)
            
            # Qui si inserirà la logica della chiamata API usando id_categoria, p_inizio e p_fine
            print(f"-> Download periodo: {p_inizio} al {p_fine}")
            print(f"   Destinazione file: {percorso_file}\n")
            
    except ValueError as errore:
        print(f"Errore nei parametri: {errore}")


# Controllo per far capire a python se questo file deve essere esguito immediatamente o deve importarsi in un altro script.
if __name__ == "__main__":
    main()