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

    def set_file_lenght(self, file_lenght):
        self.__file_lenght = file_lenght

    def set_file_position(self, file_position):
        self.__file_position = file_position

    def crea_azione(self, **kwargs):
        comando = kwargs.get("comando")
        if comando == "login":  #si registra presso il server
            #print("Mi registro nel server")
            return {
                "comando": "login",
                "mail": self.__mail,
                "password": self.__password
            }
        #print(comando)
        elif comando == "signin":
            return {
                "comando": "signin",
                "username": self.__username,
                "mail": self.__mail,
                "password": self.__password
            }
        elif comando == "messaggio":  #crea un messaggio per l'utente
            #print(f"Invio un messaggio a {kwargs['destinatario']}")
            return {
                "comando": "messaggio",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "messaggio": kwargs["messaggio"]
            }

        elif comando == "crea_gruppo":  #crea un messaggio per un gruppo
            #print(f"Invio un messaggio a {kwargs['nome_gruppo']}")
            return {
                "comando": "crea_gruppo",
                "nome_gruppo": kwargs["nome_gruppo"],
                "mittente": self.__username
            }
        elif comando == "is_in_gruppo": return {
            "comando": "is_in_gruppo",
            "nome_gruppo": kwargs["nome_gruppo"],
            "mittente": self.__username
        }
        elif comando == "file":
            return {
                "comando": "file",
                "mittente": self.__username,
                "destinatario": self.__destinatario,
                "nome_file": self.__nome_file,
                "file": self.__file,
                "file_lenght": self.__file_lenght,
                "file_position": self.__file_position
            }




