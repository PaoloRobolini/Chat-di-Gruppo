class utente:
    def __init__(self, nome):
        self.__nome = nome

    def getNome(self):
        return self.__nome

    def creaMessaggio(self, destinatario, messaggio):
        return self.__nome + ";" + destinatario + ";" + messaggio
