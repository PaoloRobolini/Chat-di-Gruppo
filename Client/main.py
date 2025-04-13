import json
import multiprocessing
import socket
import threading

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from utente import utente

Builder.load_file("chat.kv")
ip_server = "26.117.59.21"
porta_server = 65432
server = (ip_server, porta_server)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

coda_arrivo_msg = multiprocessing.Queue()
coda_manda_msg = multiprocessing.Queue()

chat = {}

global user

class LoginScreen(Screen):
    def login(self):
        mail = self.ids.mail.text.strip()
        password = self.ids.password.text.strip()
        if mail and password:
            global user
            user = utente(mail=mail, password=password)

            dati_serializzati = json.dumps(user.crea_azione(comando="login")).encode('utf-8')
            s.sendto(dati_serializzati, server)

            print("messaggio mandato")

            data, addr = s.recvfrom(1024)
            reply = data.decode()

            print(reply)

            if reply != "1":
                chat_screen = self.manager.get_screen('chat')
                chat_screen.username = reply
                self.manager.current = 'chat'
                reply = reply.replace('"', '')
                user.set_nome(reply)
            else:
                self.ids.login_data_error.text = "mail o password non corrispondono"
                self.ids.mail.text = ""
                self.ids.password.text = ""

            #ricezione chat
            data, addr = s.recvfrom(1024)
            reply = data.decode()

            print(reply)

            for _ in range(int(reply)):
                datachat, addr = s.recvfrom(1024)
                nome_file = datachat.decode()
                nome_file = nome_file.replace('"', '').replace("'", "")

                datachat, addr = s.recvfrom(1024)
                chat = datachat.decode()
                chat = json.loads(chat)

                with open("datiChat/" + nome_file, 'w') as file:
                    json.dump(chat, file, indent=4)  # `indent=4` rende il file leggibile

            thread_ricevi = threading.Thread(target=ricevi_messaggi)

            thread_ricevi.start()




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

            print("messaggio mandato")

            data, addr = s.recvfrom(1024)
            reply = data.decode()

            print(reply)

            if reply == "0":
                chat_screen = self.manager.get_screen('chat')
                chat_screen.username = username
                self.manager.current = 'chat'
                thread_ricevi = threading.Thread(target=ricevi_messaggi)
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

        self.chat_history = chat[testo]


    def send_message(self):
        message = self.ids.message_input.text.strip()
        if message:
            self.chat_history += f"\n{user.get_nome()} > {message}"
            self.ids.message_input.text = ""
            azione = user.crea_azione(comando="messaggio", messaggio=message)
            s.sendto(json.dumps(azione).encode(), server)


    def receive_message(self, messaggio):
        print("ho ricevuto un messaggio: " + messaggio)
        if not chat[messaggio['mittente']]:
            chat[messaggio['mittente']] = ''
        chat[messaggio['mittente']] += messaggio['messaggio']




    def aggiungicontatto(self):
        self.manager.current = 'aggiungicontatto'

    def aggiungi_nuovo_contatto(self, contatto):
        if contatto not in self.contact_buttons:
            self.contact_buttons.append(contatto)

class AggiungiContatto(Screen):
    def aggiungicontatto(self):
        nuovo_contatto = self.ids.contatto.text.strip()
        if nuovo_contatto:
            chat_screen = self.manager.get_screen('chat')
            chat_screen.aggiungi_nuovo_contatto(nuovo_contatto)
            self.ids.contatto.text = ""
            self.manager.current = 'chat'


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
                # Riceve sia i dati che l'indirizzo del mittente
                data, addr = s.recvfrom(1024)
                if data:
                    messaggio = data.decode()
                    print("messaggio: " + messaggio)

                    # Decodifica e processa il messaggio
                    try:
                        messaggio = json.loads(messaggio)
                        print(messaggio)
                        if "mittente" in messaggio:  # Verifica che sia un messaggio valido
                            print("c'e` il mittente")
                            coda_arrivo_msg.put(messaggio)
                            print(coda_arrivo_msg)

                            app = App.get_running_app()
                            chat_screen = app.root.get_screen('chat')
                            chat_screen.receive_message(messaggio)


                    except json.decoder.JSONDecodeError:
                        coda_arrivo_msg.put("Errore: messaggio non valido")
            except ConnectionResetError as e:
                coda_arrivo_msg.put(f"Errore nella ricezione: {e}")
                pass
            except OSError as e:
                pass


    def manda_messaggi():
        messaggio = coda_manda_msg.get()
        s.sendto(json.dumps(messaggio).encode(), server)




    ChatApp().run()