import threading
import time
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pynput import mouse, keyboard
import os
import sys

try:
    import keyboard as kb  # keyboard lib para hotkeys globais
except ImportError:
    kb = None

eventos = []
gravando = False
reproduzindo = False
pausado = False
ml = None
kl = None
start_time = [0]
arquivo_atual = [None]
timer_var = None
timer_running = False

dark_mode = [False]

def atualizar_status():
    status = []
    if gravando:
        status.append("Gravando")
    elif len(eventos) > 0:
        status.append(f"{len(eventos)} evento(s) na memória")
    else:
        status.append("Nenhum macro na memória")
    if arquivo_atual[0]:
        status.append(f"Arquivo: {os.path.basename(arquivo_atual[0])}")
    status_label.config(text=" | ".join(status))

def registrar_evento(evento):
    t = time.time() - start_time[0]
    eventos.append({'tempo': t, **evento})

def on_click(x, y, button, pressed):
    registrar_evento({
        'tipo': 'mouse_click',
        'x': x,
        'y': y,
        'botao': str(button),
        'pressed': pressed
    })

def on_scroll(x, y, dx, dy):
    registrar_evento({
        'tipo': 'mouse_scroll',
        'x': x,
        'y': y,
        'dx': dx,
        'dy': dy
    })

def on_move(x, y):
    registrar_evento({
        'tipo': 'mouse_move',
        'x': x,
        'y': y
    })

def on_press(key):
    try:
        k = key.char
    except AttributeError:
        k = str(key)
    registrar_evento({'tipo': 'key_press', 'tecla': k})

def on_release(key):
    try:
        k = key.char
    except AttributeError:
        k = str(key)
    registrar_evento({'tipo': 'key_release', 'tecla': k})

def iniciar_gravacao():
    def gravar():
        global ml, kl, gravando, start_time, timer_running
        gravando = True
        start_time[0] = time.time()
        ml = mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move)
        kl = keyboard.Listener(on_press=on_press, on_release=on_release)
        ml.start()
        kl.start()
        timer_running = True
        progress['value'] = 0
        atualizar_status()
        atualizar_timer()
    try:
        segundos = int(entry_tempo_espera_gravacao.get())
        if segundos < 0: segundos = 0
    except:
        segundos = 3
    status_label.config(text=f"Gravando em {segundos} seg...")
    app.update()
    def aguarda_e_grava():
        time.sleep(segundos)
        gravar()
        status_label.config(text="Gravando...")
    threading.Thread(target=aguarda_e_grava, daemon=True).start()

def parar_gravacao():
    global ml, kl, gravando, timer_running
    gravando = False
    timer_running = False
    if ml: ml.stop()
    if kl: kl.stop()
    pressionadas = set()
    for e in eventos:
        if e['tipo'] == 'key_press':
            pressionadas.add(e['tecla'])
        elif e['tipo'] == 'key_release' and e['tecla'] in pressionadas:
            pressionadas.remove(e['tecla'])
    now = time.time() - start_time[0]
    for tecla in pressionadas:
        eventos.append({'tempo': now, 'tipo': 'key_release', 'tecla': tecla})
    LIMITE_TEMPO = 1.5
    eventos_filtrados = []
    for e in eventos:
        if not (e['tipo'] == 'mouse_click' and now - e['tempo'] < LIMITE_TEMPO):
            eventos_filtrados.append(e)
    removidos = len(eventos) - len(eventos_filtrados)
    eventos.clear()
    eventos.extend(eventos_filtrados)
    atualizar_status()
    messagebox.showinfo("Macro", f"Gravação pausada!\n{len(eventos)} eventos em memória.\nTeclas travadas corrigidas automaticamente!\n{removidos} clique(s) próximo(s) ao Parar removido(s).")

def limpar_macro():
    global eventos
    eventos.clear()
    atualizar_status()
    messagebox.showinfo("Macro", "Macro limpo da memória.")

def salvar_macro():
    if len(eventos) == 0:
        messagebox.showwarning("Salvar", "Nenhum macro na memória para salvar!")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".json", filetypes=[("Arquivos JSON", "*.json")],
        title="Salvar Macro"
    )
    if path:
        with open(path, "w") as f:
            json.dump(eventos, f, indent=2)
        arquivo_atual[0] = path
        messagebox.showinfo("Macro", f"Macro salvo em:\n{path}")
    atualizar_status()

def carregar_macro():
    global eventos
    path = filedialog.askopenfilename(
        defaultextension=".json", filetypes=[("Arquivos JSON", "*.json")],
        title="Carregar Macro"
    )
    if path:
        try:
            with open(path) as f:
                eventos.clear()
                eventos.extend(json.load(f))
            arquivo_atual[0] = path
            messagebox.showinfo("Macro", f"Macro carregado de:\n{path}\n{len(eventos)} eventos na memória.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar macro:\n{e}")
    atualizar_status()

def toggle_pause():
    global pausado
    pausado = not pausado
    if pausado:
        status_label.config(text="Pausado")
        pause_btn.config(text="Retomar")
    else:
        status_label.config(text="Reproduzindo...")
        pause_btn.config(text="Pausar")

def reproduzir_macro():
    if len(eventos) == 0:
        messagebox.showwarning("Reproduzir", "Nenhum macro na memória para reproduzir!")
        return
    import pynput
    global reproduzindo, timer_running, pausado
    mousec = pynput.mouse.Controller()
    keyboardc = pynput.keyboard.Controller()
    status_label.config(text="Reproduzindo...")

    try:
        n_reps = int(entry_repeticoes.get())
        if n_reps < 1:
            n_reps = 1
    except Exception:
        n_reps = 1

    try:
        velocidade = float(entry_velocidade.get())
        if velocidade <= 0:
            velocidade = 1.0
    except Exception:
        velocidade = 1.0

    try:
        delay_entre_reps = float(entry_tempo_entre_reps.get())
        if delay_entre_reps < 0:
            delay_entre_reps = 0
    except Exception:
        delay_entre_reps = 0

    total_eventos = len(eventos) * n_reps

    def run():
        global reproduzindo, timer_running, pausado
        reproduzindo = True
        timer_running = True
        evento_cont = 0
        for rep in range(n_reps):
            pressionadas = set()
            for i, evento in enumerate(eventos):
                while pausado:
                    time.sleep(0.1)
                evento_cont += 1
                progress['value'] = (evento_cont / total_eventos) * 100
                app.update_idletasks()
                if i > 0:
                    tempo_espera = (evento['tempo'] - eventos[i-1]['tempo']) / velocidade
                    if tempo_espera > 0:
                        time.sleep(tempo_espera)
                if evento['tipo'] == 'mouse_move':
                    mousec.position = (evento['x'], evento['y'])
                elif evento['tipo'] == 'mouse_click':
                    mousec.position = (evento['x'], evento['y'])
                    botao = pynput.mouse.Button.left if 'left' in evento['botao'] else pynput.mouse.Button.right
                    if evento['pressed']:
                        mousec.press(botao)
                    else:
                        mousec.release(botao)
                elif evento['tipo'] == 'mouse_scroll':
                    mousec.position = (evento['x'], evento['y'])
                    mousec.scroll(evento['dx'], evento['dy'])
                elif evento['tipo'] == 'key_press':
                    tecla = evento['tecla']
                    if len(tecla) == 1:
                        keyboardc.press(tecla)
                        pressionadas.add(tecla)
                    else:
                        try:
                            val = getattr(pynput.keyboard.Key, tecla.replace('Key.', ''))
                            keyboardc.press(val)
                            pressionadas.add(val)
                        except AttributeError:
                            pass
                elif evento['tipo'] == 'key_release':
                    tecla = evento['tecla']
                    if len(tecla) == 1:
                        keyboardc.release(tecla)
                        pressionadas.discard(tecla)
                    else:
                        try:
                            val = getattr(pynput.keyboard.Key, tecla.replace('Key.', ''))
                            keyboardc.release(val)
                            pressionadas.discard(val)
                        except AttributeError:
                            pass
            for tecla in list(pressionadas):
                try:
                    keyboardc.release(tecla)
                except Exception:
                    pass
            pressionadas.clear()
            if rep < n_reps - 1 and delay_entre_reps > 0:
                status_label.config(text=f"Aguardando {delay_entre_reps}s para próxima repetição...")
                app.update()
                time.sleep(delay_entre_reps)
        reproduzindo = False
        timer_running = False
        progress['value'] = 100
        status_label.config(text="Pronto")
        atualizar_status()
        try:
            from plyer import notification
            notification.notify(
                title="Macro Recorder",
                message="Macro finalizado!",
                app_name="Macro Recorder"
            )
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()
    atualizar_timer()

def atualizar_timer():
    global timer_var, timer_running
    if timer_running:
        if gravando:
            tempo = int(time.time() - start_time[0])
            timer_label.config(text=f"⏱ Gravando: {tempo}s")
        elif reproduzindo:
            timer_label.config(text=f"⏱ Reproduzindo...")
        else:
            timer_label.config(text="")
        app.after(500, atualizar_timer)
    else:
        timer_label.config(text="")

def toggle_dark_mode():
    global dark_mode
    if not dark_mode[0]:
        app.tk_setPalette(background='#20242b', foreground='#fff', activeBackground='#444', activeForeground='#fff')
        dark_mode[0] = True
    else:
        app.tk_setPalette(background='#ececec', foreground='#000', activeBackground='#dcdcdc', activeForeground='#000')
        dark_mode[0] = False

def show_about():
    messagebox.showinfo("Sobre o App", """
Mouse/Keyboard Macro Recorder Pro

Recursos:
- Gravação/Reprodução de Mouse e Teclado
- Pausa/Retomar durante execução (botão ou F7)
- Barra de Progresso e Timer ao vivo
- Atalhos Globais: F9 (Gravar), F10 (Parar), F8 (Reproduzir)
- Dark Mode
- Temporizador, Delay, Repetições e Velocidade

Sugestões? Só chamar o Rafael Lass!
    """)

def iniciar_atalhos():
    if kb:
        kb.add_hotkey('F9', lambda: threading.Thread(target=iniciar_gravacao, daemon=True).start())
        kb.add_hotkey('F10', parar_gravacao)
        kb.add_hotkey('F8', reproduzir_macro)
        kb.add_hotkey('F7', toggle_pause)

# --- GUI
app = tk.Tk()
app.title("Mouse/Keyboard Macro Recorder Pro")
app.geometry("470x500")

notebook = ttk.Notebook(app)
notebook.pack(fill='both', expand=True)

# --- Aba Macro (básico) ---
frame_macro = tk.Frame(notebook)
frame_macro.pack(fill='both', expand=True)
notebook.add(frame_macro, text='Macro')

btn_carregar = tk.Button(frame_macro, text="Carregar", command=carregar_macro, width=18)
btn_gravar = tk.Button(frame_macro, text="Gravar", command=lambda: threading.Thread(target=iniciar_gravacao, daemon=True).start(), width=18)
btn_parar = tk.Button(frame_macro, text="Parar", command=parar_gravacao, width=18)
btn_limpar = tk.Button(frame_macro, text="Limpar", command=limpar_macro, width=18)
btn_salvar = tk.Button(frame_macro, text="Salvar", command=salvar_macro, width=18)
btn_reproduzir = tk.Button(frame_macro, text="Reproduzir", command=reproduzir_macro, width=18)
pause_btn = tk.Button(frame_macro, text="Pausar", command=toggle_pause, width=18)

btn_carregar.pack(pady=2)
btn_gravar.pack(pady=2)
btn_parar.pack(pady=2)
btn_limpar.pack(pady=2)
btn_salvar.pack(pady=2)
btn_reproduzir.pack(pady=2)
pause_btn.pack(pady=2)

status_label = tk.Label(frame_macro, text="", fg="blue")
status_label.pack(pady=8)

timer_label = tk.Label(frame_macro, text="", fg="green", font=("Arial", 11, "bold"))
timer_label.pack(pady=2)

progress = ttk.Progressbar(frame_macro, orient='horizontal', length=240, mode='determinate')
progress.pack(pady=4)

# --- Aba Configurações ---
frame_config = tk.Frame(notebook)
frame_config.pack(fill='both', expand=True)
notebook.add(frame_config, text='Configurações Avançadas')

frame_rept = tk.Frame(frame_config)
frame_rept.pack(pady=6)
tk.Label(frame_rept, text="Repetições:").pack(side=tk.LEFT)
entry_repeticoes = tk.Entry(frame_rept, width=7)
entry_repeticoes.insert(0, "1")
entry_repeticoes.pack(side=tk.LEFT)

frame_vel = tk.Frame(frame_config)
frame_vel.pack(pady=6)
tk.Label(frame_vel, text="Velocidade:").pack(side=tk.LEFT)
entry_velocidade = tk.Entry(frame_vel, width=7)
entry_velocidade.insert(0, "1")
entry_velocidade.pack(side=tk.LEFT)

frame_delay = tk.Frame(frame_config)
frame_delay.pack(pady=6)
tk.Label(frame_delay, text="Delay entre repetições (s):").pack(side=tk.LEFT)
entry_tempo_entre_reps = tk.Entry(frame_delay, width=7)
entry_tempo_entre_reps.insert(0, "0")
entry_tempo_entre_reps.pack(side=tk.LEFT)

frame_temp = tk.Frame(frame_config)
frame_temp.pack(pady=6)
tk.Label(frame_temp, text="Temporizador antes de gravar (s):").pack(side=tk.LEFT)
entry_tempo_espera_gravacao = tk.Entry(frame_temp, width=7)
entry_tempo_espera_gravacao.insert(0, "3")
entry_tempo_espera_gravacao.pack(side=tk.LEFT)

frame_dark = tk.Frame(frame_config)
frame_dark.pack(pady=6)
dark_mode_btn = tk.Button(frame_dark, text="Alternar Dark Mode", command=toggle_dark_mode, width=20)
dark_mode_btn.pack()

frame_help = tk.Frame(frame_config)
frame_help.pack(pady=6)
about_btn = tk.Button(frame_help, text="Ajuda/About", command=show_about, width=20)
about_btn.pack()

atualizar_status()

if kb:
    threading.Thread(target=iniciar_atalhos, daemon=True).start()

app.mainloop()
