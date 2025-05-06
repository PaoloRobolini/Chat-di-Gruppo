import base64
import json
import multiprocessing
import os
import socket
import threading
import time
from ftplib import FTP

import self
from kivy.clock import Clock, mainthread
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty
from kivy.lang import Builder
from utente import utente

from kivy.app import App
from kivy.uix.button import Button
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
                chat[file] = ""
                for message in dati['gruppo']:
                    chat[file] += f"\n{message['mittente']}> {message['messaggio']}"
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
                chat[altro_utente] = ""
                for message in dati['chat']:
                    chat[altro_utente] += f"\n{message['mittente']}> {message['messaggio']}"
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
    chat_history = StringProperty("")
    contact_buttons = ListProperty([])
    selected_contact = StringProperty("Seleziona un contatto")

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
            btn = Button(text=contact, size_hint=(None, None), size=(50, 50))
            btn.bind(on_press=self.on_contact_button_click)
            self.ids.contact_list_sidebar.add_widget(btn)

    def on_contact_button_click(self, instance):
        global user
        testo = instance.text
        user.set_destinatario(testo)
        self.selected_contact = f"Chat con {testo}"
        testo = testo.replace("'", '')
        try:
            self.chat_history = chat[testo]
        except KeyError:
            chat[testo] = ""

    def send_message(self):
        message = self.ids.message_input.text.strip()
        if message and user.get_destinatario() is not None:
            if not chat[user.get_destinatario()]:
                chat[user.get_destinatario()] = ''

            # Aggiunge il messaggio alla chat locale immediatamente
            chat[user.get_destinatario()] += f"\n{user.get_nome()}> {message}"
            self.chat_history = chat[user.get_destinatario()]
            self.ids.message_input.text = ""

            # Se il destinatario è l'AI, mostra l'indicatore di stato
            if user.get_destinatario() == "AI":
                self.show_ai_status(True)

            # Crea e invia il messaggio in modo asincrono
            azione = user.crea_azione(comando="messaggio", messaggio=message)
            coda_manda_msg.put(azione)

    def receive_message(self, messaggio):
        nuovo_messaggio = f"\n{messaggio['mittente']} > {messaggio['messaggio']}"

        if "nome_gruppo" in messaggio:
            mittente = messaggio["nome_gruppo"]
        else:
            mittente = messaggio["mittente"]

        if mittente not in self.contact_buttons:
            Clock.schedule_once(
                lambda dt: self.aggiungi_nuovo_contatto(mittente)
            )

        if mittente == user.get_destinatario():
            # Nasconde l'indicatore di stato se è una risposta dell'AI
            if mittente == "AI":
                self.show_ai_status(False)

            Clock.schedule_once(
                lambda dt: setattr(self, 'chat_history', self.chat_history + nuovo_messaggio)
            )

        Clock.schedule_once(
            lambda dt: self.salva_messaggio(mittente, nuovo_messaggio)
        )

    def aggiungicontatto(self):
        self.manager.current = 'aggiungicontatto'

    def aggiungi_nuovo_contatto(self, contatto):
        if contatto not in self.contact_buttons:
            self.contact_buttons.append(contatto)
            self.property('contact_buttons').dispatch(self)

    def salva_messaggio(self, mittente, messaggio):
        if mittente not in chat:
            chat[mittente] = ""
        chat[mittente] += messaggio

    def send_file(self, instance):
        root = Tk()
        root.withdraw()

        file_path = askopenfilename(title="scegli un file")

        if file_path:
            print(f"📤 File selezionato: {file_path}")
            nome_file_basename = os.path.basename(file_path)

            if user.get_destinatario() is None:
                print("Errore: destinatario non impostato per invio file")
                self.chat_history += "\n[Sistema] Errore: Seleziona un destinatario prima di inviare un file."
                root.destroy()
                return

            chat[user.get_destinatario()] += f"\n[Sistema] Iniziando invio file {nome_file_basename} via FTP..."
            self.chat_history = chat[user.get_destinatario()]

            try:
                # Connessione FTP con autenticazione
                ftp = FTP()
                ftp.connect(ip_server, ftp_port)
                ftp.login(user=user.get_nome(), passwd=user.get_password())

                # Usa la directory del mittente per salvare il file
                mittente_dir = user.get_nome()
                try:
                    ftp.cwd(mittente_dir)
                except:
                    try:
                        ftp.mkd(mittente_dir)
                        ftp.cwd(mittente_dir)
                    except Exception as e:
                        print(f"Errore nella creazione/accesso della directory {mittente_dir}: {e}")
                        return

                with open(file_path, 'rb') as file:
                    ftp.storbinary(f'STOR {nome_file_basename}', file,
                                   callback=lambda s: self.update_ftp_progress(s, nome_file_basename))

                ftp.quit()

                notifica = {
                    "comando": "ftp_file_notification",
                    "mittente": user.get_nome(),
                    "destinatario": user.get_destinatario(),
                    "nome_file": nome_file_basename
                }
                coda_manda_msg.put(notifica)

                chat[user.get_destinatario()] += f"\n[Sistema] File {nome_file_basename} inviato con successo via FTP!"
                self.chat_history = chat[user.get_destinatario()]

            except Exception as e:
                error_msg = f"\n[Sistema] Errore nell'invio del file via FTP: {str(e)}"
                chat[user.get_destinatario()] += error_msg
                self.chat_history = chat[user.get_destinatario()]
                print(f"Errore FTP dettagliato: {e}")

        root.destroy()

    def update_ftp_progress(self, block, nome_file):
        if user.get_destinatario() is not None:
            lines = chat[user.get_destinatario()].split("\n")
            if "[Progresso invio FTP]" in lines[-1]:
                lines[-1] = f"[Progresso invio FTP] Trasferimento di {nome_file} in corso..."
            else:
                lines.append(f"[Progresso invio FTP] Trasferimento di {nome_file} in corso...")
            chat[user.get_destinatario()] = "\n".join(lines)
            self.chat_history = chat[user.get_destinatario()]

    def receive_file(self, messaggio):
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")

        # Determina il mittente effettivo e il destinatario per il messaggio
        if comando == "nuovo_messaggio_gruppo":
            chat_id = messaggio.get("nome_gruppo")
        else:
            chat_id = mittente

        if comando in ["nuovo_messaggio_privato", "nuovo_messaggio_gruppo"] and "via FTP" in messaggio.get("messaggio",
                                                                                                           ""):
            if chat_id in chat:
                chat[chat_id] += f"\n{messaggio['messaggio']}"
                if chat_id == user.get_destinatario():
                    self.chat_history += f"\n{messaggio['messaggio']}"

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
                    return

                # Estrai il nome del file dal messaggio
                if "via FTP" in messaggio.get("messaggio", ""):
                    file_message = messaggio.get("messaggio", "")
                    start_index = file_message.find(": ") + 2
                    end_index = file_message.find(" (via FTP)")
                    if start_index > 1 and end_index > start_index:
                        nome_file = file_message[start_index:end_index]

                # Verifica se il file esiste
                files_disponibili = ftp.nlst()
                print(f"File disponibili: {files_disponibili}")
                if nome_file not in files_disponibili:
                    print(f"File {nome_file} non trovato nella directory")
                    return

                local_file_path = os.path.join(cartella_destinazione, nome_file)

                # Aggiunge un messaggio di progresso nella chat
                if chat_id in chat:
                    chat[chat_id] += f"\n[Sistema] Avvio download di {nome_file}..."
                    if chat_id == user.get_destinatario():
                        self.chat_history = chat[chat_id]

                with open(local_file_path, 'wb') as file:
                    def callback(chunk):
                        # Scrivi il chunk nel file
                        file.write(chunk)
                        # Aggiorna il progresso nella chat
                        if chat_id in chat and chat_id == user.get_destinatario():
                            lines = chat[chat_id].split("\n")
                            if "[Download in corso]" in lines[-1]:
                                lines[-1] = f"[Download in corso] Ricezione di {nome_file} in corso..."
                            else:
                                lines.append(f"[Download in corso] Ricezione di {nome_file} in corso...")
                            chat[chat_id] = "\n".join(lines)
                            self.chat_history = chat[user.get_destinatario()]

                    ftp.retrbinary(f'RETR {nome_file}', callback)

                ftp.quit()

                msg = f"\n[Sistema] File {nome_file} scaricato con successo in {cartella_destinazione}"
                if chat_id in chat:
                    chat[chat_id] += msg
                    if chat_id == user.get_destinatario():
                        self.chat_history += msg

            except Exception as e:
                error_msg = f"\n[Sistema] Errore nel download del file via FTP: {str(e)}"
                if chat_id in chat:
                    chat[chat_id] += error_msg
                    if chat_id == user.get_destinatario():
                        self.chat_history += error_msg
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
        stream_input.stop_stream()
        stream_input.close()

    def start_call(self):
        if user.get_destinatario() is not None:
            with self.lock:
                accettata = self.chiamata_accettata

            if accettata is None:
                azione = user.crea_azione(comando="richiesta_chiamata")
                coda_manda_msg.put(azione)
            elif accettata is True:
                user.set_destinatario_chiamata(user.get_destinatario())
                Clock.schedule_once(self.opacity1)
                Clock.schedule_once(self.updateFalse)
                # self.ids.caller_name = user.get_nome()
                self.thread_manda = threading.Thread(target=self.send_call)
                self.thread_manda.start()
                print("thread avviato")
            elif accettata is False:
                print("Chiamata rifiutata.")

    def get_call(self, pacchetto_audio2):
        if self.chiamata_accettata is True:
            print("dati chiamata mostrati")
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
        print("entro in receive call")
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")

        if comando == "richiesta_chiamata":
            Clock.schedule_once(self.opacity1)
            Clock.schedule_once(self.updateFalse)
            # self.ids.caller_name = mittente
            start_time = time.time()
            self.thread_accettazione = threading.Thread(target=self.accettazione_chiamata, args=(start_time,))
            self.thread_accettazione.start()

        elif comando == "chiamata_accettata":
            with self.lock:
                self.chiamata_accettata = True
                print("entro")
            self.start_call()
            print("in teoria avvio start call")

        elif comando == "chiamata_rifiutata":
            with self.lock:
                self.chiamata_accettata = False

        elif comando == "chiamata":
            print("chiamata")
            pacchetto_audio = messaggio.get("pacchetto_audio")
            user.set_destinatario_chiamata(mittente)
            self.thread_ricevi = threading.Thread(target=self.get_call, args=(pacchetto_audio,))
            self.thread_ricevi.start()

        elif comando == "chiamata_terminata":
            print("entro in chiamata terminata")
            with self.lock:
                self.chiamata_accettata = None
            self.thread_ricevi.join()
            self.thread_manda.join()
            Clock.schedule_once(self.opacity0)
            Clock.schedule_once(self.updateTrue)

    def accetta_chiamata(self):
        with self.lock:
            self.chiamata_accettata = True
        self.start_call()

    def rifiuta_chiamata(self):
        with self.lock:
            accettata = self.chiamata_accettata
        if accettata is True or None:
            with self.lock:
                self.chiamata_accettata = None
            azione = user.crea_azione(comando="chiamata_terminata")
            coda_manda_msg.put(azione)
            self.thread_ricevi.join()
            self.thread_manda.join()
            Clock.schedule_once(self.opacity0)
            Clock.schedule_once(self.updateTrue)
        elif accettata is False:
            azione = user.crea_azione(comando="chiamata_rifiutata")
            coda_manda_msg.put(azione)
            Clock.schedule_once(self.opacity0)
            Clock.schedule_once(self.updateTrue)
        '''elif accettata is None:
            self.chiamata_accettata = False
            azione = user.crea_azione(comando="chiamata_rifiutata")
            coda_manda_msg.put(azione)
            Clock.schedule_once(self.opacity0)
            Clock.schedule_once(self.updateTrue)'''

    @mainthread
    def opacity1(self, dt):
        self.ids.incoming_call_box.opacity = 1

    @mainthread
    def opacity0(self, dt):
        self.ids.incoming_call_box.opacity = 0

    @mainthread
    def updateFalse(self, dt):
        self.ids.incoming_call_box.disabled = False

    @mainthread
    def updateTrue(self, dt):
        self.ids.incoming_call_box.disabled = True


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
                data = s.recv(8192)
                print(f"Dato ricevuto: {data}")
                if data:
                    try:
                        print("nel try di ricezione")
                        messaggio = json.loads(data.decode())

                        if "comando" in messaggio:
                            if messaggio["comando"] in ["richiesta_chiamata", "chiamata_accettata",
                                                        "chiamata_rifiutata", "chiamata", "chiamata_terminata"]:
                                chat_screen = App.get_running_app().root.get_screen('chat')
                                chat_screen.receive_call(messaggio)
                            else:
                                Clock.schedule_once(lambda dt: processa_messaggio(messaggio))
                        print("in treoria ne sono anche uscito")
                    except json.JSONDecodeError:
                        pass
            except (OSError, ConnectionResetError):
                pass


    def processa_messaggio(messaggio):
        chat_screen = App.get_running_app().root.get_screen('chat')
        print("entro in processa_messaggio")

        if "comando" in messaggio:
            print("entro nel controllo del comando")
            if messaggio["comando"] in ["nuovo_messaggio_privato", "nuovo_messaggio_gruppo"]:
                if "via FTP" in messaggio.get("messaggio", ""):
                    chat_screen.receive_file(messaggio)
                else:
                    chat_screen.receive_message(messaggio)
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
                    print("conferma dell'invio")
                    s.sendall(json.dumps(messaggio).encode("utf-8"))
            except Exception as e:
                print(f"Errore nell'invio del messaggio: {e}")


    cartella_destinazione = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_ricevuti")
    os.makedirs(cartella_destinazione, exist_ok=True)
    os.makedirs("datiChat", exist_ok=True)
    os.makedirs("datiGruppi", exist_ok=True)

    ChatApp().run()