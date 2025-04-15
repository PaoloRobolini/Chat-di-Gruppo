import json
import multiprocessing
import os
import socket
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.button import Button
from utente import utente

Builder.load_file("chat.kv")
ip_server = "10.4.54.27"
porta_server = 65432
server = (ip_server, porta_server)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

coda_arrivo_msg = multiprocessing.Queue()
coda_manda_msg = multiprocessing.Queue()

chat = {}

global user

def carica_gruppi():
    files_chat = [
        f for f in os.listdir('datiGruppi')
    ]

    for file in files_chat:
        s.sendto(json.dumps(user.crea_azione(comando="is_in_gruppo", nome_gruppo=file[:-5])).encode(), server)
        data, address = s.recvfrom(1024)
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
    data, addr = s.recvfrom(1024)
    reply = data.decode()

    os.makedirs(cartella, exist_ok=True)

    for _ in range(int(reply)):
        datachat, addr = s.recvfrom(1024)
        nome_file = datachat.decode()
        nome_file = nome_file.replace('"', '').replace("'", "")

        datachat, addr = s.recvfrom(1024)
        chat = datachat.decode()
        chat = json.loads(chat)
        with open(f"{cartella}/{nome_file}", 'w') as file:
            json.dump(chat, file, indent=4)  # `indent=4` rende il file leggibile

class LoginScreen(Screen):
    def login(self):
        mail = self.ids.mail.text.strip()
        password = self.ids.password.text.strip()
        if mail and password:
            global user
            user = utente(mail=mail, password=password)

            dati_serializzati = json.dumps(user.crea_azione(comando="login")).encode('utf-8')
            s.sendto(dati_serializzati, server)

            data, addr = s.recvfrom(1024)
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
            s.sendto(dati_serializzati, server)

            data, addr = s.recvfrom(1024)
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
        if message:
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
                data, addr = s.recvfrom(1024)
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
        chat_screen.receive_message(messaggio)


    def manda_messaggi():
        while True:
            messaggio = coda_manda_msg.get()
            s.sendto(json.dumps(messaggio).encode(), server)

    ChatApp().run()