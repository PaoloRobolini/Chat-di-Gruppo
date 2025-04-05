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
def handle_client(socket, client_address):
    print(f"[+] Connessione da {client_address}")

    while True:
        try:
            data = socket.recv(1024).decode()
            if not data:
                break

            messaggio = {}
            try:
                messaggio = json.loads(data)
            except json.decoder.JSONDecodeError:
                messaggio = {}
                pass

            print(f"[{client_address}] ha inviato: {messaggio}")

            if messaggio["destinatario"] in client:

                dati_nuovi = {
                    "mittente": messaggio["mittente"],
                    "messaggio": messaggio["messaggio"],
                    "data": messaggio["data"]

                }

                socket.sendto(json.dumps(dati_nuovi).encode(), client.get(messaggio["destinatario"]))

                #cerco di salvare il messaggio boh
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

        except:
            break

    print(f"[-] Disconnessione da {client_address}")
    socket.close()

# Creazione del socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(server_address)

print(f"[SERVER] In ascolto su {server_address}...")

# Loop per accettare connessioni
while True:
    try:
        data, client_address = server_socket.recvfrom(1024)
        print(f"{client_address}")
        with lock_client:
            client[data.decode()] = client_address
        print(client)
    except ConnectionResetError:
        pass
    client_thread = threading.Thread(target=handle_client, args=(server_socket, client_address))
    client_thread.daemon = True
    client_thread.start()