import base64
import json
import multiprocessing
import os
import socket
import threading
import time

from kivy.clock import Clock
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

porta_server = 65432
server = (ip_server, porta_server)

file_transfers_lock = threading.Lock()
file_transfers = {}

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(server)

coda_arrivo_msg = multiprocessing.Queue()
coda_manda_msg = multiprocessing.Queue()

chat = {}

global user

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


def scarica_chat(cartella):
    data = s.recv(4096)
    reply = data.decode()

    print(reply)

    os.makedirs(cartella, exist_ok=True)

    for _ in range(int(reply)):
        messaggio = s.recv(4096)
        print(messaggio)
        messaggio = json.loads(messaggio.decode())
        messaggio["nome"] = messaggio["nome"].replace('"', '').replace("'", "")

        print(f"Nome del file: {messaggio["nome"]}")
        with open(f"{cartella}/{messaggio["nome"]}", 'w') as f:
            json.dump(messaggio["contenuto"], f, indent=4)  # `indent=4` rende il file leggibile


class LoginScreen(Screen):
    def login(self):
        mail = self.ids.mail.text.strip()
        password = self.ids.password.text.strip()
        if mail and password:
            global user
            user = utente(mail=mail, password=password)

            dati_serializzati = json.dumps(user.crea_azione(comando="login")).encode('utf-8')
            s.sendall(dati_serializzati)


            data = s.recv(1024)
            reply = data.decode()

            if reply != "1":
                chat_screen = self.manager.get_screen('chat')
                chat_screen.username = reply
                self.manager.current = 'chat'
                reply = reply.replace('"', '')
                user.set_nome(reply)

                scarica_chat('datiChat')
                scarica_chat('datiGruppi')
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
            chat[user.get_destinatario()] += f"\n{user.get_nome()}> {message}"
            self.chat_history = chat[user.get_destinatario()]

            self.ids.message_input.text = ""
            azione = user.crea_azione(comando="messaggio", messaggio=message)
            coda_manda_msg.put(azione)



    def receive_message(self, messaggio):
        nuovo_messaggio = f"\n{messaggio['mittente']} > {messaggio['messaggio']}"

        if "nome_gruppo" in messaggio:
            mittente = messaggio["nome_gruppo"]
        else:
            mittente = messaggio["mittente"]

        # 1. Aggiornamento lista contatti in modo thread-safe
        if mittente not in self.contact_buttons:
            Clock.schedule_once(
                lambda dt: self.aggiungi_nuovo_contatto(mittente)
            )

        # 2. Aggiornamento cronologia chat solo se nella conversazione corretta
        if mittente == user.get_destinatario():
            Clock.schedule_once(
                lambda dt: setattr(self, 'chat_history', self.chat_history + nuovo_messaggio)
            )

        # 3. Salvataggio messaggio nella struttura dati
        Clock.schedule_once(
            lambda dt: self.salva_messaggio(mittente, nuovo_messaggio)
        )

    def aggiungicontatto(self):
        self.manager.current = 'aggiungicontatto'

    def aggiungi_nuovo_contatto(self, contatto):
        # Metodo wrapper per l'aggiunta thread-safe
        if contatto not in self.contact_buttons:
            self.contact_buttons.append(contatto)
            self.property('contact_buttons').dispatch(self)  # Forza notifica cambio

    def salva_messaggio(self, mittente, messaggio):
        # Salvataggio nella struttura dati principale
        if mittente not in chat:
            chat[mittente] = ""
        chat[mittente] += messaggio

    def send_file(self, instance):
        root = Tk()
        root.withdraw()

        # Apre il gestore file
        file_path = askopenfilename(title="scegli un file")

        if file_path:
            print(f"📤 File selezionato: {file_path}")
            nome_file_basename = os.path.basename(file_path)

            if user.get_destinatario() is None:
                print("Errore: destinatario non impostato per invio file")
                # Aggiorna la chat con un messaggio di errore
                self.chat_history += "\n[Sistema] Errore: Seleziona un destinatario prima di inviare un file."
                root.destroy()
                return

            # Aggiorna l'interfaccia per mostrare l'inizio del trasferimento
            chat[user.get_destinatario()] += f"\n[Sistema] Iniziando invio file {nome_file_basename}..."
            self.chat_history = chat[user.get_destinatario()]

            # Ottieni dimensione del file e calcola numero di chunk
            file_size = os.path.getsize(file_path)
            chunk_size = 2048  # Dimensione di ogni chunk in bytes
            total_chunks = (file_size + chunk_size - 1) // chunk_size  # Arrotonda per eccesso

            # Invio le informazioni di inizio trasferimento
            inizia_trasferimento = {
                "comando": "inizia_trasferimento_file",
                "mittente": user.get_nome(),
                "destinatario": user.get_destinatario(),
                "nome_file": nome_file_basename,
                "file_size": file_size
            }
            coda_manda_msg.put(inizia_trasferimento)

            # Leggi e invia i chunk del file
            with open(file_path, "rb") as file:
                for chunk_id in range(total_chunks):
                    # Posizionati all'inizio del chunk corrente
                    file.seek(chunk_id * chunk_size)
                    chunk_data = file.read(chunk_size)
                    if not chunk_data:  # Fine del file
                        break

                    # Converti il chunk in base64 per sicurezza nella trasmissione JSON
                    chunk_base64 = base64.b64encode(chunk_data).decode('utf-8')

                    # Crea un messaggio per ogni chunk
                    chunk_msg = {
                        "comando": "trasferimento_file_chunk",
                        "mittente": user.get_nome(),
                        "destinatario": user.get_destinatario(),
                        "nome_file": nome_file_basename,
                        "chunk": chunk_base64,
                        "chunk_id": chunk_id,
                        "total_chunks": total_chunks,
                        "chunk_size": len(chunk_data),
                        "file_size": file_size
                    }

                    # Invia il chunk
                    coda_manda_msg.put(chunk_msg)

                    # Aggiorna periodicamente la UI (ogni 10 chunk)
                    if chunk_id % 10 == 0 or chunk_id == total_chunks - 1:
                        progress = round(((chunk_id + 1) / total_chunks) * 100)
                        Clock.schedule_once(
                            lambda dt, prog=progress, tot=total_chunks, curr=chunk_id:
                            self.update_progress(prog, tot, curr), 0
                        )

                    # Piccola pausa per evitare sovraccarichi
                    time.sleep(0.05)

            # Notifica il server che il trasferimento è completo
            fine_trasferimento = {
                "comando": "fine_trasferimento_file",
                "mittente": user.get_nome(),
                "destinatario": user.get_destinatario(),
                "nome_file": nome_file_basename,
                "file_size": file_size
            }
            coda_manda_msg.put(fine_trasferimento)

            # Aggiorna la chat con notifica di completamento
            chat[user.get_destinatario()] += f"\n[Sistema] File {nome_file_basename} inviato con successo!"
            self.chat_history = chat[user.get_destinatario()]

            print(f"📤 Trasferimento file completato: {nome_file_basename}")

        # Chiude la finestra Tk
        root.destroy()

    def update_progress(self, progress, total_chunks, current_chunk):
        """Aggiorna la chat con l'avanzamento dell'invio file"""
        if user.get_destinatario() is not None:
            # Non vogliamo aggiornare la cronologia completamente, solo l'ultimo messaggio di progresso
            if "[Progresso" in chat[user.get_destinatario()].split("\n")[-1]:
                # Sostituisci l'ultimo messaggio con il nuovo stato di avanzamento
                lines = chat[user.get_destinatario()].split("\n")
                lines[-1] = f"[Progresso invio] Chunk {current_chunk + 1}/{total_chunks} ({progress}%)"
                chat[user.get_destinatario()] = "\n".join(lines)
            else:
                chat[
                    user.get_destinatario()] += f"\n[Progresso invio] Chunk {current_chunk + 1}/{total_chunks} ({progress}%)"

            self.chat_history = chat[user.get_destinatario()]

    def receive_file(self, messaggio):
        """Gestisce la ricezione di un file (o parte di esso)"""
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")
        nome_file = messaggio.get("nome_file")
        destinatario = messaggio.get("destinatario")

        cartella_destinazione = "file_ricevuti"

        if comando == "trasferimento_file_inizio":
            # Inizializzazione di un nuovo trasferimento file
            file_size = messaggio.get("file_size", "Sconosciuta")
            print(f"📥 Inizio ricezione file {nome_file} da {mittente} (dimensione: {file_size} bytes)")

            # Crea la cartella per i file ricevuti se non esiste
            os.makedirs(cartella_destinazione, exist_ok=True)

            # Aggiorna la chat con la notifica di inizio ricezione
            msg = f"\n[Sistema] Inizio ricezione file {nome_file} da {mittente} ({file_size} bytes)"
            if mittente in chat:
                chat[mittente] += msg
                if mittente == user.get_destinatario():
                    self.chat_history += msg

            # Apre e chiude il file per crearlo vuoto
            transfer_key = f"{mittente}_{destinatario}_{nome_file}_{file_size}"

            # Prepara la struttura per salvare il file sul server
            with file_transfers_lock:
                file_transfers[transfer_key] = {
                    "chunks": {},
                    "total_chunks": 0,
                    "completed": False,
                    "nome_file": nome_file,
                    "mittente": mittente,
                    "destinatario": destinatario,
                    "file_size": file_size
                }

        elif comando == "trasferimento_file_chunk":
            # Ricezione di un chunk del file
            chunk_id = messaggio.get("chunk_id")
            total_chunks = messaggio.get("total_chunks")
            chunk = messaggio.get("chunk")
            file_size = messaggio.get("file_size")

            try:
                # Chiave univoca per questo trasferimento
                transfer_key = f"{messaggio["mittente"]}_{messaggio["destinatario"]}_{nome_file}_{file_size}"

                # Salva il chunk nella struttura temporanea
                with file_transfers_lock:
                    if transfer_key in file_transfers:
                        file_transfers[transfer_key]["chunks"][chunk_id] = chunk
                        file_transfers[transfer_key]["total_chunks"] = total_chunks

                # Aggiorna l'interfaccia utente con lo stato di avanzamento
                if chunk_id % 10 == 0 or chunk_id == total_chunks - 1:
                    progress = round(((chunk_id + 1) / total_chunks) * 100)

                    # Aggiorna l'interfaccia solo se è il mittente attualmente selezionato
                    if mittente in chat and mittente == user.get_destinatario():
                        # Aggiorna in modo atomico per evitare messaggi duplicati
                        def update_ui():
                            # Trova l'ultimo messaggio di progresso o aggiungi uno nuovo
                            lines = self.chat_history.split("\n")
                            for i in range(len(lines) - 1, -1, -1):
                                if "[Ricezione]" in lines[i]:
                                    lines[i] = f"[Ricezione] Chunk {chunk_id + 1}/{total_chunks} ({progress}%)"
                                    self.chat_history = "\n".join(lines)
                                    return
                            # Se non trova un messaggio di progresso, aggiunge uno nuovo
                            self.chat_history += f"\n[Ricezione] Chunk {chunk_id + 1}/{total_chunks} ({progress}%)"

                        Clock.schedule_once(lambda dt: update_ui(), 0)
                        # Aggiorna anche lo stato nella struttura chat
                        chat[mittente] = self.chat_history

            except Exception as e:
                print(f"❌ Errore nella scrittura del chunk {chunk_id}: {e}")
                # Aggiungi una notifica di errore nella chat
                error_msg = f"\n[Errore] Problemi nella ricezione del chunk {chunk_id}: {str(e)}"
                if mittente in chat and mittente == user.get_destinatario():
                    self.chat_history += error_msg
                    chat[mittente] = self.chat_history

        elif comando == "trasferimento_file_fine":
            mittente = messaggio.get("mittente")
            destinatario = messaggio.get("destinatario")
            nome_file = messaggio.get("nome_file")
            file_size = messaggio.get("file_size")


            # Chiave univoca per questo trasferimento
            transfer_key = f"{mittente}_{destinatario}_{nome_file}_{file_size}"

            file_path = os.path.join("file_ricevuti", nome_file)

            with file_transfers_lock:
                if transfer_key in file_transfers:
                    # Ordina i chunk e scrivili su file
                    try:
                        with open(file_path, 'wb') as file_out:
                            for i in range(file_transfers[transfer_key]["total_chunks"]):
                                chunk_data = file_transfers[transfer_key]["chunks"].get(i)
                                if chunk_data:
                                    decoded_chunk = base64.b64decode(chunk_data)
                                    file_out.write(decoded_chunk)

                        file_transfers[transfer_key]["completed"] = True
                        print(f"File {nome_file} salvato con successo in {file_path}")


                    except Exception as e:
                        print(f"Errore nel salvataggio del file: {e}")

                    # Pulizia dopo il salvataggio
                    del file_transfers[transfer_key]

            if os.path.exists(file_path):
                print(f"✅ File completato: {nome_file}")
                # Verifica la dimensione finale
                file_size_ricevuto = os.path.getsize(file_path)
                file_size_atteso = messaggio.get("file_size", 0)

                # Messaggio di completamento con verifica della dimensione
                if file_size_atteso > 0 and file_size_ricevuto != file_size_atteso:
                    messaggio_notifica = f"\n[Attenzione] File ricevuto da {mittente}: {nome_file} (dimensione: {file_size_ricevuto}/{file_size_atteso} bytes - potrebbe essere corrotto)"
                else:
                    messaggio_notifica = f"\n[Sistema] File ricevuto da {mittente}: {nome_file} (salvato in {cartella_destinazione})"

                # Aggiorna la chat con la notifica di completamento
                if mittente in chat:
                    chat[mittente] += messaggio_notifica
                    if mittente == user.get_destinatario():
                        self.chat_history += messaggio_notifica
            else:
                print(f"❌ File non trovato dopo il trasferimento: {nome_file}")
                messaggio_notifica = f"\n[Errore] Impossibile trovare il file {nome_file} dopo il trasferimento"
                if mittente in chat and mittente == user.get_destinatario():
                    self.chat_history += messaggio_notifica
                    chat[mittente] = self.chat_history

    def start_call(self):
        if user.get_destinatario() is not None:
            self.chiamata_accettata = None
            if self.chiamata_accettata is None:
                azione = user.crea_azione(comando="richiesta_chiamata")
                coda_manda_msg.put(azione)
            elif self.chiamata_accettata == True:
                stream_input = p.open(format=FORMAT,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      frames_per_buffer=CHUNK)
                while True:
                    data = stream_input.read(CHUNK, exception_on_overflow=False)
                    user.set_pacchetto_audio(data)
                    azione = user.crea_azione(comando="chiamata")
                    coda_manda_msg.put(azione)

                    # Calcola energia del pacchetto audio
                    samples = struct.unpack('<' + ('h' * (len(data) // 2)), data)
                    energy = sum(abs(sample) for sample in samples) / len(samples)

                    if energy > SILENCE_THRESHOLD:
                        print("🎙️ Sto inviando audio... (energia:", int(energy), ")")
                    else:
                        print("😶 Silenzio mentre invio... (energia:", int(energy), ")")


    def receive_call(self, messaggio):
        self.button_pressed = None
        comando = messaggio.get("comando")
        mittente = messaggio.get("mittente")
        if comando == "richiesta_chiamata":
            self.ids.incoming_call_box.opacity = 1
            self.ids.incoming_call_box.disabled = False
            self.ids.caller_name = mittente
            start_time = time.time()
            while True:
                now = time.time()
                elapsed = now - start_time  # Quanto tempo è passato

                if elapsed > 5:  # Se sono passati più di 5 secondi
                    self.ids.incoming_call_box.opacity = 0
                    self.ids.incoming_call_box.disabled = True
                    break

                if self.button_pressed is True:
                    self.ids.incoming_call_box.opacity = 0
                    self.ids.incoming_call_box.disabled = True
                    break
                else:
                    self.ids.incoming_call_box.opacity = 0
                    self.ids.incoming_call_box.disabled = True
                    break

            if self.button_pressed is True:
                azione = user.crea_azione(comando="accetta_chiamata")
                coda_manda_msg.put(azione)
                self.start_call()
            else:
                azione = user.crea_azione(comando="rifiuta_chiamata")
                coda_manda_msg.put(azione)


        elif comando == "accetta_chiamata" or comando == "rifiuta_chiamata":
            if comando == "accetta_chiamata":
                self.chiamata_accettata = True
                self.start_call()
            elif comando == "rifiuta_chiamata":
                self.chiamata_accettata = False


        elif comando == "chiamata":
            while True:
                pacchetto_audio = "pacchetto_audio"
                stream_output.write(pacchetto_audio)

                # Calcola energia del pacchetto ricevuto
                samples = struct.unpack('<' + ('h' * (len(pacchetto_audio) // 2)), pacchetto_audio)
                energy = sum(abs(sample) for sample in samples) / len(samples)

                if energy > SILENCE_THRESHOLD:
                    print("🔊 Sto ricevendo audio... (energia:", int(energy), ")")
                else:
                    print("🛑 Ricevo silenzio... (energia:", int(energy), ")")








    def accetta_chiamata(self, instance):
        self.button_pressed = True

    def rifiuta_chiamata(self, instance):
        self.button_pressed = False





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
        if "comando" in messaggio:
            comando = messaggio["comando"]
            if comando.startswith("trasferimento_file"):
                chat_screen.receive_file(messaggio)
            elif comando in ["nuovo_messaggio_privato", "nuovo_messaggio_gruppo"]:
                chat_screen.receive_message(messaggio)
            elif comando in ["chiamata", "richiesta_chiamata", "accetta_chiamata", "rifiuta_chiamata"]:
                chat_screen.receive_call(messaggio)
            else:
                print(f"Comando non gestito: {comando}")
        else:
            print("Messaggio senza comando.")


    def manda_messaggi():
        while True:
            messaggio = coda_manda_msg.get()
            if messaggio is None:
                print("Attenzione: messaggio None ricevuto nella coda")
                continue  # Ignora questo messaggio e passa al prossimo

            try:
                if not isinstance(messaggio, dict):
                    print(f"Attenzione: messaggio non valido nella coda: {type(messaggio)}")
                    continue

                if "file" not in messaggio:
                    s.sendall(json.dumps(messaggio).encode())
                else:
                    s.sendall(json.dumps(messaggio).encode("utf-8") + b'\n')
            except Exception as e:
                print(f"Errore nell'invio del messaggio: {e}")


    cartella_destinazione = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_ricevuti")
    os.makedirs(cartella_destinazione, exist_ok=True)
    ChatApp().run()