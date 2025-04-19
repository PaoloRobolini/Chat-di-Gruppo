import json
import socket
import threading
import os
from tempfile import NamedTemporaryFile

# Parametri server

HOST = "127.0.0.1"

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


def manda_gruppi_client(client_socket, username):

    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
    os.makedirs(cartella_chat, exist_ok=True)

    with lock_for_locks:
        try:
            with open("datiGruppi.json", 'r') as file:
                dati = json.load(file)
                gruppi_utente = [g["nome"] for g in dati["gruppi"] if username in g["membri"]]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Errore lettura gruppi: {str(e)}")
            gruppi_utente = []

    client_socket.sendall(str(len(gruppi_utente)).encode())

    for nome_gruppo in gruppi_utente:
        file_name = f"{nome_gruppo}.json"  # Aggiunta estensione
        messaggio = {
            "nome": file_name,
        }

        with lock_for_locks:
            if nome_gruppo not in locks_chat:
                locks_chat[nome_gruppo] = threading.Lock()
            gruppo_lock = locks_chat[nome_gruppo]

        with gruppo_lock:
            with open(f"datiGruppi/{nome_gruppo}.json", 'r') as f:
                dati_gruppo = json.load(f)

        messaggio["contenuto"] = dati_gruppo
        client_socket.sendall(json.dumps(messaggio).encode())

# Modifica la funzione manda_chat_client
def manda_chat_client(client_socket, username):
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


    client_socket.sendall(str(len(file_da_mandare)).encode())

    for nome_file in file_da_mandare:
        file_path = os.path.join(cartella_chat, nome_file)
        messaggio = {
            "nome": nome_file
        }

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
                messaggio['contenuto'] = dati
                client_socket.sendall(json.dumps(messaggio).encode())
                print(f"Inviato: {nome_file}")

            except (json.JSONDecodeError, IOError) as e:
                print(f"Errore lettura {nome_file}: {str(e)}")
                ...




# Funzione per gestire ogni client connesso
def handle_client(client_socket, client_address):
    print(f"Nuova connessione da {client_address}")
    while True:
        
        try:
            data = client_socket.recv(1024)
        except ConnectionResetError:
            break
        
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

            with open('datiUtente.json', 'r') as file:
                dati = json.load(file)

            username_trovato = None
            for utente in dati["utenti"]:
                if utente["email"] == mail and utente["password"] == password:
                    username_trovato = utente["username"]

                    break
            if username_trovato:
                client_socket.sendall(json.dumps(username_trovato).encode())
                # manda dati chat contatti e gruppi


                # aggiornamento ip e porta nel file datiutente
                with lock_datiUtente:
                    with open('datiUtente.json', 'r') as file:
                        dati = json.load(file)

                for utente in dati["utenti"]:
                    if utente["email"] == mail:
                        utente["address"] = tuple(client_address)

                with lock_datiUtente:
                    with open('datiUtente.json', 'w') as file:
                        json.dump(dati, file, indent=4)  # `indent=4` rende il file leggibile

                manda_chat_client(client_socket, username_trovato)
                manda_gruppi_client(client_socket, username_trovato)

            else:
                client_socket.sendall(b"1")




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
                client_socket.sendall(reply.encode())
            else:
                if "@" in mail:
                    reply = "0"
                    # salvataggio nuovo utente su file
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

            client_socket.sendall(reply.encode())



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
                    gruppi_attivi.append(gruppo["nome"])

            if messaggio["destinatario"] in gruppi_attivi:
                destinatario = messaggio["destinatario"]
                mittente = messaggio["mittente"]

                nuovo_messaggio = {
                    "nome_gruppo ": destinatario,
                    "mittente": mittente,
                    "messaggio": messaggio["messaggio"]
                }

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
                            client_socket.sendall(json.dumps(nuovo_messaggio).encode(), tuple(utente["address"]))

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
                # Invio dei dati in una chat
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
                        try:
                            client_socket.sendall(json.dumps(nuovo_messaggio).encode(), tuple(utente["address"]))
                        except Exception:
                            pass

                # cerco di salvare su file parte
                salva_messaggio('datiChat', nuovo_messaggio)


        elif comando == "is_in_gruppo":
            with open("datiGruppi.json", 'r') as file:
                dati = json.load(file)

            for gruppo in dati["gruppi"]:
                if gruppo["nome"] == messaggio["nome_gruppo"] and messaggio["mittente"] in gruppo["membri"]:
                    client_socket.sendall(b"yes")
                    return

            client_socket.sendall(b"no")


        elif comando == "file":
            mittente = messaggio["mittente"]
            destinatario = messaggio["destinatario"]
            nome_file = messaggio['nome_file']
            file = messaggio['file']
            file_lenght = messaggio['file_lenght']
            file_position = messaggio['file_position']

            print(f"Ricevuto il nome del file: {nome_file}")
            cartella_destinazione = 'file_ricevuti'

            os.makedirs(cartella_destinazione, exist_ok=True)

            nuovo_pacchetto_file = {
                "mittente": mittente,
                "destinatario": destinatario,
                "nome_file": nome_file,
                "file": file,
                "file_lenght": file_lenght,
                "file_position": file_position
            }

            with open('datiUtente.json', 'r') as file:
                dati = json.load(file)

            for utente in dati["utenti"]:
                if utente["username"] == destinatario:
                    try:
                        client_socket.sendall(json.dumps(nuovo_pacchetto_file).encode(), tuple(utente["address"]))
                    except Exception:
                        pass

        else:
            print("destinatario non trovato")
    print(f"{client_address} si è disconnesso")
    client_socket.close()


# Creazione del socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(server_address)
server_socket.listen()

os.makedirs("datiChat", exist_ok=True)
os.makedirs("datiGruppi", exist_ok=True)

print(f"[SERVER] In ascolto su {server_address}")

# Loop per accettare connessioni
while True:
    try:
        client_socket,client_address = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, client_address)).start()
    except ConnectionResetError:
        continue