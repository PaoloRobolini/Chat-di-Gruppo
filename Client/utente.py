class utente:
    def __init__(self, nome):
        self.__nome = nome

    def get_nome(self):
        return self.__nome

    def crea_azione(self, **kwargs):
        comando = kwargs.get("comando")
        print(comando)
        if comando == "messaggio":  #crea un messaggio per l'utente
            print(f"Invio un messaggio a {kwargs['destinatario']}")
            return {
                "comando": "messaggio",
                "mittente": self.__nome,
                "destinatario": kwargs["destinatario"],
                "messaggio": kwargs["messaggio"]
            }

        elif comando == "unisci_gruppo":  #crea un messaggio per un gruppo
            print(f"Invio un messaggio a {kwargs['nome_gruppo']}")
            return {
                "comando": "unisci_gruppo",
                "nome_gruppo": kwargs["nome_gruppo"],
                "nome_utente": self.__nome
            }

        elif comando == "registrazione":  #si registra presso il server
            print("Mi registro nel server")
            return {
                "comando": "registrazione",
                "nome": self.__nome,
            }
