import json
import socket
import struct
import threading
import os
from sys import orig_argv
import string
import random

# Parametri server
HOST = "26.21.230.217"
PORT = 65432
server_address = (HOST, PORT)
lock_datiUtente = threading.Lock()
clients = {}

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
    if comando == "login":
        print("sono entrato nel login")
        mail = messaggio["mail"]
        password = messaggio["password"]
        print("ho preso i dati")

        with open('datiUtente.json', 'r') as file:
            dati = json.load(file)

        username_trovato = None
        for utente in dati["utenti"]:
            if utente["email"] == mail and utente["password"] == password:
                username_trovato = utente["username"]

                break
        print("posso mandare i dati")
        if username_trovato:
            socket.sendto(json.dumps(username_trovato).encode(), client_address)
        else:
            socket.sendto(b"1", client_address)
        print("ho mandato i dati")

        #manda dati chat contatti e gruppi

        cartella = os.path.join(os.getcwd(), 'datiChat')

        conta = 0

        for nome_file in os.listdir(cartella):
            if os.path.isfile(os.path.join(cartella, nome_file)):
                if username_trovato in nome_file:
                    conta += 1


        data = str(conta)
        socket.sendto(data.encode(), client_address)

        for nome_file in os.listdir(cartella):
            if os.path.isfile(os.path.join(cartella, nome_file)):
                if username_trovato in nome_file:
                    print(nome_file)
                    with open("datiChat/" + nome_file, 'r') as file:
                        dati = json.load(file)
                        print("ho preso i dati del file")
                        socket.sendto(json.dumps(nome_file).encode(), client_address)
                        print("ho mandato il nome del file")
                        socket.sendto(json.dumps(dati).encode(), client_address)
                        print("ho mandato i dati del file")

        #aggiornamento ip e porta nel file datiutente
        with lock_datiUtente:
            with open('datiUtente.json', 'r') as file:
                dati = json.load(file)

        for utente in dati["utenti"]:
            if utente["email"] == mail:
                utente["address"] = tuple(client_address)

        with lock_datiUtente:
            with open('datiUtente.json', 'w') as file:
                json.dump(dati, file, indent=4)  # `indent=4` rende il file leggibile


    elif comando == "signin":
        username = messaggio["username"]
        mail = messaggio["mail"]
        password = messaggio["password"]

        reply = ""

        with lock_datiUtente:
            with open('datiUtente.json', 'r') as file:
                dati = json.load(file)

        for utente in dati["utenti"]:
            if utente["email"] == mail:
                reply = "1"

        if reply == "1":
            socket.sendto(reply.encode(), client_address)
        else:
            if "@" in mail:
                reply = "0"
                #salvataggio nuovo utente su file
                nuovo_utente = {
                    "email": mail,
                    "password": password,
                    "username": username,
                    "address": tuple(client_address),
                }
                dati["utenti"].append(nuovo_utente)

                with lock_datiUtente:
                    with open('datiUtente.json', 'w') as file:
                        json.dump(dati, file, indent=4)  # `indent=4` rende il file leggibile
            else:
                reply = "2"

        socket.sendto(reply.encode(), client_address)





    # Unione a un gruppo da parte di un client, in caso il gruppo non esiste viene creato
    elif comando == "unisci_gruppo":
        print("\n")
        if not messaggio["nome_gruppo"] in clients:
            clients[messaggio["nome_gruppo"]] = []
            print(f"creato il gruppo {messaggio['nome_gruppo']}")

        print(f"Si è unito al gruppo {messaggio['nome_gruppo']} {client_address}")
        clients[messaggio["nome_gruppo"]].append(client_address)

    # Inoltro di un messaggio a un altro client o gruppo




    elif comando == "messaggio":

        mittente = messaggio["mittente"]
        destinatario = messaggio["destinatario"]
        messaggio = messaggio["messaggio"]


        with open('datiUtente.json', 'r') as file:
            dati = json.load(file)

        for utente in dati["utenti"]:
            if utente["username"] == destinatario:
                ip = utente["address"]
                ip = tuple(ip)
                nuovo_messaggio = {
                    "mittente" : mittente,
                    "messaggio" : messaggio
                }
                socket.sendto(json.dumps(nuovo_messaggio).encode(), ip)
                print("ho mandato i dati")



        #cerco di salvare su file parte
        cartella = os.path.join(os.getcwd(), 'datiChat')

        for nome_file in os.listdir(cartella):
            if os.path.isfile(os.path.join(cartella, nome_file)):
                if mittente and destinatario in nome_file:
                    print(nome_file)
                    with open("datiChat/" + nome_file, 'r') as file:
                        dati = json.load(file)
                        nuovo_messaggio = {
                            "mittente": mittente,
                            "messsaggio": messaggio,
                        }
                        dati["chat"].append(nuovo_messaggio)
                        print("ho preso i dati da mettere nel file")

                        with open(nome_file, 'w') as file:
                            json.dump(dati, file, indent=4)  # `indent=4` rende il file leggibile
                        print("li ho messi nel file")


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
    try:
        data, client_address = server_socket.recvfrom(1024)
        print(f"[SERVER] {client_address}: {data.decode()}")
        if data and client_address:
            threading.Thread(target=handle_client, args=(server_socket, data, client_address)).start()
    except ConnectionResetError:
        continue