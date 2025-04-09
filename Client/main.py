import json
import socket
import threading
import utente

nome_utente = input("Inserisci il tuo nome: ")
utente = utente.utente(nome_utente)
server = ("10.4.54.27", 65432)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def stampa_messaggi_arrivati():
    while True:
        try:
            # Riceve sia i dati che l'indirizzo del mittente
            data, addr = s.recvfrom(1024)
            messaggio = data.decode()

            # Decodifica e processa il messaggio
            try:
                messaggio = json.loads(messaggio)
                if "mittente" in messaggio:  # Verifica che sia un messaggio valido
                    print(f"\nMessaggio da {messaggio['mittente']} > {messaggio['messaggio']}")

            except json.decoder.JSONDecodeError:
                print("Ricevuto messaggio non valido")

        except ConnectionResetError as e:
            print(f"Errore nella ricezione: {e}")
            pass


if __name__ == "__main__":
    # Registrazione iniziale
    s.sendto(json.dumps(utente.crea_azione(comando="registrazione")).encode(), server)

    # Thread per la ricezione messaggi
    stampa = threading.Thread(target=stampa_messaggi_arrivati, daemon=True)
    stampa.start()

    # Ciclo principale per l'invio messaggi
    while True:
        destinatario = input("Inserisci il destinatario (o 'exit' per uscire): ")
        if destinatario.lower() == 'exit':
            break

        testo = input(f"Inserisci un messaggio per {destinatario}: ")
        messaggio = utente.crea_azione("unisci_gruppo", nome_gruppo=destinatario, messaggio=testo)
        s.sendto(json.dumps(messaggio).encode(), server)

    print("Disconnessione...")
    s.close()
