import json
import socket
import threading
import os
from sys import orig_argv

# Parametri server
HOST = "26.21.230.217"  # radmin PC BAOLO
PORT = 65432
server_address = (HOST, PORT)
lock_client = threading.Lock()
client = {}


# Funzione per gestire ogni client connesso
def handle_client(socket, data, client_address):

    messaggio = data.decode()
    try:
        messaggio = json.loads(messaggio)
    except json.decoder.JSONDecodeError:
        messaggio = {}
        pass

    comando = messaggio['comando']

    # Aggiunta di un nuovo client al dizionario client
    if comando == "registrazione" and messaggio["nome"] not in client:
        client[messaggio["nome"]] = client_address
        print(f"\nAggiunto {messaggio['nome']} ai client, indirizzo: {client_address}")


    # Unione ad un gruppo da parte di un client, in caso il gruppo non esiste viene creato
    elif comando == "unisci_gruppo":
        print("\n")
        if not messaggio["nome_gruppo"] in client:
            client[messaggio["nome_gruppo"]] = []
            print(f"creato il gruppo {messaggio['nome_gruppo']}")

        print(f"Si è unito al gruppo {messaggio['nome_gruppo']} {client_address}")
        client[messaggio["nome_gruppo"]].append(client_address)

    # Inoltro di un messaggio ad un altro client o gruppo
    elif comando == "messaggio" and messaggio["destinatario"] in client:

        destination_address = client[messaggio["destinatario"]]
        print(f"\nDestinazione del pacchatto: {destination_address}")
        dati_nuovi = {
            "mittente": messaggio["mittente"],
            "messaggio": messaggio["messaggio"],
        }
        #Invio dei messaggi ad un gruppo
        if type(destination_address) is list:

            for destinazione in destination_address:
                if destinazione != client_address:
                    print(f"[{client_address}] ha inviato: {dati_nuovi} a {destinazione}")
                    socket.sendto(json.dumps(dati_nuovi).encode(), destinazione)
        #Invio ad un singolo client
        else:
            print(f"[{client_address}] ha inviato: {dati_nuovi} a {destination_address}")
            socket.sendto(json.dumps(dati_nuovi).encode(), destination_address)



        # cerco di salvare il messaggio boh
        """nome_file = messaggio[0] + "_" + messaggio[1] + ".json"
        nome_file2 = messaggio[1] + "_" + messaggio[0] + ".json"
        if os.path.exists(nome_file):
            with open(nome_file, "r") as json_file:
                dati_file = json.load(json_file)
                dati_file.update(dati_file_nuovi)
            with open(nome_file, "w") as json_file:
                json.dump(dati_file, json_file, indent=4)
        elif os.path.exists(nome_file2):
            with open(nome_file2, "r") as json_file:
                dati_file = json.load(json_file)
                dati_file.update(dati_file_nuovi)
            with open(nome_file2, "w") as json_file:
                json.dump(dati_file, json_file, indent=4)
        else:
            with open(nome_file, "w") as json_file:
                json.dump(dati_file_nuovi, json_file, indent=4)"""


    else:
        print("destinatario non trovato")


# Creazione del socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(server_address)

print(f"[SERVER] In ascolto su {server_address}")

# Loop per accettare connessioni
while True:
    data, client_address = server_socket.recvfrom(1024)
    print(f"[SERVER] {client_address}: {data.decode()}")
    if  data and client_address:
        client_thread = threading.Thread(target=handle_client, args=(server_socket, data, client_address))
        client_thread.daemon = True
        client_thread.start()
