class utente:
    def __init__(self, nome):
        self.__nome = nome

    def get_nome(self):
        return self.__nome

    def crea_messaggio(self, destinatario, messaggio):
        return self.__nome + ";" + destinatario + ";" + messaggio
