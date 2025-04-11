import json
import multiprocessing
import socket
import threading
from multiprocessing import Queue

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty
from kivy.lang import Builder
from utente import utente

Builder.load_file("chat.kv")
server = ("26.21.230.217", 65432)
coda_arrivo_msg = multiprocessing.Queue()
coda_manda_msg = multiprocessing.Queue()

class LoginScreen(Screen, utente):
    def login(self):
        username = self.ids.username_input.text.strip()
        if username:
            utente.set_nome(self,username)
            chat_screen = self.manager.get_screen('chat')
            chat_screen.username = username
            self.manager.current = 'chat'


class ChatScreen(Screen, utente):
    username = StringProperty("")
    chat_history = StringProperty("")

    def send_message(self):
        message = self.ids.message_input.text.strip()
        if message:
            self.chat_history += f"\n{self.username} > {message}"
            self.ids.message_input.text = ""
            azione = utente.crea_azione(self,comando="messaggio", messaggio=message)
            coda_arrivo_msg.put(azione)

    def receive_message(self):
        ricevuto = coda_arrivo_msg.get(block=False, timeout=1)
        if ricevuto:
            self.chat_history += ricevuto


class ChatApp(App):
    def build(self):
        self.utente = utente()
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(ChatScreen(name='chat'))
        return sm


if __name__ == '__main__':

    def ricevi_messaggi():
        while True:
            try:
                # Riceve sia i dati che l'indirizzo del mittente
                data, addr = s.recvfrom(1024)
                messaggio = data.decode()

                # Decodifica e processa il messaggio
                try:
                    messaggio = json.loads(messaggio)
                    if "mittente" in messaggio:  # Verifica che sia un messaggio valido
                        coda_arrivo_msg.put(f"\nMessaggio da {messaggio['mittente']} > {messaggio['messaggio']}")

                except json.decoder.JSONDecodeError:
                    coda_arrivo_msg.put("Errore: messaggio non valido")

            except ConnectionResetError as e:
                coda_arrivo_msg.put(f"Errore nella ricezione: {e}")
                pass

    def manda_messaggi():
        while True:
            messaggio = coda_manda_msg.get()
            s.sendto(json.dumps(messaggio).encode(), server)


    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    thread_ricevi = threading.Thread(target=ricevi_messaggi, args=())
    thread_ricevi.start()

    ChatApp().run()