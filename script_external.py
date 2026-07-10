from datetime import datetime

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_DESC = "gg/mm/aaaa"


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