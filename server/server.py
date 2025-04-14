import json
import socket
import struct
import threading
import os
from sys import orig_argv
import string
import random
from tempfile import NamedTemporaryFile

# Parametri server
HOST = "10.4.54.27"
PORT = 65432
server_address = (HOST, PORT)
lock_datiUtente = threading.Lock()
clients = {}

def genera_nome_file(nome1, nome2):
    sorted_names = sorted([nome1, nome2])
    return f"{sorted_names[0]}_{sorted_names[1]}.json"


# Aggiungi queste variabili globali in cima al codice
lock_for_locks = threading.Lock()
locks_chat = {}
open_handles = {}


# Modifica la funzione salva_messaggio
def salva_messaggio(cartella_chat, nuovo_messaggio):
    if not {'mittente', 'messaggio', 'destinatario'}.issubset(nuovo_messaggio):
        raise ValueError("Messaggio non valido")

    nome_file = genera_nome_file(nuovo_messaggio['mittente'], nuovo_messaggio['destinatario'])
    percorso = os.path.join(cartella_chat, nome_file)
    os.makedirs(cartella_chat, exist_ok=True)

    # Ottieni il lock specifico per questo file
    with lock_for_locks:
        if nome_file not in locks_chat:
            locks_chat[nome_file] = threading.Lock()
        file_lock = locks_chat[nome_file]

    with file_lock:
        try:
            # Carica i dati esistenti
            dati = {'chat': []}
            if os.path.exists(percorso):
                with open(percorso, 'r') as f:
                    try:
                        dati = json.load(f)
                        if not isinstance(dati.get('chat'), list):
                            raise ValueError("Formato file non valido")
                    except json.JSONDecodeError:
                        os.remove(percorso)
                        dati = {'chat': []}

            # Aggiungi nuovo messaggio
            dati['chat'].append({
                'mittente': nuovo_messaggio['mittente'].strip(),
                'messaggio': nuovo_messaggio['messaggio'].strip()
            })

            # Scrittura atomica con gestione esplicita degli handle
            temp_path = ''
            try:
                with NamedTemporaryFile('w', dir=cartella_chat, delete=False, encoding='utf-8') as tmp:
                    temp_path = tmp.name
                    json.dump(dati, tmp, indent=4)
                    tmp.flush()  # Forza lo svuotamento del buffer

                # Sostituzione atomica del file
                os.replace(temp_path, percorso)

            except Exception as e:
                print(f"Errore durante il salvataggio: {e}")
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                raise

        except Exception as e:
            print(f"Errore critico durante il salvataggio: {e}")

    # Pulizia periodica dei lock (opzionale)
    with lock_for_locks:
        if nome_file not in open_handles:
            del locks_chat[nome_file]


# Modifica la funzione manda_chat_client
def manda_chat_client(socket, username, client_address):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    os.makedirs(cartella_chat, exist_ok=True)

    files_chat = [
        f for f in os.listdir(cartella_chat)
        if os.path.isfile(os.path.join(cartella_chat, f)) and username in f
    ]

    socket.sendto(str(len(files_chat)).encode(), client_address)

    for nome_file in files_chat:
        file_path = os.path.join(cartella_chat, nome_file)

        # Ottieni il lock per questo file
        with lock_for_locks:
            if nome_file not in locks_chat:
                locks_chat[nome_file] = threading.Lock()
            file_lock = locks_chat[nome_file]

        with file_lock:
            try:
                # Apri il file in modalità read con contest manager
                with open(file_path, 'r') as f:
                    dati = json.load(f)

                # Invia i dati
                socket.sendto(nome_file.encode(), client_address)
                socket.sendto(json.dumps(dati).encode(), client_address)
                print(f"Inviato: {nome_file}")

            except (json.JSONDecodeError, IOError) as e:
                print(f"Errore lettura {nome_file}: {str(e)}")
                continue


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
        manda_chat_client(socket, username_trovato, client_address)

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

        destinatario = messaggio["destinatario"]

        nuovo_messaggio = {
            "mittente": messaggio["mittente"],
            "destinatario": destinatario,
            "messaggio": messaggio["messaggio"]
        }

        with open('datiUtente.json', 'r') as file:
            dati = json.load(file)

        for utente in dati["utenti"]:
            if utente["username"] == destinatario:
                socket.sendto(json.dumps(nuovo_messaggio).encode(), tuple(utente["address"]))
                print("ho mandato i dati")

        #cerco di salvare su file parte
        salva_messaggio('datiChat', nuovo_messaggio)




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