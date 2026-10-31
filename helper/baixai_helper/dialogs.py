"""Diálogos do sistema (escolher pasta) e 'mostrar no gerenciador de arquivos'."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .errors import BaixaiError


def choose_folder(prompt: str = "Escolha a pasta de downloads") -> str | None:
    """Abre o seletor de pastas do sistema. Retorna None se o usuário cancelar."""
    if sys.platform == "darwin":
        cmd = ["osascript", "-e", f'POSIX path of (choose folder with prompt "{prompt}")']
    elif sys.platform == "win32":
        ps = ("Add-Type -AssemblyName System.Windows.Forms;"
              f"$d=New-Object System.Windows.Forms.FolderBrowserDialog;$d.Description='{prompt}';"
              "if($d.ShowDialog() -eq 'OK'){[Console]::Out.Write($d.SelectedPath)}")
        cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps]
    elif shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory", f"--title={prompt}"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", str(Path.home())]
    else:
        raise BaixaiError("no_dialog", "Nenhum seletor de pastas disponível. Informe o caminho manualmente nas configurações.")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0)
    except (OSError, subprocess.TimeoutExpired):
        raise BaixaiError("no_dialog", "Não foi possível abrir o seletor de pastas.") from None
    path = out.stdout.strip()
    return path.rstrip("\n") or None if out.returncode == 0 else None


def reveal(path: Path) -> None:
    """Mostra o arquivo (ou a pasta) no gerenciador de arquivos. Argumentos estruturados, sem shell."""
    if not path.exists():
        raise BaixaiError("missing_file", "O arquivo não existe mais no disco (foi movido ou apagado).")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{path}"])
        else:
            subprocess.Popen(["xdg-open", str(path.parent if path.is_file() else path)])
    except OSError:
        raise BaixaiError("reveal_failed", "Não foi possível abrir o gerenciador de arquivos.") from None
