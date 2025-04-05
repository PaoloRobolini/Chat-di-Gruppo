import json
import socket
import threading
import os

# Parametri server
HOST = '127.0.0.1'  # localhost
PORT = 18474

client = {
    "alice": "192.168.1.10",
    "bob": "192.168.1.20",
    "carlo": "192.168.1.30"
}


# Funzione per gestire ogni client connesso
def handle_client(client_socket, client_address):
    print(f"[+] Connessione da {client_address}")
    while True:
        try:
            message = client_socket.recv(1024)
            if not message:
                break

            messaggio = []
            data = message.decode()
            messaggio = data.split(";")

            print(f"[{client_address}] ha inviato: {data}")

            if len(messaggio) == 2:
                if not messaggio[0] in client:
                    client[messaggio[0]] = client_address
            elif messaggio[1] in client:
                ip_destinatario = client.get(messaggio[1])
                data.encode()
                data.sendall(ip_destinatario)
                #cerco di salvare il messaggio boh
                dati_file_nuovi = {
                    "mittente": messaggio[0],
                    "messaggio": messaggio[2],
                    "data_ora": messaggio[3]
                }
                nome_file = messaggio[0] + "_" + messaggio[1] + ".json"
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
                        json.dump(dati_file_nuovi, json_file, indent=4)


            else:
                print("destinatario non trovato")

        except:
            break

    print(f"[-] Disconnessione da {client_address}")
    client_socket.close()

# Creazione del socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()

print(f"[SERVER] In ascolto su {HOST}:{PORT}...")

# Loop per accettare connessioni
while True:
    client_socket, client_address = server_socket.accept()

    client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
    client_thread.start()
