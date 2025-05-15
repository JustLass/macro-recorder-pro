# Macro Recorder Pro

> Gravador e executor de macros de mouse e teclado – Open Source, multiplataforma (Windows/Linux).

## Funcionalidades

- Grava movimentos do mouse, cliques, teclado e rolagem
- Interface moderna (PyQt5)
- Hotkeys globais (teclas de atalho)*
- Salva, carrega, repete e controla velocidade dos scripts
- Dark mode

> *No Linux, hotkeys globais requerem execução como root.

---

## Instalação

### **Windows**

1. Instale Python 3: [python.org](https://www.python.org/downloads/)
2. Instale dependências:
    ```sh
    pip install pyqt5 pynput keyboard
    ```
3. Para gerar .exe (opcional):
    ```sh
    pip install pyinstaller
    pyinstaller --onefile --windowed macroqt5.py
    ```
    O executável aparecerá em `dist\`.

### **Linux**

1. Instale Python 3.
2. Instale dependências:
    ```sh
    pip3 install pyqt5 pynput keyboard
    ```
3. Rode:
    ```sh
    python3 macroqt5.py
    ```
4. Para uso completo (hotkeys globais):
    ```sh
    sudo python3 macroqt5.py
    ```

---

## Como usar

1. Execute `macroqt5.py` (ou `macroqt5.exe` se gerado).
2. Grave, salve e execute suas macros!
3. Veja instruções detalhadas em [README.txt](./README.txt) (ou abaixo).

---

## Releases

Versões compiladas (.exe e .deb) podem ser disponibilizadas na área de [Releases](https://github.com/SEUUSUARIO/macro-recorder-pro/releases).

---

## Licença

MIT – use, modifique e contribua!

---

## Créditos

Desenvolvido por Rafael Lass.

---



---

## Contribua

Pull requests e sugestões são bem-vindos!  
