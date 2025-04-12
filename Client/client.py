import json
import socket
import threading
import utente

nome_utente = input("Inserisci il tuo nome: ")
user = utente.utente(nome_utente)
server = ("26.21.230.217", 65432)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def menu_opzioni():
    opzioni_valide = {
        0 : "Esci dal programma",
        1 : "Registrati nel server",
        2 : "Invia un messaggio a una persona",
        3 : "Invia un messaggio a un gruppo"
    }
    stringa_input = "Inserisci una tra le seguenti opzioni:\n"

    for numero_opzione, opzione_valida in opzioni_valide.items():
        stringa_input += f"{numero_opzione}) {opzione_valida}" + "\n"

    try:
        opzione_utente = int(input(stringa_input))
        if opzione_utente < 0 or opzione_utente >= len(opzioni_valide):
            menu_opzioni()
        return opzione_utente
    except ValueError:
        menu_opzioni()


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
    s.sendto(json.dumps(user.crea_azione(comando="registrazione")).encode(), server)

    # Thread per la ricezione messaggi
    stampa = threading.Thread(target=stampa_messaggi_arrivati, daemon=True)
    stampa.start()

    # Ciclo principale per l'invio messaggi
    while True:
        opzione = menu_opzioni()
        operazione = {}
        match opzione:
            case 1:
                scegli_operazione = "registrazione"
            case 2:
                scegli_operazione = "messaggio"
                destinatario = input("Inserisci il destinatario: \n")
                messaggio = input(f"Cosa vuoi scrivere a {destinatario}? ")
                operazione["destinatario"] = destinatario
                operazione["messaggio"] = messaggio
            case 3:
                scegli_operazione = "unisci_gruppo"
                nome_gruppo = input("Inserisci il nome del gruppo: \n")
                operazione["nome_gruppo"] = nome_gruppo
            case 0:
                break
        operazione["comando"] = scegli_operazione
        azione = user.crea_azione(**operazione)
        s.sendto(json.dumps(azione).encode(), server)

    print("Disconnessione...")
    s.close()
