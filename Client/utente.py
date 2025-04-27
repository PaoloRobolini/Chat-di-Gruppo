class utente:
    def __init__(self, mail="", password="", username=""):
        self.__username = username
        self.__mail = mail
        self.__password = password
        self.__destinatario = None
        self.__nome_file = None
        self.__file = None
        self.__file_lenght = None
        self.__file_position = None
        self.__pacchetto_audio = None

    def set_nome(self, nome):
        self.__username = nome

    def get_nome(self):
        return self.__username

    def set_destinatario(self, destinatario):
        self.__destinatario = destinatario

    def get_destinatario(self):
        return self.__destinatario

    def set_nome_file(self, nome_file):
        self.__nome_file = nome_file

    def get_nome_file(self):
        return self.__nome_file

    def set_file(self, file):
        self.__file = file

    def get_file(self):
        return self.__file

    def set_file_lenght(self, file_lenght):
        self.__file_lenght = file_lenght

    def get_file_lenght(self):
        return self.__file_lenght

    def set_file_position(self, file_position):
        self.__file_position = file_position

    def get_file_position(self):
        return self.__file_position

    def set_pacchetto_audio(self, pacchetto_audio):
        self.__pacchetto_audio = pacchetto_audio

    def get_pacchetto_audio(self):
        return self.__pacchetto_audio

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
                "messaggio": kwargs["messaggio"]
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
        elif comando == "inizia_trasferimento_file":
            if not self.__destinatario:
                print("Errore: destinatario non impostato per iniziare trasferimento file")
                return None
            return {
                "comando": "inizia_trasferimento_file",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "nome_file": kwargs.get("nome_file", self.__nome_file),
                "file_size": kwargs.get("file_size", 0)
            }
        elif comando == "trasferimento_file_chunk":
            if not self.__destinatario:
                print("Errore: destinatario non impostato per inviare chunk")
                return None
            return {
                "comando": "trasferimento_file_chunk",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "nome_file": kwargs.get("nome_file", self.__nome_file),
                "chunk": kwargs.get("chunk"),
                "chunk_id": kwargs.get("chunk_id", 0),
                "total_chunks": kwargs.get("total_chunks", 1),
                "chunk_size": kwargs.get("chunk_size", 512),
                "file_size": kwargs.get("file_size", 0)
            }
        elif comando == "fine_trasferimento_file":
            if not self.__destinatario:
                print("Errore: destinatario non impostato per completare trasferimento")
                return None
            return {
                "comando": "fine_trasferimento_file",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "nome_file": kwargs.get("nome_file", self.__nome_file),
                "file_size": kwargs.get("file_size", 0)
            }
        elif comando == "chiamata":
            if not self.__destinatario:
                print("Errore: destinatario non impostato")
                return None
            return {
                "comando": "chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "pacchetto_audio": self.__pacchetto_audio
            }
        elif comando == "richiesta_chiamata":
            if not self.__destinatario:
                print("Errore: destinatario non impostato")
                return None
            return {
                "comando": "richiesta_chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
            }
        elif comando == "accetta_chiamata":
            return {
                "comando": "accetta_chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
            }
        elif comando == "rifiuta_chiamata":
            return {
                "comando": "rifiuta_chiamata",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
            }



        else:
            print(f"Comando sconosciuto: {comando}")
            return {"comando": "sconosciuto"}