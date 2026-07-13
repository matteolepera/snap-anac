print("########## AVVIO SCRIPT ##########")
import argparse
from datetime import datetime

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

def mese_successivo(anno, mese):
    if mese == 12:
        # caso limite: dicembre -> gennaio dell'anno dopo
        nuovo_anno = anno + 1
        nuovo_mese = 1
    else:
        # caso normale: incremento semplice
        nuovo_anno = anno
        nuovo_mese = mese + 1
    
    return nuovo_anno, nuovo_mese

def genera_mesi(data_inizio_str, data_fine_str):
    data_inizio = datetime.strptime(data_inizio_str, FORMATO_DATA)
    data_fine = datetime.strptime(data_fine_str, FORMATO_DATA)

    anno_corrente = data_inizio.year
    mese_corrente = data_inizio.month

    mesi = []
    
    while (anno_corrente, mese_corrente) <= (data_fine.year, data_fine.month):
        mesi.append((anno_corrente, mese_corrente))
        anno_corrente, mese_corrente = mese_successivo(anno_corrente, mese_corrente)
    
    return mesi

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