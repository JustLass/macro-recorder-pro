import sys
import os
import json
import time
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QFileDialog, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QSlider, QMessageBox, QSystemTrayIcon, QMenu
)
from PyQt6.QtGui import QIcon, QFont, QKeySequence, QAction
from PyQt6.QtCore import Qt, QTimer

import keyboard  # pip install keyboard
from pynput import mouse, keyboard as pkbd

eventos = []
gravando = False
reproduzindo = False
pausado = False
ml = None
kl = None
start_time = [0]
arquivo_atual = [None]
timer_running = False

hotkeys = {
    'gravar': 'ctrl+alt+r',
    'parar': 'ctrl+alt+p',
    'reproduzir': 'ctrl+alt+e',
    'pausar': 'ctrl+alt+s'
}

def registrar_evento(evento):
    t = time.time() - start_time[0]
    eventos.append({'tempo': t, **evento})

class MacroRecorderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Recorder Pro (PyQt)")
        self.setWindowIcon(QIcon.fromTheme("media-record"))
        self.resize(600, 540)
        self.setStyleSheet(self.dark_stylesheet())
        self.tray = None
        self.criar_tray()

        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 12))
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.tabs)

        # --- Aba Macro ---
        self.tab_macro = QWidget()
        self.tabs.addTab(self.tab_macro, "Macro")

        vbox_macro = QVBoxLayout(self.tab_macro)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet("""
            QProgressBar {
                border-radius: 9px; background: #222;
                color: #fff; text-align: center; font: 11pt 'Segoe UI Semibold';
            }
            QProgressBar::chunk {
                background-color: #00e78a; border-radius: 9px;
            }
        """)
        vbox_macro.addWidget(self.progress)

        self.timer_label = QLabel("⏱ Pronto")
        self.timer_label.setStyleSheet("color:#7FEAFA;font-size:13pt;font-weight:600;")
        vbox_macro.addWidget(self.timer_label)

        # --- Slot de nome + salvar macro ---
        hsave = QHBoxLayout()
        self.input_nome_macro = QLineEdit()
        self.input_nome_macro.setPlaceholderText("Nome do macro/script")
        self.input_nome_macro.setStyleSheet("border-radius:8px;background:#262b33;color:#fff;padding:6px;font-size:11pt;min-width:130px;")
        hsave.addWidget(self.input_nome_macro)

        self.label_dir_macro = QLabel("Nenhum diretório selecionado")
        self.label_dir_macro.setStyleSheet("color:#aaa;font-size:10pt;")
        hsave.addWidget(self.label_dir_macro)

        self.btn_escolher_dir = QPushButton("📁")
        self.btn_escolher_dir.setFixedWidth(36)
        self.btn_escolher_dir.setStyleSheet("background:#30384a;color:#fff;border-radius:9px;")
        self.btn_escolher_dir.clicked.connect(self.selecionar_diretorio)
        hsave.addWidget(self.btn_escolher_dir)

        self.btn_salvar = QPushButton("💾 Salvar Macro")
        self.btn_salvar.setStyleSheet("background:#18dcff;color:#222;border-radius:10px;font-weight:600;font-size:11pt;padding:8px 16px;")
        self.btn_salvar.clicked.connect(self.salvar_macro)
        hsave.addWidget(self.btn_salvar)

        vbox_macro.addLayout(hsave)

        # Botões com ícones
        hbtns = QHBoxLayout()
        self.btn_gravar = self.icon_button("▶️ Gravar", "#00e78a", self.iniciar_gravacao)
        self.btn_parar = self.icon_button("⏹️ Parar", "#ea3546", self.parar_gravacao)
        self.btn_reproduzir = self.icon_button("🔄 Reproduzir", "#409cff", self.reproduzir_macro)
        self.btn_pausar = self.icon_button("⏸️ Pausar", "#f5a623", self.toggle_pause)
        self.btn_carregar = self.icon_button("📂 Carregar", "#7d5fff", self.carregar_macro)
        self.btn_limpar = self.icon_button("🗑️ Limpar", "#fd5e53", self.limpar_macro)
        for b in [self.btn_gravar, self.btn_parar, self.btn_reproduzir, self.btn_pausar, self.btn_carregar, self.btn_limpar]:
            hbtns.addWidget(b)
        vbox_macro.addLayout(hbtns)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#fff;font-size:11pt;")
        vbox_macro.addWidget(self.status_label)

        # --- Aba Configurações ---
        self.tab_conf = QWidget()
        self.tabs.addTab(self.tab_conf, "Configurações")
        vbox_conf = QVBoxLayout(self.tab_conf)

        self.input_rep = self.config_line(vbox_conf, "Repetições", "1", tip="Quantas vezes repetir o macro")

        hslider = QHBoxLayout()
        lbl_vel = QLabel("Velocidade:")
        lbl_vel.setStyleSheet("color:#aaa;font-size:10.5pt;font-weight:500;")
        hslider.addWidget(lbl_vel)
        self.slider_vel = QSlider(Qt.Orientation.Horizontal)
        self.slider_vel.setMinimum(1)
        self.slider_vel.setMaximum(40)
        self.slider_vel.setValue(10)
        self.slider_vel.setStyleSheet("QSlider { min-width:160px; }")
        self.slider_vel.valueChanged.connect(self.atualiza_label_vel)
        hslider.addWidget(self.slider_vel)
        self.lbl_slider_vel = QLabel("1.0x")
        self.lbl_slider_vel.setStyleSheet("color:#0af;font-size:11pt;margin-left:7px;")
        hslider.addWidget(self.lbl_slider_vel)
        vbox_conf.addLayout(hslider)

        self.input_delay = self.config_line(vbox_conf, "Delay entre repetições (s)", "0", tip="Tempo em segundos de espera entre cada repetição")
        self.input_timer = self.config_line(vbox_conf, "Temporizador antes de gravar (s)", "3", tip="Delay antes de começar a gravação")

        # HOTKEYS configuráveis
        self.hotkey_inputs = {}
        atalho_layout = QVBoxLayout()
        atalho_layout.addWidget(QLabel("<b>Atalhos Globais (Hotkeys):</b>"))
        for key, default in hotkeys.items():
            h = QHBoxLayout()
            l = QLabel(f"{key.capitalize()}:")
            l.setStyleSheet("color:#aaa;")
            inp = QLineEdit()
            inp.setText(default)
            inp.setPlaceholderText("ex: ctrl+alt+r")
            inp.setFixedWidth(130)
            inp.setStyleSheet("border-radius:7px;background:#333;color:#fff;padding:4px;font-size:10pt;")
            self.hotkey_inputs[key] = inp
            h.addWidget(l)
            h.addWidget(inp)
            atalho_layout.addLayout(h)
        btn_aplicar_hotkeys = QPushButton("Aplicar Hotkeys")
        btn_aplicar_hotkeys.setStyleSheet("background:#00e78a;color:#222;font-weight:600;padding:6px 13px;border-radius:7px;")
        btn_aplicar_hotkeys.clicked.connect(self.atualizar_hotkeys)
        atalho_layout.addWidget(btn_aplicar_hotkeys)
        vbox_conf.addLayout(atalho_layout)

        # --- Aba Eventos ---
        self.tab_eventos = QWidget()
        self.tabs.addTab(self.tab_eventos, "Eventos")
        vbox_ev = QVBoxLayout(self.tab_eventos)
        self.list_eventos = QListWidget()
        vbox_ev.addWidget(self.list_eventos)
        self.refresh_eventos_btn = QPushButton("Atualizar Lista")
        self.refresh_eventos_btn.clicked.connect(self.refresh_eventos)
        vbox_ev.addWidget(self.refresh_eventos_btn)

        # --- Aba Ajuda ---
        self.tab_help = QWidget()
        self.tabs.addTab(self.tab_help, "Ajuda")
        vbox_help = QVBoxLayout(self.tab_help)
        ajuda_html = """
        <h2 style='color:#7FEAFA;font-weight:700;'>Como usar os Hotkeys</h2>
        <ul style='color:#f0f0f0;font-size:11.5pt;'>
        <li>Defina os atalhos na aba <b>Configurações</b>. Use combinações como <b>ctrl+alt+r</b>, <b>ctrl+alt+p</b>, etc.</li>
        <li>O app pode minimizar para o tray automaticamente quando perder o foco.</li>
        <li>Você pode restaurar clicando no ícone da bandeja.</li>
        <li>Alguns atalhos exigem rodar como root/sudo no Linux.</li>
        </ul>
        <hr>
        <b>Dúvidas? Fale com Rafael Lass.</b>
        """
        tedit = QTextEdit()
        tedit.setReadOnly(True)
        tedit.setHtml(ajuda_html)
        tedit.setStyleSheet("background:#222; color:#fff; font-size:11pt; border:0;")
        vbox_help.addWidget(tedit)

        # Timer para barra/timer_label/status
        self.timer = QTimer()
        self.timer.timeout.connect(self.atualizar_timer)
        self.timer.start(500)
        self.atualizar_status()
        self.dir_macro = os.path.expanduser("~")

        # Inicia ouvindo hotkeys
        self.hotkey_threads = []
        self.atualizar_hotkeys()

    def criar_tray(self):
        # System tray
        self.tray = QSystemTrayIcon(QIcon.fromTheme("media-record"), self)
        self.tray.setToolTip("Macro Recorder Pro (PyQt)")
        menu = QMenu()
        rest_action = QAction("Restaurar", self)
        rest_action.triggered.connect(self.restaurar_janela)
        sair_action = QAction("Sair", self)
        sair_action.triggered.connect(self.fechar_app)
        menu.addAction(rest_action)
        menu.addSeparator()
        menu.addAction(sair_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.restaurar_janela)
        self.tray.show()

    def restaurar_janela(self, *args):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def fechar_app(self, *args):
        QApplication.quit()

    def focusOutEvent(self, event):
        self.hide()  # Minimiza para tray ao perder o foco

    def icon_button(self, label, color, func):
        b = QPushButton(label)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {color}; color: #222;
                border-radius: 12px; font-weight:600; font-size:11pt; padding:9px 17px;
            }}
            QPushButton:hover {{ background: #1a2a3c; color:#fff; }}
        """)
        b.clicked.connect(func)
        return b

    def config_line(self, layout, desc, default, tip=""):
        h = QHBoxLayout()
        lbl = QLabel(desc+":")
        lbl.setStyleSheet("color:#aaa;font-size:10.5pt;font-weight:500;")
        if tip: lbl.setToolTip(tip)
        inp = QLineEdit()
        inp.setFixedWidth(70)
        inp.setText(str(default))
        inp.setStyleSheet("border-radius:7px;background:#333;color:#fff;padding:5px;font-size:11pt;")
        h.addWidget(lbl)
        h.addWidget(inp)
        layout.addLayout(h)
        return inp

    def atualiza_label_vel(self):
        v = self.slider_vel.value()
        vel = round(v / 10, 2)
        self.lbl_slider_vel.setText(f"{vel}x")

    def dark_stylesheet(self):
        return """
            QWidget { background: #181c22; color: #fff; font-family: 'Segoe UI', 'Arial', sans-serif; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #20242b; color: #fff; padding: 8px 24px; border-radius:10px 10px 0 0;}
            QTabBar::tab:selected { background: #161921; color: #00e78a; }
            QLabel { font-size:11pt; }
            QPushButton { border:none; }
            QLineEdit, QTextEdit { background:#232830; color:#fff; border-radius:8px; }
            QListWidget { background:#15171b; border-radius:8px; color:#f0f0f0;}
        """

    def selecionar_diretorio(self):
        dir_sel = QFileDialog.getExistingDirectory(self, "Escolha o diretório para salvar")
        if dir_sel:
            self.dir_macro = dir_sel
            self.label_dir_macro.setText(dir_sel)

    # --- Macro Logic: Gravar, Parar, Reproduzir etc ---
    def iniciar_gravacao(self):
        global gravando, ml, kl, start_time, eventos
        if gravando:
            return
        try:
            segundos = int(self.input_timer.text())
            if segundos < 0: segundos = 0
        except:
            segundos = 3
        self.status_label.setText(f"Gravando em {segundos}s...")
        self.timer_label.setText(f"⏱ Gravando em {segundos}s...")
        self.progress.setValue(0)
        eventos.clear()
        self.atualizar_status()
        def start_real():
            global gravando, ml, kl, start_time
            gravando = True
            start_time[0] = time.time()
            ml = mouse.Listener(on_click=self.on_click, on_scroll=self.on_scroll, on_move=self.on_move)
            kl = pkbd.Listener(on_press=self.on_press, on_release=self.on_release)
            ml.start()
            kl.start()
            self.timer_label.setText("⏱ Gravando...")
            self.atualizar_status()
        QTimer.singleShot(segundos * 1000, start_real)

    def parar_gravacao(self):
        global gravando, ml, kl, eventos
        if not gravando: return
        gravando = False
        if ml: ml.stop()
        if kl: kl.stop()
        now = time.time() - start_time[0]
        eventos_filtrados = [e for e in eventos if not (e['tipo']=='mouse_click' and now-e['tempo']<1.5)]
        eventos[:] = eventos_filtrados
        self.atualizar_status()
        self.timer_label.setText("⏱ Gravação parada.")

    def reproduzir_macro(self):
        global reproduzindo, pausado
        if reproduzindo or gravando or not eventos:
            return
        reproduzindo = True
        pausado = False
        try: reps = int(self.input_rep.text())
        except: reps = 1
        vel = round(self.slider_vel.value()/10, 2)
        try: delay = float(self.input_delay.text())
        except: delay = 0

        def run():
            from pynput import mouse as pm, keyboard as pk
            mousec = pm.Controller()
            keyboardc = pk.Controller()
            total = len(eventos)*reps
            done = 0
            for rep in range(reps):
                pressionadas = set()
                for i, e in enumerate(eventos):
                    while pausado: time.sleep(0.1)
                    done += 1
                    QTimer.singleShot(0, lambda d=done: self.progress.setValue(d*100//total))
                    if i>0:
                        t = (e['tempo']-eventos[i-1]['tempo'])/vel
                        if t>0: time.sleep(t)
                    if e['tipo'] == 'mouse_move':
                        mousec.position = (e['x'],e['y'])
                    elif e['tipo']=='mouse_click':
                        mousec.position=(e['x'],e['y'])
                        btn = pm.Button.left if 'left' in e['botao'] else pm.Button.right
                        if e['pressed']: mousec.press(btn)
                        else: mousec.release(btn)
                    elif e['tipo']=='mouse_scroll':
                        mousec.position=(e['x'],e['y'])
                        mousec.scroll(e['dx'],e['dy'])
                    elif e['tipo']=='key_press':
                        tecla=e['tecla']
                        if len(tecla)==1:
                            keyboardc.press(tecla)
                            pressionadas.add(tecla)
                        else:
                            try:
                                val = getattr(pk.Key, tecla.replace('Key.',''))
                                keyboardc.press(val)
                                pressionadas.add(val)
                            except: pass
                    elif e['tipo']=='key_release':
                        tecla=e['tecla']
                        if len(tecla)==1:
                            keyboardc.release(tecla)
                            pressionadas.discard(tecla)
                        else:
                            try:
                                val = getattr(pk.Key, tecla.replace('Key.',''))
                                keyboardc.release(val)
                                pressionadas.discard(val)
                            except: pass
                for tecla in list(pressionadas):
                    try: keyboardc.release(tecla)
                    except: pass
                if rep<reps-1 and delay>0:
                    QTimer.singleShot(0, lambda: self.status_label.setText(f"Aguardando {delay}s para próxima repetição..."))
                    time.sleep(delay)
            QTimer.singleShot(0, lambda: self.status_label.setText("Pronto"))
            QTimer.singleShot(0, lambda: self.timer_label.setText("⏱ Pronto"))
            QTimer.singleShot(0, lambda: self.progress.setValue(100))
            global reproduzindo
            reproduzindo = False

        threading.Thread(target=run, daemon=True).start()
        self.timer_label.setText("⏱ Reproduzindo...")
        self.status_label.setText("Reproduzindo...")

    def toggle_pause(self):
        global pausado
        pausado = not pausado
        self.status_label.setText("Pausado" if pausado else "Reproduzindo...")

    def carregar_macro(self):
        global eventos, arquivo_atual
        fname, _ = QFileDialog.getOpenFileName(self, "Carregar Macro", self.dir_macro, "Arquivos JSON (*.json)")
        if fname:
            with open(fname) as f:
                eventos.clear()
                eventos.extend(json.load(f))
            arquivo_atual[0]=fname
            self.input_nome_macro.setText(os.path.splitext(os.path.basename(fname))[0])
            self.dir_macro = os.path.dirname(fname)
            self.label_dir_macro.setText(self.dir_macro)
            self.atualizar_status()
            self.timer_label.setText("⏱ Macro carregado!")

    def salvar_macro(self):
        global eventos, arquivo_atual
        nome = self.input_nome_macro.text().strip()
        if not nome:
            QMessageBox.warning(self, "Erro ao salvar", "Digite um nome para o macro antes de salvar.")
            return
        dir_dest = self.dir_macro
        if not os.path.isdir(dir_dest):
            QMessageBox.warning(self, "Erro ao salvar", "Selecione um diretório válido para salvar o macro.")
            return
        fname = os.path.join(dir_dest, f"{nome}.json")
        with open(fname, "w") as f:
            json.dump(eventos, f, indent=2)
        arquivo_atual[0]=fname
        QMessageBox.information(self, "Macro salvo", f"Macro salvo como '{nome}.json' em:\n{dir_dest}")
        self.timer_label.setText(f"⏱ Macro salvo: {nome}.json")
        self.atualizar_status()

    def limpar_macro(self):
        global eventos
        eventos.clear()
        self.status_label.setText("Macro limpo!")
        self.progress.setValue(0)
        self.refresh_eventos()

    def atualizar_status(self):
        s = ""
        if gravando:
            s += "Gravando... "
        elif reproduzindo:
            s += "Reproduzindo... "
        if arquivo_atual[0]:
            s += f"Arquivo: {os.path.basename(arquivo_atual[0])} "
        s += f"Eventos: {len(eventos)}"
        self.status_label.setText(s)

    def atualizar_timer(self):
        if gravando:
            t = int(time.time() - start_time[0])
            self.timer_label.setText(f"⏱ Gravando: {t}s")
        elif reproduzindo:
            self.timer_label.setText("⏱ Reproduzindo...")
        elif not gravando and not reproduzindo:
            self.timer_label.setText("⏱ Pronto")
        self.refresh_eventos()

    def refresh_eventos(self):
        self.list_eventos.clear()
        for e in eventos:
            s = f"{e['tipo']} ({e.get('x','')},{e.get('y','')}) - t={e['tempo']:.2f}s"
            item = QListWidgetItem(s)
            self.list_eventos.addItem(item)

    # HOTKEYS
    def atualizar_hotkeys(self):
        # Remove hotkeys antigos
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        for key in hotkeys:
            novo = self.hotkey_inputs[key].text().strip()
            if novo:
                hotkeys[key] = novo
        # Cria os hooks novos
        def safe_thread(func):
            def call():
                QTimer.singleShot(0, func)
            return call
        keyboard.add_hotkey(hotkeys['gravar'], safe_thread(self.iniciar_gravacao))
        keyboard.add_hotkey(hotkeys['parar'], safe_thread(self.parar_gravacao))
        keyboard.add_hotkey(hotkeys['reproduzir'], safe_thread(self.reproduzir_macro))
        keyboard.add_hotkey(hotkeys['pausar'], safe_thread(self.toggle_pause))

    # ----- pynput handlers -----
    def on_click(self, x, y, button, pressed):
        registrar_evento({
            'tipo': 'mouse_click',
            'x': x,
            'y': y,
            'botao': str(button),
            'pressed': pressed
        })

    def on_scroll(self, x, y, dx, dy):
        registrar_evento({
            'tipo': 'mouse_scroll',
            'x': x,
            'y': y,
            'dx': dx,
            'dy': dy
        })

    def on_move(self, x, y):
        registrar_evento({
            'tipo': 'mouse_move',
            'x': x,
            'y': y
        })

    def on_press(self, key):
        try:
            k = key.char
        except AttributeError:
            k = str(key)
        registrar_evento({'tipo': 'key_press', 'tecla': k})

    def on_release(self, key):
        try:
            k = key.char
        except AttributeError:
            k = str(key)
        registrar_evento({'tipo': 'key_release', 'tecla': k})

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MacroRecorderApp()
    mainWin.show()
    sys.exit(app.exec())
