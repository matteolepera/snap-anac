print("########## AVVIO SCRIPT ##########")
import argparse
from datetime import date, timedelta
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


def valida_parametri(data_inizio_str, data_fine_str, categoria, categorie):
    # Funzione che valida i parametri ricevuti da argparse.

    # Controllo le date
    data_inizio = _analizza_data(data_inizio_str, "inizio")
    data_fine = _analizza_data(data_fine_str, "fine")

    # Controllo ordine cronoligco
    if data_inizio > data_fine:
        raise ValueError("La data di inizio non può essere successiva alla data di fine.")

    # Controllo che la data finale non sia nel futuro
    oggi = datetime.today().date()

    if data_fine > oggi:
        raise ValueError(
            "La data di fine non può essere successiva alla data odierna."
        )


    # Controllo categoria
    if categoria not in categorie:
        raise ValueError(
            f"Categoria '{categoria}' non valida."
            f"Categorie disponibili: {', '.join(categorie.keys())}"
        )

    return data_inizio, data_fine

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


def costruisci_percorso(categoria, anno, mese):
    # Formatta il mese inserendo uno zero iniziale se ha una sola cifra (es. 1 -> '01')
    mese_formattato = f"{mese:02d}"

    # Crea il nome del file (es. "2025-01.json")
    nome_file = f"{anno}-{mese_formattato}.json"

    # Costruisce il percorso combinando le cartelle usando l'operatore / di pathlib
    percorso = Path("dati") / categoria / str(anno) / nome_file

    return percorso




def main():

    # Dizionario con le chiavi di ogni categoria da scaricare
    categorie = {
    "bandi": "4",
    "avvisi": "2",
    }

    # Argomenti da passare allo script
    parser = argparse.ArgumentParser(description="test srt")
    parser.add_argument("--data-inizio", type=str, required=True)
    parser.add_argument("--data-fine", type=str, required=True)
    parser.add_argument("--categoria", type=str, required=True)
    args = parser.parse_args()

    try:
        data_inizio, data_fine = valida_parametri(
            args.data_inizio, args.data_fine, args.categoria, categorie
        )
        print(f"Parametri validi: {data_inizio} → {data_fine}, categoria={args.categoria}")
    except ValueError as errore:
        print(f"Errore nei parametri: {errore}")

# Controllo per far capire a python se questo file deve essere esguito immediatamente o deve importarsi in un altro script.
if __name__ == "__main__":
    main()