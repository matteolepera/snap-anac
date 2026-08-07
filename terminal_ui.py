"""Componenti visuali condivisi per l'output dei comandi ANAC.

Lo stile usa solo ANSI e caratteri Unicode, quindi non aggiunge dipendenze al
progetto. I colori vengono disabilitati automaticamente quando l'output non è
un terminale oppure quando è presente la variabile d'ambiente ``NO_COLOR``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Iterable, Mapping
from typing import TextIO


class TerminalUI:
    """Piccolo renderer per messaggi terminale coerenti e accessibili."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    VIOLET = "\033[38;5;141m"
    CYAN = "\033[38;5;117m"
    GREEN = "\033[38;5;114m"
    YELLOW = "\033[38;5;215m"
    RED = "\033[38;5;203m"
    MUTED = "\033[38;5;245m"
    WHITE = "\033[38;5;255m"

    _LIVELLI = {
        "info": ("●", "INFO", CYAN),
        "success": ("✓", "OK", GREEN),
        "warning": ("▲", "ATTENZIONE", YELLOW),
        "error": ("✕", "ERRORE", RED),
        "fatal": ("■", "FATALE", RED),
        "working": ("◇", "IN CORSO", VIOLET),
        "retry": ("↻", "NUOVO TENTATIVO", YELLOW),
        "wait": ("◷", "ATTESA", MUTED),
        "skip": ("○", "SALTATO", MUTED),
    }

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout
        self.colori_attivi = self._supporta_colori()

    def _supporta_colori(self) -> bool:
        if os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("FORCE_COLOR") not in (None, "", "0"):
            return True
        return bool(
            hasattr(self.stream, "isatty")
            and self.stream.isatty()
            and os.environ.get("TERM") != "dumb"
        )

    def _stile(self, testo: object, *codici: str) -> str:
        valore = str(testo)
        if not self.colori_attivi or not codici:
            return valore
        return f"{''.join(codici)}{valore}{self.RESET}"

    def _scrivi(self, testo: str = "") -> None:
        print(testo, file=self.stream, flush=True)

    @property
    def larghezza(self) -> int:
        colonne = shutil.get_terminal_size(fallback=(88, 24)).columns
        return max(56, min(colonne, 96))

    def banner(self, titolo: str, sottotitolo: str) -> None:
        """Mostra l'identità del comando senza occupare troppo spazio."""
        linea = "─" * max(8, self.larghezza - len(titolo) - 12)
        self._scrivi()
        self._scrivi(
            self._stile("╭─", self.VIOLET)
            + " "
            + self._stile("◆", self.CYAN, self.BOLD)
            + " "
            + self._stile(titolo.upper(), self.WHITE, self.BOLD)
            + " "
            + self._stile(linea, self.VIOLET)
        )
        self._scrivi(
            self._stile("╰─", self.VIOLET)
            + " "
            + self._stile(sottotitolo, self.MUTED)
        )

    def section(self, titolo: str, dettaglio: str | None = None) -> None:
        suffisso = ""
        if dettaglio:
            suffisso = "  " + self._stile(dettaglio, self.MUTED)
        self._scrivi()
        self._scrivi(
            self._stile("┌─", self.VIOLET)
            + " "
            + self._stile(titolo.upper(), self.WHITE, self.BOLD)
            + suffisso
        )

    def event(self, livello: str, messaggio: str, indentazione: int = 0) -> None:
        simbolo, etichetta, colore = self._LIVELLI[livello]
        rientro = "  " * max(0, indentazione)
        badge = f"{simbolo} {etichetta:<15}"
        self._scrivi(
            rientro
            + self._stile(badge, colore, self.BOLD)
            + " "
            + self._stile(messaggio, self.WHITE)
        )

    def info(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("info", messaggio, indentazione)

    def success(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("success", messaggio, indentazione)

    def warning(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("warning", messaggio, indentazione)

    def error(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("error", messaggio, indentazione)

    def fatal(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("fatal", messaggio, indentazione)

    def working(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("working", messaggio, indentazione)

    def retry(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("retry", messaggio, indentazione)

    def wait(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("wait", messaggio, indentazione)

    def skip(self, messaggio: str, indentazione: int = 0) -> None:
        self.event("skip", messaggio, indentazione)

    def metric(self, etichetta: str, valore: object, indentazione: int = 0) -> None:
        rientro = "  " * max(0, indentazione)
        self._scrivi(
            rientro
            + self._stile("│", self.VIOLET)
            + " "
            + self._stile(f"{etichetta:<32}", self.MUTED)
            + self._stile(valore, self.WHITE, self.BOLD)
        )

    def metrics(
        self,
        valori: Mapping[str, object] | Iterable[tuple[str, object]],
        indentazione: int = 0,
    ) -> None:
        elementi = valori.items() if isinstance(valori, Mapping) else valori
        for etichetta, valore in elementi:
            self.metric(etichetta, valore, indentazione)

    def step(
        self,
        corrente: int,
        totale: int,
        titolo: str,
        dettaglio: str | None = None,
    ) -> None:
        indice = f"{corrente:>{len(str(max(totale, 1)))}}/{totale}"
        suffisso = ""
        if dettaglio:
            suffisso = "  " + self._stile(dettaglio, self.MUTED)
        self._scrivi()
        self._scrivi(
            self._stile("├─", self.VIOLET)
            + " "
            + self._stile(f"[{indice}]", self.CYAN, self.BOLD)
            + " "
            + self._stile(titolo, self.WHITE, self.BOLD)
            + suffisso
        )

    def progress(
        self,
        corrente: int,
        totale: int,
        etichetta: str,
        dettaglio: str | None = None,
    ) -> None:
        percentuale = 100.0 if totale == 0 else min(100.0, corrente / totale * 100)
        segmenti = 12
        pieni = round(segmenti * percentuale / 100)
        barra = "●" * pieni + "·" * (segmenti - pieni)
        suffisso = f"  {dettaglio}" if dettaglio else ""
        self._scrivi(
            self._stile("  ◇", self.VIOLET)
            + " "
            + self._stile(barra, self.CYAN)
            + " "
            + self._stile(f"{percentuale:5.1f}%", self.WHITE, self.BOLD)
            + "  "
            + self._stile(f"{corrente}/{totale}", self.MUTED)
            + "  "
            + self._stile(etichetta + suffisso, self.WHITE)
        )

    def summary(
        self,
        titolo: str,
        valori: Mapping[str, object] | Iterable[tuple[str, object]],
        stato: str = "success",
    ) -> None:
        colore = self._LIVELLI[stato][2]
        simbolo = self._LIVELLI[stato][0]
        self._scrivi()
        self._scrivi(
            self._stile("╭─", colore)
            + " "
            + self._stile(f"{simbolo} {titolo.upper()}", colore, self.BOLD)
        )
        self.metrics(valori)
        self._scrivi(self._stile("╰" + "─" * (self.larghezza - 1), colore))


console = TerminalUI()


class TerminalArgumentParser(argparse.ArgumentParser):
    """ArgumentParser con errori coerenti con il resto dell'interfaccia."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        TerminalUI(stream=sys.stderr).error(f"Argomenti non validi · {message}")
        self.exit(2)
