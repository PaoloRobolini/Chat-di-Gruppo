import time
from datetime import datetime


class utente:
    def __init__(self, mail="", password="", username=""):
        self.__username = username
        self.__mail = mail
        self.__password = password
        self.__destinatario = None
        self.__destinatario_chiamata = None
        self.__nome_file = None
        self.__pacchetto_audio = None

    def set_nome(self, nome):
        self.__username = nome

    def get_nome(self):
        return self.__username

    def get_password(self):
        return self.__password

    def set_destinatario(self, destinatario):
        self.__destinatario = destinatario

    def get_destinatario(self):
        return self.__destinatario

    def set_nome_file(self, nome_file):
        self.__nome_file = nome_file

    def get_nome_file(self):
        return self.__nome_file
    def set_pacchetto_audio(self, pacchetto_audio):
        self.__pacchetto_audio = pacchetto_audio
    def get_pacchetto_audio(self):
        return self.__pacchetto_audio

    def set_destinatario_chiamata(self, destinatario_chiamata):
        self.__destinatario_chiamata = destinatario_chiamata

    def get_destinatario_chiamata(self):
        return self.__destinatario_chiamata

    def crea_azione(self, **kwargs):
        comando = kwargs.get("comando")
        if comando == "login":  # si registra presso il server
            return {
                "comando": "login",
                "mail": self.__mail,
                "password": self.__password
            }
        elif comando == "signin":
            return {
                "comando": "signin",
                "username": self.__username,
                "mail": self.__mail,
                "password": self.__password
            }
        elif comando == "messaggio":  # crea un messaggio per l'utente
            if not self.__destinatario:
                print("Errore: destinatario non impostato")
                return None
            return {
                "comando": "messaggio",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "messaggio": kwargs["messaggio"],
                "orario": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
        elif comando == "crea_gruppo":  # crea un messaggio per un gruppo
            return {
                "comando": "crea_gruppo",
                "nome_gruppo": kwargs["nome_gruppo"],
                "mittente": self.__username
            }
        elif comando == "is_in_gruppo":
            return {
                "comando": "is_in_gruppo",
                "nome_gruppo": kwargs["nome_gruppo"],
                "mittente": self.__username
            }
        elif comando == "ftp_file_notification":  # notifica di trasferimento file completato via FTP
            if not self.__destinatario:
                print("Errore: destinatario non impostato per la notifica FTP")
                return None
            return {
                "comando": "ftp_file_notification",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "nome_file": kwargs.get("nome_file", self.__nome_file)
            }
        elif comando == "richiesta_chiamata":
            return {
                "comando": "richiesta_chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario
            }
        elif comando == "chiamata":
            return {
                "comando": "chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario_chiamata,
                "pacchetto_audio": self.__pacchetto_audio
            }
        elif comando == "chiamata_accettata":
            return {
                "comando": "chiamata_accettata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
            }
        elif comando == "chiamata_rifiutata":
            return {
                "comando": "chiamata_rifiutata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
            }
        elif comando == "chiamata_terminata":
            return {
                "comando": "chiamata_terminata",
                "mittente": self.__username,
                "destinatario": self.__destinatario_chiamata,
            }
        elif comando == "logout":
            return {
                "comando": "logout",
                "mittente": self.__username
            }
        else:
            print(f"Comando sconosciuto: {comando}")
            return {"comando": "sconosciuto"}