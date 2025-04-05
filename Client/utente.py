class utente:
    def __init__(self, nome):
        self.__nome = nome

    def get_nome(self):
        return self.__nome

    def crea_messaggio(self, destinatario, messaggio):
        dizionario = {
            "comando" : "messaggio",
            "mittente": self.__nome,
            "destinatario": destinatario,
            "messaggio": messaggio
        }
        return dizionario

    def registrazione(self):
        dizionario = {
            "comando" : "registrazione",
            "nome" : self.__nome,
        }
        return dizionario
