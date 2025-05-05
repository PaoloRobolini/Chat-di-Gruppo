import base64
import json
import multiprocessing
import os
import socket
import threading
import time
from ftplib import FTP

from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty
from kivy.lang import Builder

from utente import utente

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label # Importa Label per i messaggi
from kivy.uix.boxlayout import BoxLayout # Importa BoxLayout
from kivy.graphics import Color, RoundedRectangle # Importa per disegnare rettangoli arrotondati
from kivy.uix.widget import Widget # Importa Widget per lo Spacer
from tkinter import Tk
from tkinter.filedialog import askopenfilename

import pyaudio
import struct

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
SILENCE_THRESHOLD = 500  # più basso = più sensibile

p = pyaudio.PyAudio()

stream_output = p.open(format=FORMAT,
                                   channels=CHANNELS,
                                   rate=RATE,
                                   output=True,
                                   frames_per_buffer=CHUNK)


Builder.load_file("chat.kv")

ip_server = "127.0.0.1"
porta_server = 50000
ftp_port = 21
server = (ip_server, porta_server)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(server)

coda_arrivo_msg = multiprocessing.Queue()
coda_manda_msg = multiprocessing.Queue()

chat = {}

# Variabili globali
global user
global temp_folder_info
temp_folder_info = None


def carica_gruppi():
    files_chat = [
        f for f in os.listdir('datiGruppi')
    ]

    for file in files_chat:
        s.sendall(json.dumps(user.crea_azione(comando="is_in_gruppo", nome_gruppo=file[:-5])).encode())
        data = s.recv(4096)
        if data == b"yes":
            with open(f"datiGruppi/{file}", "r") as f:
                dati = json.load(f)
                file = file[:-5]
                # Modificato: Memorizza i messaggi come lista di stringhe
                chat[file] = [f"{message['mittente']}> {message['messaggio']}" for message in dati['gruppo']]
                chat_screen = App.get_running_app().root.get_screen('chat')
                chat_screen.aggiungi_nuovo_contatto(file)


def carica_chat():
    files_chat = [
        f for f in os.listdir('datichat')
    ]

    for i in range(len(files_chat)):
        try:
            nome_file = files_chat[i]
            altro_utente = nome_file[:-5]
            altro_utente = altro_utente.split('_')
            altro_utente.remove(user.get_nome())
            altro_utente = altro_utente[0]

            with open('datichat/' + nome_file, 'r') as file:
                dati = json.load(file)
                # Modificato: Memorizza i messaggi come lista di stringhe
                chat[altro_utente] = [f"{message['mittente']}> {message['messaggio']}" for message in dati['chat']]
                chat_screen = App.get_running_app().root.get_screen('chat')
                chat_screen.aggiungi_nuovo_contatto(altro_utente)
        except ValueError:
            ...


def scarica_chat(cartella, cartella_temp, files):

    try:
        global temp_folder_info

        temp_folder_info = cartella_temp  # Salva le informazioni della cartella temporanea

        if not files:
            print("Nessun file da scaricare")
            return

        try:
            # Connessione FTP con autenticazione
            ftp = FTP()
            ftp.connect(ip_server, ftp_port)
            ftp.login(user=user.get_nome(), passwd=user.get_password())

            # Vai alla cartella temporanea
            try:
                ftp.cwd(cartella_temp)
            except Exception as e:
                print(f"Errore nell'accesso alla cartella {cartella_temp}: {e}")
                return

            # Scarica tutti i file e rimuovili dopo il download
            for nome_file in files:
                file_path = os.path.join(cartella, nome_file)
                print(f"Scaricamento di {nome_file}...")

                try:
                    with open(file_path, 'wb') as f:
                        ftp.retrbinary(f'RETR {nome_file}', f.write)
                    # Rimuovi il file temporaneo dal server dopo averlo scaricato
                    try:
                        ftp.delete(nome_file)
                        print(f"File temporaneo {nome_file} rimosso dal server")
                    except Exception as e:
                        print(f"Errore nella rimozione del file temporaneo {nome_file}: {e}")
                except Exception as e:
                    print(f"Errore nel download del file {nome_file}: {e}")
                    continue

            ftp.quit()

        except Exception as e:
            print(f"Errore durante il download dei file via FTP: {e}")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Errore nella lettura delle informazioni dei file: {e}")


def rimuovi_cartella_temp():
    global temp_folder_info
    if temp_folder_info is None:
        print("Nessuna informazione sulla cartella temporanea disponibile")
        return

    try:
        ftp = FTP()
        ftp.connect(ip_server, ftp_port)
        ftp.login(user=user.get_nome(), passwd=user.get_password())
        cartella_temp = temp_folder_info

        # Torna alla directory principale
        ftp.cwd("/")

        # Rimuovi la cartella temporanea
        try:
            # Prima rimuovi eventuali file rimanenti
            try:
                ftp.cwd(cartella_temp)
                for nome_file in ftp.nlst():
                    if nome_file not in ('.', '..'):
                        try:
                            ftp.delete(nome_file)
                        except:
                            try:
                                ftp.rmd(nome_file)
                            except Exception as e:
                                print(f"Impossibile rimuovere {nome_file}: {e}")
            except Exception as e:
                print(f"Errore nell'accesso alla cartella temporanea: {e}")

            # Torna alla directory principale e rimuovi la cartella
            ftp.cwd("/")
            ftp.rmd(cartella_temp)
            print(f"Cartella temporanea {cartella_temp} rimossa dal server")

            # Resetta le informazioni della cartella temporanea
            temp_folder_info = None

        except Exception as e:
            print(f"Errore nella rimozione della cartella temporanea {cartella_temp}: {e}")

        ftp.quit()

    except Exception as e:
        print(f"Errore nella connessione FTP: {e}")


class LoginScreen(Screen):

    def on_pre_enter(self, *args):
        self.ids.mail.text = ''
        self.ids.password.text = ''

    def check_state(self):
        if self.ids.ricorda.active:
            print("Checked")
        else:
            print("Unchecked")

    def login(self):
        mail = self.ids.mail.text.strip()
        password = self.ids.password.text.strip()
        if mail and password:
            global user
            user = utente(mail=mail, password=password)

            dati_serializzati = json.dumps(user.crea_azione(comando="login")).encode('utf-8')
            s.sendall(dati_serializzati)

            data = s.recv(4096)
            reply = data.decode()

            if reply != "1":
                chat_screen = self.manager.get_screen('chat')
                chat_screen.username = reply
                self.manager.current = 'chat'
                reply = reply.replace('"', '')
                user.set_nome(reply)

                data = s.recv(4096)
                dati = json.loads(data.decode())
                print(f"Chat e gruppi da scaricare: {dati}")
                scarica_chat('datiChat', dati['cartella'], dati['chat'])
                scarica_chat('datiGruppi', dati['cartella'], dati['gruppi'])
                rimuovi_cartella_temp()  # Rimuovi la cartella temporanea dopo aver scaricato tutto
                carica_chat()
                carica_gruppi()

                thread_ricevi = threading.Thread(target=ricevi_messaggi)
                thread_manda = threading.Thread(target=manda_messaggi)
                thread_manda.start()
                thread_ricevi.start()

            else:
                self.ids.login_data_error.text = "mail o password non corrispondono"
                self.ids.mail.text = ""
                self.ids.password.text = ""


class SigninScreen(Screen):
    def signin(self):
        username = self.ids.username.text
        mail = self.ids.mail.text.strip()
        password = self.ids.password.text.strip()
        if username and mail and password:
            global user
            user = utente(mail=mail, password=password, username=username)
            dati_serializzati = json.dumps(user.crea_azione(comando="signin")).encode('utf-8')
            s.sendall(dati_serializzati)

            data = s.recv(4096)
            reply = data.decode()

            if reply == "0":
                chat_screen = self.manager.get_screen('chat')
                chat_screen.username = username
                self.manager.current = 'chat'
                thread_ricevi = threading.Thread(target=ricevi_messaggi)
                thread_manda = threading.Thread(target=manda_messaggi)
                thread_manda.start()
                thread_ricevi.start()
            elif reply == "1":
                self.ids.signin_data_error.text = "la mail e` gia` associata a un account"
                self.ids.mail.text = ""
                self.ids.password.text = ""
                self.ids.username.text = ""
            elif reply == "2":
                self.ids.signin_data_error.text = "la mail non e` valida"
                self.ids.mail.text = ""
                self.ids.password.text = ""
                self.ids.username.text = ""


class ChatScreen(Screen):
    username = StringProperty("")
    contact_buttons = ListProperty([])
    selected_contact = StringProperty("Seleziona un contatto")
    _selected_contact_button = None # Aggiunta: variabile per tenere traccia del pulsante selezionato


    def logout(self):
        schermata = self.manager.get_screen('login')
        schermata.ids.username.text.clear()
        schermata.ids.password.text.clear()
        self.manager.current = 'login'

    def show_ai_status(self, show=True):
        if show:
            self.ids.ai_status.text = "L'AI sta elaborando la risposta..."
            self.ids.ai_status.opacity = 1
        else:
            self.ids.ai_status.text = ""
            self.ids.ai_status.opacity = 0

    def on_contact_buttons(self, instance, value):
        self.ids.contact_list_sidebar.clear_widgets()
        for contact in self.contact_buttons:
            # Modificato: Creazione del pulsante con stile di default
            btn = Button(
                text=contact,
                size_hint=(None, None),
                size=(90, 50),
                background_normal='',
                background_color=(0.2, 0.2, 0.3, 1), # Colore di default
                color=(1, 1, 1, 1),
                font_size=16
            )
            btn.bind(on_press=self.on_contact_button_click)
            self.ids.contact_list_sidebar.add_widget(btn)

    def on_contact_button_click(self, instance):
        global user
        testo = instance.text

        # Modificato: Gestione del colore di sfondo dei pulsanti
        if self._selected_contact_button:
            # Ripristina il colore del pulsante precedentemente selezionato
            self._selected_contact_button.background_color = (0.2, 0.2, 0.3, 1) # Colore di default

        # Imposta il colore del pulsante attualmente selezionato
        instance.background_color = (0.1, 0.6, 1, 1) # Colore selezionato (blu)

        # Aggiorna la variabile del pulsante selezionato
        self._selected_contact_button = instance

        user.set_destinatario(testo)
        self.selected_contact = f"Chat con {testo}"
        testo = testo.replace("'", '')
        try:
            # Quando si seleziona un contatto, carichiamo e visualizziamo la sua cronologia
            self.display_chat_history(testo)
        except KeyError:
            chat[testo] = [] # Inizializza la chat come lista vuota se non esiste
            self.display_chat_history(testo) # Visualizza la chat vuota

    def display_chat_history(self, contact):
        """Visualizza la cronologia della chat per il contatto selezionato."""
        self.ids.chat_history_container.clear_widgets() # Pulisce i messaggi precedenti
        if contact in chat:
            for message_text in chat[contact]:
                self.add_message_bubble(message_text) # Aggiunge ogni messaggio come una bolla

    def add_message_bubble(self, message_text):
        """Crea e aggiunge una bolla di messaggio alla chat con stile moderno."""
        # Determina se il messaggio è dell'utente corrente
        is_user_message = message_text.startswith(user.get_nome())
        is_system_message = message_text.startswith("[Sistema]")

        # Estrai mittente e messaggio
        if is_system_message:
            sender = "Sistema"
            message_content = message_text[9:].strip()
        else:
            parts = message_text.split('>', 1)
            if len(parts) > 1:
                sender = parts[0].strip()
                message_content = parts[1].strip()
            else:
                sender = "Sistema"
                message_content = message_text.strip()

        # Definisci i colori per diversi tipi di messaggi
        colors = {
            'user_bubble': (0.2, 0.6, 1, 1),
            'user_text': (1, 1, 1, 1),
            'other_bubble': (0.95, 0.95, 0.95, 1),
            'other_text': (0.2, 0.2, 0.2, 1),
            'system_bubble': (0.9, 0.9, 0.9, 0.7),
            'system_text': (0.4, 0.4, 0.4, 1),
            'sender_name_user': (1, 1, 1, 1),      # Nome utente in bianco per contrasto su sfondo blu
            'sender_name_other': (0.3, 0.3, 0.3, 1)  # Nome altri utenti in grigio scuro per contrasto su sfondo chiaro
        }

        # Scegli i colori appropriati
        if is_system_message:
            bubble_color = colors['system_bubble']
            text_color = colors['system_text']
        elif is_user_message:
            bubble_color = colors['user_bubble']
            text_color = colors['user_text']
        else:
            bubble_color = colors['other_bubble']
            text_color = colors['other_text']

        # Crea il layout della riga del messaggio
        row = BoxLayout(
            size_hint_y=None,
            height=44,  # Altezza iniziale che verrà aggiornata
            padding=[10, 5, 10, 5],  # Padding esterno della riga
            spacing=10
        )

        # Crea il layout della bolla
        bubble = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(0, 0),  # Sarà aggiornato in base al contenuto
            padding=[15, 10, 15, 10],  # Padding interno della bolla
            spacing=4
        )

        max_bubble_width = self.ids.chat_history_container.width * 0.7

        temp_label = Label(
            text=message_content,
            font_size='16sp'  # Aumentato da 14sp a 16sp
        )
        temp_label.texture_update()

        text_width = min(max(temp_label.texture_size[0] + 20, 100), max_bubble_width - bubble.padding[0] - bubble.padding[2])

        # Aggiungi il nome del mittente se non è un messaggio di sistema
        if not is_system_message:
            sender_label = Label(
                text=sender,
                size_hint=(None, None),
                color=colors['sender_name_user'] if is_user_message else colors['sender_name_other'],
                font_size='15sp',  # Aumentato da 12sp a 15sp
                bold=True,
                halign='left'
            )
            sender_label.bind(texture_size=sender_label.setter('size'))
            bubble.add_widget(sender_label)

        # Crea la label per il messaggio
        msg_label = Label(
            text=message_content,
            size_hint=(None, None),
            color=text_color,
            font_size='16sp',  # Aumentato da 14sp a 16sp
            text_size=(text_width, None),  # Usa la larghezza calcolata
            halign='left',
            valign='middle'
        )
        msg_label.bind(texture_size=msg_label.setter('size'))
        bubble.add_widget(msg_label)

        # Funzione per aggiornare le dimensioni della bolla
        def update_bubble_size(*args):
            # Calcola l'altezza totale del contenuto
            content_height = sum(c.height for c in bubble.children) + bubble.spacing * (len(bubble.children) - 1)
            # Trova la larghezza massima tra i widget
            content_width = max(c.width for c in bubble.children)
            # Aggiorna le dimensioni della bolla considerando il padding
            bubble.size = (
                content_width + bubble.padding[0] + bubble.padding[2],
                content_height + bubble.padding[1] + bubble.padding[3]
            )
            # Aggiorna l'altezza della riga
            row.height = bubble.height + row.padding[1] + row.padding[3]

        # Collega l'aggiornamento delle dimensioni
        msg_label.bind(texture_size=update_bubble_size)
        if not is_system_message:
            sender_label.bind(texture_size=update_bubble_size)

        # Aggiungi lo sfondo della bolla
        with bubble.canvas.before:
            Color(*bubble_color)
            if is_user_message:
                radius = [15, 15, 3, 15]
            else:
                radius = [15, 15, 15, 3]

            bubble_bg = RoundedRectangle(
                pos=bubble.pos,
                size=bubble.size,
                radius=radius
            )
            # Aggiorna la posizione e dimensione dello sfondo quando la bolla cambia
            bubble.bind(
                pos=lambda instance, value: setattr(bubble_bg, 'pos', value),
                size=lambda instance, value: setattr(bubble_bg, 'size', value)
            )

        # Aggiungi la bolla alla riga con l'allineamento appropriato
        if is_user_message:
            row.add_widget(Widget(size_hint_x=1))  # Spacer a sinistra
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            row.add_widget(Widget(size_hint_x=1))  # Spacer a destra

        update_bubble_size()

        # Aggiungi la riga alla chat
        self.ids.chat_history_container.add_widget(row)

    def send_message(self):
        message = self.ids.message_input.text.strip()
        if message and user.get_destinatario() is not None:
            if user.get_destinatario() not in chat:
                chat[user.get_destinatario()] = []

            # Aggiunge il messaggio alla chat locale immediatamente come stringa
            full_message_text = f"{user.get_nome()}> {message}"
            chat[user.get_destinatario()].append(full_message_text)
            self.add_message_bubble(full_message_text) # Aggiunge il bottone alla UI

            self.ids.message_input.text = ""

            # Se il destinatario è l'AI, mostra l'indicatore di stato
            if user.get_destinatario() == "AI":
                self.show_ai_status(True)

            # Crea e invia il messaggio in modo asincrono
            azione = user.crea_azione(comando="messaggio", messaggio=message)
            coda_manda_msg.put(azione)

    def receive_message(self, messaggio):
        if "nome_gruppo" in messaggio:
            chat_id = messaggio["nome_gruppo"]
        else:
            chat_id = messaggio["mittente"]

        nuovo_messaggio_text = f"{messaggio['mittente']} > {messaggio['messaggio']}"

        if chat_id not in self.contact_buttons:
            Clock.schedule_once(
                lambda dt: self.aggiungi_nuovo_contatto(chat_id)
            )

        if chat_id not in chat:
            chat[chat_id] = []
        chat[chat_id].append(nuovo_messaggio_text)

        if chat_id == user.get_destinatario():
            if chat_id == "AI":
                self.show_ai_status(False)
            Clock.schedule_once(
                lambda dt: self.add_message_bubble(nuovo_messaggio_text)
            )


    def aggiungicontatto(self):
        self.manager.current = 'aggiungicontatto'

    def aggiungi_nuovo_contatto(self, contatto):
        if contatto not in self.contact_buttons:
            self.contact_buttons.append(contatto)
            # Quando aggiungiamo un nuovo contatto, assicuriamoci che non sia selezionato
            # In questo caso, non facciamo nulla qui, la selezione avviene solo al click.


    def send_file(self, instance):
        root = Tk()
        root.withdraw()

        file_path = askopenfilename(title="scegli un file")

        if file_path:
            print(f"📤 File selezionato: {file_path}")
            nome_file_basename = os.path.basename(file_path)

            if user.get_destinatario() is None:
                print("Errore: destinatario non impostato per invio file")
                self.add_message_bubble(f"[Sistema] Errore: Seleziona un destinatario prima di inviare un file.")
                root.destroy()
                return

            self.add_message_bubble(f"[Sistema] Iniziando invio file {nome_file_basename} via FTP...")


            try:
                # Connessione FTP con autenticazione
                ftp = FTP()
                ftp.connect(ip_server, ftp_port)
                ftp.login(user=user.get_nome(), passwd=user.get_password())

                mittente_dir = user.get_nome()
                try:
                    ftp.cwd(mittente_dir)
                except:
                    try:
                        ftp.mkd(mittente_dir)
                        ftp.cwd(mittente_dir)
                    except Exception as e:
                        print(f"Errore nella creazione/accesso della directory {mittente_dir}: {e}")
                        self.add_message_bubble(f"[Sistema] Errore: Impossibile accedere alla directory del mittente.")
                        return

                with open(file_path, 'rb') as file:
                    ftp.storbinary(f'STOR {nome_file_basename}', file)

                ftp.quit()

                notifica = {
                    "comando": "ftp_file_notification",
                    "mittente": user.get_nome(),
                    "destinatario": user.get_destinatario(),
                    "nome_file": nome_file_basename
                }
                coda_manda_msg.put(notifica)

                self.add_message_bubble(f"[Sistema] File {nome_file_basename} inviato con successo via FTP!")


            except Exception as e:
                error_msg = f"[Sistema] Errore nell'invio del file via FTP: {str(e)}"
                self.add_message_bubble(error_msg)
                print(f"Errore FTP dettagliato: {e}")

        root.destroy()

    def update_ftp_progress(self, block, nome_file):
        print(f"[Progresso invio FTP] Trasferimento di {nome_file} in corso...")


    def receive_file(self, messaggio):
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")

        # Determina il mittente effettivo e il destinatario per il messaggio
        if comando == "nuovo_messaggio_gruppo":
            chat_id = messaggio.get("nome_gruppo")
        else:
            chat_id = mittente

        if comando in ["nuovo_messaggio_privato", "nuovo_messaggio_gruppo"] and "via FTP" in messaggio.get("messaggio", ""):
            # Aggiunge il messaggio di notifica file come una bolla
            self.add_message_bubble(f"{messaggio['mittente']} > {messaggio['messaggio']}")

            try:
                cartella_destinazione = "file_ricevuti"
                os.makedirs(cartella_destinazione, exist_ok=True)

                # Connessione FTP con autenticazione
                ftp = FTP()
                ftp.connect(ip_server, ftp_port)
                ftp.login(user=user.get_nome(), passwd=user.get_password())

                # Lista le directory disponibili
                print("Directory disponibili sul server:", ftp.nlst())

                # Entra nella directory del mittente
                try:
                    ftp.cwd(mittente)
                    print(f"Contenuto della directory {mittente}:", ftp.nlst())
                except Exception as e:
                    print(f"Errore nell'accesso alla directory {mittente}: {e}")
                    # Aggiunge il messaggio di errore come una bolla
                    self.add_message_bubble(f"[Sistema] Errore: Impossibile accedere alla directory del mittente per il download.")
                    return

                # Estrai il nome del file dal messaggio
                nome_file = None
                if "via FTP" in messaggio.get("messaggio", ""):
                    file_message = messaggio.get("messaggio", "")
                    start_index = file_message.find(": ") + 2
                    end_index = file_message.find(" (via FTP)")
                    if start_index > 1 and end_index > start_index:
                        nome_file = file_message[start_index:end_index]

                if nome_file is None:
                     print("Nome file non trovato nel messaggio")
                     self.add_message_bubble(f"[Sistema] Errore: Nome file non trovato nel messaggio.")
                     return


                # Verifica se il file esiste
                files_disponibili = ftp.nlst()
                print(f"File disponibili: {files_disponibili}")
                if nome_file not in files_disponibili:
                    print(f"File {nome_file} non trovato nella directory")
                    self.add_message_bubble(f"[Sistema] Errore: File '{nome_file}' non trovato sul server.")
                    return

                local_file_path = os.path.join(cartella_destinazione, nome_file)

                # Aggiunge un messaggio di progresso nella chat come una bolla
                self.add_message_bubble(f"[Sistema] Avvio download di {nome_file}...")


                with open(local_file_path, 'wb') as file:
                    def callback(chunk):
                        file.write(chunk)
                        print(f"[Download in corso] Ricezione di {nome_file} in corso...")


                    ftp.retrbinary(f'RETR {nome_file}', callback)

                ftp.quit()

                msg = f"[Sistema] File {nome_file} scaricato con successo in {cartella_destinazione}"
                # Aggiunge il messaggio di successo come una bolla
                self.add_message_bubble(msg)


            except Exception as e:
                error_msg = f"[Sistema] Errore nel download del file via FTP: {str(e)}"
                # Aggiunge il messaggio di errore come una bolla
                self.add_message_bubble(error_msg)
                print(f"Errore FTP dettagliato: {e}")



    chiamata_accettata = None
    lock = threading.Lock()


    def send_call(self):
        stream_input = p.open(format=FORMAT,
                              channels=CHANNELS,
                              rate=RATE,
                              input=True,
                              frames_per_buffer=CHUNK)
        while True:
            if self.chiamata_accettata is True:
                data = stream_input.read(CHUNK, exception_on_overflow=False)
                data = base64.b64encode(data).decode('utf-8')
                user.set_pacchetto_audio(data)
                azione = user.crea_azione(comando="chiamata")

                coda_manda_msg.put(azione)

                # Calcola energia del pacchetto audio
                data_decoded = base64.b64decode(data)  # 🔥 Da base64 torna a bytes veri
                samples = struct.unpack('<' + ('h' * (len(data_decoded) // 2)), data_decoded)
                energy = sum(abs(sample) for sample in samples) / len(samples)

                if energy > SILENCE_THRESHOLD:
                    print("🎙️ Sto inviando audio... (energia:", int(energy), ")")
                else:
                    print("😶 Silenzio mentre invio... (energia:", int(energy), ")")
            else:
                break
        # Assicurati che il thread termini correttamente
        if hasattr(self, 'thread') and self.thread.is_alive():
             self.thread.join()


    def start_call(self):
        if user.get_destinatario() is not None:
            with self.lock:
                accettata = self.chiamata_accettata

            if accettata is None:
                azione = user.crea_azione(comando="richiesta_chiamata")
                coda_manda_msg.put(azione)
            elif accettata is True:
                self.ids.incoming_call_box.opacity = 1
                self.ids.incoming_call_box.disabled = False
                # Assicurati che caller_name sia impostato correttamente
                self.ids.caller_name.text = user.get_destinatario() # Mostra il nome del destinatario
                self.thread = threading.Thread(target=self.send_call) # Salva il thread per poterlo joinare
                self.thread.start()
                print("thread avviato")
            elif accettata is False:
                # Assicurati che il thread esista prima di provare a joinarlo
                 if hasattr(self, 'thread') and self.thread.is_alive():
                    self.thread.join()


    def get_call(self, pacchetto_audio2):
        #thread che riceve e gestisce il pacchetto audio
        print(type(pacchetto_audio2))
        pacchetto_audio2 = base64.b64decode(pacchetto_audio2)
        stream_output.write(pacchetto_audio2)

        data_decoded = pacchetto_audio2
        samples = struct.unpack('<' + ('h' * (len(data_decoded) // 2)), data_decoded)
        energy = sum(abs(sample) for sample in samples) / len(samples)

        if energy > SILENCE_THRESHOLD:
            print("🔊 Sto ricevendo audio... (energia:", int(energy), ")")
        else:
            print("🛑 Ricevo silenzio... (energia:", int(energy), ")")

    def accettazione_chiamata(self, start_time):
        while True:
            now = time.time()
            elapsed = now - start_time

            with self.lock:
                accettata = self.chiamata_accettata

            if elapsed > 5 and accettata is None:
                with self.lock:
                    self.chiamata_accettata = False
                break

            if accettata is True or accettata is False:
                break

        with self.lock:
            if self.chiamata_accettata is True:
                azione = user.crea_azione(comando="chiamata_accettata")
            else:
                azione = user.crea_azione(comando="chiamata_rifiutata")
        coda_manda_msg.put(azione)

    def receive_call(self, messaggio):
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")

        if comando == "richiesta_chiamata":
            self.ids.incoming_call_box.opacity = 1
            self.ids.incoming_call_box.disabled = False
            self.ids.caller_name.text = mittente # Mostra il nome del chiamante
            start_time = time.time()
            thread = threading.Thread(target=self.accettazione_chiamata, args=(start_time,))
            thread.start()

        elif comando == "chiamata_accettata":
            with self.lock:
                self.chiamata_accettata = True
            self.start_call() # Avvia la chiamata in uscita dopo l'accettazione

        elif comando == "chiamata_rifiutata":
            with self.lock:
                self.chiamata_accettata = False
            # Nasconde la finestra di chiamata in arrivo se rifiutata
            self.ids.incoming_call_box.opacity = 0
            self.ids.incoming_call_box.disabled = True


        elif comando == "chiamata":
            pacchetto_audio = messaggio.get("pacchetto_audio")
            # user.set_destinatario(mittente) # Non impostare il destinatario qui, potrebbe cambiare la chat corrente
            thread = threading.Thread(target=self.get_call, args=(pacchetto_audio,))
            thread.start()


    def accetta_chiamata(self):
        with self.lock:
            self.chiamata_accettata = True
            azione = user.crea_azione(comando="chiamata_accettata")
            coda_manda_msg.put(azione)
            # Nasconde la finestra di chiamata in arrivo
            self.ids.incoming_call_box.opacity = 0
            self.ids.incoming_call_box.disabled = True
            # Avvia l'invio dell'audio solo se non è già in corso
            if not hasattr(self, 'thread') or not self.thread.is_alive():
                 self.thread = threading.Thread(target=self.send_call)
                 self.thread.start()


    def rifiuta_chiamata(self):
        with self.lock:
            self.chiamata_accettata = False
            azione = user.crea_azione(comando="chiamata_rifiutata")
            coda_manda_msg.put(azione)
            # Nasconde la finestra di chiamata in arrivo
            self.ids.incoming_call_box.opacity = 0
            self.ids.incoming_call_box.disabled = True
            # Assicurati che il thread esista prima di provare a joinarlo
            if hasattr(self, 'thread') and self.thread.is_alive():
                 self.thread.join()


class AggiungiContatto(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.contatto = True

    def aggiungicontatto(self):
        nuovo_contatto = self.ids.contatto.text.strip()
        if nuovo_contatto:
            if not self.contatto:
                coda_manda_msg.put(user.crea_azione(comando="crea_gruppo", nome_gruppo=nuovo_contatto))

            chat_screen = self.manager.get_screen('chat')
            chat_screen.aggiungi_nuovo_contatto(nuovo_contatto)
            self.ids.contatto.text = ""
            self.manager.current = 'chat'

    def on_radio_select(self, instance, text):
        if instance.state == "down":
            if text == "Nuovo contatto":
                self.contatto = True
            else:
                self.contatto = False


class ChatApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(SigninScreen(name='signin'))
        sm.add_widget(ChatScreen(name='chat'))
        sm.add_widget(AggiungiContatto(name='aggiungicontatto'))
        return sm


if __name__ == '__main__':

    def ricevi_messaggi():
        while True:
            try:
                data = s.recv(4096)
                print(f"Dato ricevuto: {data}")
                if data:
                    try:
                        messaggio = json.loads(data.decode())
                        Clock.schedule_once(lambda dt: processa_messaggio(messaggio))
                    except json.JSONDecodeError:
                        pass
            except (OSError, ConnectionResetError):
                pass


    def processa_messaggio(messaggio):
        chat_screen = App.get_running_app().root.get_screen('chat')
        if "comando" in messaggio and messaggio["comando"] in ["nuovo_messaggio_privato", "nuovo_messaggio_gruppo"]:
            if "ftp" in messaggio:
                chat_screen.receive_file(messaggio)
            else:
                chat_screen.receive_message(messaggio)

        elif "comando" in messaggio and messaggio["comando"] in ["richiesta_chiamata", "chiamata", "chiamata_accettata", "chiamata_rifiutata"]:
            chat_screen.receive_call(messaggio)
        else:
            print(f"Comando non gestito: {messaggio['comando']}")

    def manda_messaggi():
        while True:
            messaggio = coda_manda_msg.get()
            print(f"Dato manda a {server}: {messaggio}")
            if messaggio is None:
                print("Attenzione: messaggio None ricevuto nella coda")
                continue

            try:
                if not isinstance(messaggio, dict):
                    print(f"Attenzione: messaggio non valido nella coda: {type(messaggio)}")
                    continue
                else:
                    s.sendall(json.dumps(messaggio).encode("utf-8"))
            except Exception as e:
                print(f"Errore nell'invio del messaggio: {e}")

    cartella_destinazione = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_ricevuti")
    os.makedirs(cartella_destinazione, exist_ok=True)
    os.makedirs("datiChat", exist_ok=True)
    os.makedirs("datiGruppi", exist_ok=True)

    ChatApp().run()
