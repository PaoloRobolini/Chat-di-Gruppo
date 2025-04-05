import json
import socket
import threading
import os
from sys import orig_argv

# Parametri server
HOST = '26.195.124.237'  # radmin PC BAOLO
PORT = 65432
server_address = (HOST, PORT)
lock_client = threading.Lock()
client = {
}


# Funzione per gestire ogni client connesso
def handle_client(socket, data, client_address):

    messaggio = data.decode()
    try:
        messaggio = json.loads(messaggio)
    except json.decoder.JSONDecodeError:
        messaggio = {}
        pass

    if messaggio["comando"] == "registrazione":
        with lock_client:
            client[messaggio["nome"]] = client_address
            print(client)

    elif messaggio["comando"] == "messaggio" and messaggio["destinatario"] in client:
        destination_address = client[messaggio["destinatario"]]
        print(f"[{client_address}] ha inviato: {messaggio} a {destination_address}")
        dati_nuovi = {
            "mittente": messaggio["mittente"],
            "messaggio": messaggio["messaggio"],

        }

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

print(f"[SERVER] In ascolto su {server_address}...")

# Loop per accettare connessioni
while True:
    data, client_address = server_socket.recvfrom(1024)
    print(f"[SERVER] {data}")
    print(f"[SERVER] {client_address}")
    if  data and client_address:
        client_thread = threading.Thread(target=handle_client, args=(server_socket, data, client_address))
        client_thread.daemon = True
        client_thread.start()