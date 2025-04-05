import json
import socket
import threading

import utente
nome_utente = input("Inserisci il tuo nome: ")
destinatario = input("Inserisci il destinatario: ")
utente = utente.utente(nome_utente)
server = ("127.0.0.1", 65432)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def stampa_messaggi_arrivati():
    while True:
        try:
            data = s.recvfrom(1024)
            if data is None:
                break

            try:
                messaggio = json.loads(data)
                print(messaggio)
            except json.decoder.JSONDecodeError:
                pass

        except ConnectionResetError:
            break




if __name__ == "__main__":
    stampa = threading.Thread(target=stampa_messaggi_arrivati)
    s.sendto(utente.get_nome().encode(), server)

    while True:
        messaggio = input(f"Inserisci un messaggio per {destinatario}: ")
        if messaggio == "exit":
            break

        messaggio = utente.crea_messaggio(destinatario, messaggio)
        s.sendto(messaggio.encode("utf-8"), server)
