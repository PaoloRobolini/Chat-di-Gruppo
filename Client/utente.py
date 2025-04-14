class utente:
    def __init__(self, mail="", password="", username=""):
        self.__username = username
        self.__mail = mail
        self.__password = password
        self.__destinatario = None

    def set_nome(self, nome):
        self.__username = nome

    def get_nome(self):
        return self.__username

    def set_destinatario(self, destinatario):
        self.__destinatario = destinatario

    def get_destinatario(self):
        return self.__destinatario

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



