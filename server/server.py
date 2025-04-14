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
HOST = "192.168.1.9"
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


def manda_gruppi_client(socket, username, client_address):
    gruppi_utente = []

    with lock_for_locks:
        try:
            with open("datiGruppi.json", 'r') as file:
                dati = json.load(file)
                gruppi_utente = [g["nome"] for g in dati["gruppi"] if username in g["membri"]]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Errore lettura gruppi: {str(e)}")
            gruppi_utente = []

    socket.sendto(str(len(gruppi_utente)).encode(), client_address)

    for nome_gruppo in gruppi_utente:
        file_name = f"{nome_gruppo}.json"  # Aggiunta estensione
        file_path = os.path.join("datiGruppi", file_name)

        with lock_for_locks:
            if nome_gruppo not in locks_chat:
                locks_chat[nome_gruppo] = threading.Lock()
            gruppo_lock = locks_chat[nome_gruppo]

        with gruppo_lock:
            try:
                # Invia il nome completo del file con estensione
                socket.sendto(file_name.encode(), client_address)
                print(f"Inviato: {file_name}")

                with open(file_path, 'r') as f:
                    dati_gruppo = json.load(f)
                    socket.sendto(json.dumps(dati_gruppo).encode(), client_address)

            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Errore gruppo {file_name}: {str(e)}")
                socket.sendto(json.dumps({"gruppo": []}).encode(), client_address)

# Modifica la funzione manda_chat_client
def manda_chat_client(socket, username, client_address):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    os.makedirs(cartella_chat, exist_ok=True)

    files_chat = [
            f for f in os.listdir(cartella_chat)
    ]

    file_da_mandare = []
    for file in files_chat:
        nome = file[:-5]
        nomi = nome.split('_')
        if username in nomi:
            file_da_mandare.append(file)


    socket.sendto(str(len(file_da_mandare)).encode(), client_address)

    for nome_file in file_da_mandare:
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
                ...




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
        manda_gruppi_client(socket, username_trovato, client_address)

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



    elif comando == "crea_gruppo":

        nome_gruppo = messaggio["nome_gruppo"]
        mittente = messaggio["mittente"]

        with lock_for_locks:
            with open("datiGruppi.json", 'r') as file:
                dati = json.load(file)
            aggiunto = any(g["nome"] == nome_gruppo for g in dati["gruppi"])

            if not aggiunto:
                dati["gruppi"].append({"nome": nome_gruppo, "membri": [mittente]})
            else:
                for g in dati["gruppi"]:
                    if g["nome"] == nome_gruppo and mittente not in g["membri"]:
                        g["membri"].append(mittente)

            with open("datiGruppi.json", 'w') as file:
                json.dump(dati, file, indent=4)

        file_gruppo = os.path.join("datiGruppi", f"{nome_gruppo}.json")

        with lock_for_locks:
            if nome_gruppo not in locks_chat:
                locks_chat[nome_gruppo] = threading.Lock()

            gruppo_lock = locks_chat[nome_gruppo]

        with gruppo_lock:

            if not os.path.exists(file_gruppo):
                with open(file_gruppo, 'w') as file:
                    json.dump({"gruppo": [{
                        "mittente": "Il gruppo",
                        "messaggio": "Gruppo creato",
                     }]}, file, indent=4)

    elif comando == "messaggio":

        gruppi_attivi = []

        with open("datiGruppi.json", 'r') as file:
            dati = json.load(file)

        for gruppo in dati["gruppi"]:
            if messaggio["destinatario"] == gruppo["nome"]:
                gruppi_attivi.append(gruppo)

        if messaggio["destinatario"] in gruppi_attivi:
            destinatario = messaggio["destinatario"]
            mittente = messaggio["mittente"]

            # 1. Lettura sicura della lista membri con lock
            with lock_for_locks:  # Lock globale per datiGruppi.json
                with open("datiGruppi.json", 'r') as file:
                    dati_gruppi = json.load(file)

                    for gruppo in dati_gruppi["gruppi"]:
                        if gruppo["nome"] == destinatario:
                            membri_gruppo = gruppo["membri"].copy()
                            break

            # 2. Invio messaggio ai membri
            with open('datiUtente.json', 'r') as file:
                dati_utenti = json.load(file)

            for utente in dati_utenti["utenti"]:
                if utente["username"] in membri_gruppo and utente["username"] != mittente:
                    try:
                        socket.sendto(json.dumps(messaggio).encode(), tuple(utente["address"]))

                    except Exception as e:
                        print(f"Errore invio a {utente['username']}: {str(e)}")

            # 3. Scrittura sicura nel file del gruppo con lock specifico
            file_gruppo = os.path.join("datiGruppi", f"{destinatario}.json")

            with lock_for_locks:  # Ottieni lock per questo gruppo

                if destinatario not in locks_chat:
                    locks_chat[destinatario] = threading.Lock()

                gruppo_lock = locks_chat[destinatario]

            with gruppo_lock:
                # Scrittura atomica con file temporaneo
                temp_path = ''

                try:
                    # Carica dati esistenti
                    if os.path.exists(file_gruppo):
                        with open(file_gruppo, 'r') as f:
                            dati = json.load(f)
                    else:
                        dati = {"gruppo": []}

                    # Aggiungi messaggio
                    dati["gruppo"].append({
                        "mittente": mittente,
                        "messaggio": messaggio["messaggio"]
                    })

                    # Scrittura atomica
                    with NamedTemporaryFile('w', dir="datiGruppi", delete=False, encoding='utf-8') as tmp:
                        temp_path = tmp.name
                        json.dump(dati, tmp, indent=4)
                        tmp.flush()
                    os.replace(temp_path, file_gruppo)

                except Exception as e:
                    ...
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)

        else:
            #Invio dei dati in una chat
            destinatario = messaggio["destinatario"]

            nuovo_messaggio = {
                "gruppo": False,
                "mittente": messaggio["mittente"],
                "destinatario": destinatario,
                "messaggio": messaggio["messaggio"]
            }

            with open('datiUtente.json', 'r') as file:
                dati = json.load(file)

            for utente in dati["utenti"]:
                if utente["username"] == destinatario:
                    socket.sendto(json.dumps(nuovo_messaggio).encode(), tuple(utente["address"]))

            #cerco di salvare su file parte
            salva_messaggio('datiChat', nuovo_messaggio)


    elif comando == "is_in_gruppo":
        with open("datiGruppi.json", 'r') as file:
            dati = json.load(file)

        for gruppo in dati["gruppi"]:
            if gruppo["nome"] == messaggio["nome_gruppo"] and messaggio["mittente"] in gruppo["membri"]:
                socket.sendto(b"yes", client_address)
                return

        socket.sendto(b"no", client_address)


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