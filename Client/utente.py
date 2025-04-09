class utente:
    def __init__(self, nome):
        self.__nome = nome

    def get_nome(self):
        return self.__nome

    def crea_azione(self, comando, **kwargs):
        if comando == "messaggio":  #crea un messaggio per l'utente
            return {
                "comando": "messaggio",
                "mittente": self.__nome,
                "destinatario": kwargs["destinatario"],
                "messaggio": kwargs["messaggio"]
            }

        elif comando == "unisci_gruppo":  #crea un messaggio per un gruppo
            return {
                "comando": "unisci_gruppo",
                "nome_gruppo": kwargs["nome_gruppo"],
                "nome_utente": self.__nome
            }

        elif comando == "registrazione":  #si registra presso il server
            return {
                "comando": "registrazione",
                "nome": self.__nome,
            }
