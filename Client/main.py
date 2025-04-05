import json
import socket
import threading

import utente
nome_utente = input("Inserisci il tuo nome: ")
utente = utente.utente(nome_utente)
server = ("26.195.124.237", 65432)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def stampa_messaggi_arrivati():
    while True:
        try:
            print("prima")
            data = s.recvfrom(1024)
            print("dopo")
            if not data:
                break

            try:
                messaggio = json.loads(data.decode())

            except json.decoder.JSONDecodeError:
                break

        except ConnectionResetError:
            break




if __name__ == "__main__":

    s.sendto(json.dumps(utente.registrazione()).encode(), server)
    destinatario = input("Inserisci il destinatario: ")
    stampa = threading.Thread(target=stampa_messaggi_arrivati)
    stampa.start()
    while True:
        messaggio = input(f"Inserisci un messaggio per {destinatario}: ")
        if messaggio == "exit":
            break

        messaggio = utente.crea_messaggio(destinatario, messaggio)
        s.sendto(json.dumps(messaggio).encode(), server)
