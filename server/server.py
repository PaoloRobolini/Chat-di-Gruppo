import json
import socket
import threading
import os
import time
from tempfile import NamedTemporaryFile
import google.generativeai as genai
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from soupsieve.util import lower
import datetime

HOST = "26.117.59.21"
PORT = 50000
FTP_PORT = 21
server_address = (HOST, PORT)

nome_AI = "AI"

lock_datiUtente = threading.Lock()
clients_sockets = {}
clients_lock = threading.Lock()
lock_for_locks = threading.Lock()
locks_chat = {}

user_ai_chats = {}
user_ai_chats_lock = threading.Lock()

# Variabili globali per l'authorizer FTP
ftp_authorizer = DummyAuthorizer()

with open("chiave.txt", "r") as file:
    chiave = file.read()

try:
    genai.configure(api_key=chiave)
except KeyError:
    print("Errore: Variabile d'ambiente GOOGLE_API_KEY non impostata.")
    print("Per favore, imposta la variabile d'ambiente con la tua chiave API.")
    exit()


def print_active_users():
    while True:
        with clients_lock:
            active_users = list(clients_sockets.keys())
        if active_users:
            print(f"Utenti attivi: {', '.join(active_users)}")
        else:
            print("Nessun utente attivo")
        time.sleep(30)

def genera_nome_file(nome1, nome2):
        sorted_names = sorted([nome1, nome2])
        return f"{sorted_names[0]}_{sorted_names[1]}.json"


def manda_messaggio(messaggio, mittente, destinatario):
    gruppo, membri = is_group(destinatario)
    with clients_lock:
        for membro in membri:
            if membro != mittente and membro in clients_sockets:
                clients_sockets[membro].sendall(json.dumps(messaggio).encode('utf-8'))

def is_group(destinatario):
    with lock_for_locks:
        with open("datiGruppi.json", 'r', encoding='utf-8') as file:
            dati_gruppi = json.load(file)
            for gruppo in dati_gruppi.get("gruppi", []):
                if gruppo.get("nome") == destinatario:
                    return True, gruppo["membri"]

    return False, [destinatario]


def salva_messaggio(cartella_chat, nuovo_messaggio):
    if not {'mittente', 'messaggio'}.issubset(nuovo_messaggio):
        raise ValueError("Messaggio non valido per il salvataggio")

    if 'destinatario' in nuovo_messaggio:
        nome_file = genera_nome_file(nuovo_messaggio['mittente'], nuovo_messaggio['destinatario'])
        chat_key = nome_file
        list_key = 'chat'
        message_data = {
            'mittente': nuovo_messaggio['mittente'].strip(),
            'messaggio': nuovo_messaggio['messaggio'].strip(),
            'orario': nuovo_messaggio['orario']
        }
    elif 'nome_gruppo' in nuovo_messaggio:
        nome_file = f"{nuovo_messaggio['nome_gruppo']}.json"
        chat_key = nuovo_messaggio['nome_gruppo']
        list_key = 'gruppo'
        message_data = {
            'mittente': nuovo_messaggio['mittente'].strip(),
            'messaggio': nuovo_messaggio['messaggio'].strip(),
            'orario': nuovo_messaggio['orario']
        }
    else:
        return

    percorso = os.path.join(cartella_chat, nome_file)
    os.makedirs(cartella_chat, exist_ok=True)

    with lock_for_locks:
        if chat_key not in locks_chat:
            locks_chat[chat_key] = threading.Lock()
        file_lock = locks_chat[chat_key]

    with file_lock:
        dati = {list_key: []}
        if os.path.exists(percorso):
            try:
                with open(percorso, 'r', encoding='utf-8') as f:
                    dati = json.load(f)
                    if not isinstance(dati.get(list_key), list):
                        dati = {list_key: []}
            except (FileNotFoundError, json.JSONDecodeError):
                dati = {list_key: []}

        dati[list_key].append(message_data)

        temp_path = ''
        try:
            with NamedTemporaryFile('w', dir=cartella_chat, delete=False, encoding='utf-8') as tmp:
                temp_path = tmp.name
                json.dump(dati, tmp, indent=4)
                tmp.flush()
            os.replace(temp_path, percorso)
        except Exception:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise


def manda_gruppi_client( username):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
    os.makedirs(cartella_chat, exist_ok=True)
    gruppi_utente = []
    try:
        with lock_for_locks:
            with open("datiGruppi.json", 'r', encoding='utf-8') as file:
                dati = json.load(file)
                gruppi_utente = [g for g in dati.get("gruppi", []) if username in g.get("membri", [])]
    except (FileNotFoundError, json.JSONDecodeError):
        gruppi_utente = []

    # Crea una cartella temporanea per l'utente nel file_storage
    cartella_temp = os.path.join("file_storage", f"temp_{username}")
    os.makedirs(cartella_temp, exist_ok=True)

    # Copia i file nella cartella temporanea
    file_da_mandare = []
    for gruppo_info in gruppi_utente:
        nome_gruppo = gruppo_info["nome"]
        nome_file = f"{nome_gruppo}.json"
        file_path = os.path.join(cartella_chat, nome_file)
        file_temp_path = os.path.join(cartella_temp, nome_file)
        file_da_mandare.append(nome_file)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                contenuto = json.load(f)
            with open(file_temp_path, 'w', encoding='utf-8') as f:
                json.dump(contenuto, f, indent=4)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    return file_da_mandare


def manda_chat_client( username):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    os.makedirs(cartella_chat, exist_ok=True)
    file_da_mandare = []
    for file_name in os.listdir(cartella_chat):
        if file_name.endswith(".json"):
            chat_name_parts = file_name[:-5].split('_')
            if len(chat_name_parts) == 2 and username in chat_name_parts:
                file_da_mandare.append(file_name)

    # Crea una cartella temporanea per l'utente nel file_storage
    cartella_temp = os.path.join("file_storage", f"temp_{username}")
    os.makedirs(cartella_temp, exist_ok=True)

    # Copia i file nella cartella temporanea
    for nome_file in file_da_mandare:
        file_path = os.path.join(cartella_chat, nome_file)
        file_temp_path = os.path.join(cartella_temp, nome_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                contenuto = json.load(f)
            with open(file_temp_path, 'w', encoding='utf-8') as f:
                json.dump(contenuto, f, indent=4)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    return file_da_mandare


def login(messaggio):
    mail = messaggio.get("mail")
    password = messaggio.get("password")
    username_trovato = None
    with lock_datiUtente:
        try:
            with open('datiUtente.json', 'r', encoding='utf-8') as file:
                dati = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {"utenti": []}
    for utente in dati.get("utenti", []):
        if utente.get("email") == mail and utente.get("password") == password:
            username_trovato = utente.get("username")
            break
    if username_trovato:
        with clients_lock:
            clients_sockets[username_trovato] = client_socket
        client_socket.sendall(json.dumps(username_trovato).encode('utf-8'))

        chat = manda_chat_client( username_trovato)
        gruppi = manda_gruppi_client( username_trovato)
        # Invia direttamente le informazioni sui file
        dato_da_inviare = {
            "comando": "files_ready",
            "cartella": f"temp_{username_trovato}",
            "chat": chat,
            "gruppi": gruppi
        }
        print(f"File da mandare a {client_address}: {dato_da_inviare}")
        client_socket.sendall(json.dumps(dato_da_inviare).encode())
        with user_ai_chats_lock:
            if username_trovato not in user_ai_chats:
                # Inizializza una nuova sessione di chat AI per questo utente
                model = genai.GenerativeModel('gemini-2.0-flash')
                user_ai_chats[username_trovato] = model.start_chat()
        return username_trovato

    else:
        client_socket.sendall(b"1")

    return None


def signin(messaggio):
    username = messaggio.get("username")
    mail = messaggio.get("mail")
    password = messaggio.get("password")
    with lock_datiUtente:
        try:
            with open('datiUtente.json', 'r', encoding='utf-8') as file:
                dati = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {"utenti": []}
        if any(u.get("email") == mail for u in dati.get("utenti", [])):
            reply = "1"
        elif "@" not in mail:
            reply = "2"
        elif any(u.get("username") == username for u in dati.get("utenti", [])):
            reply = "3"
        else:
            reply = "0"
            nuovo_utente = {"email": mail, "password": password, "username": username}
            dati.setdefault("utenti", []).append(nuovo_utente)
            with open('datiUtente.json', 'w', encoding='utf-8') as file:
                json.dump(dati, file, indent=4)

            # Aggiungi l'utente al server FTP usando l'authorizer globale
            try:
                ftp_authorizer.add_user(username, password, os.path.join(os.getcwd(), "file_storage"),
                                    perm="elradfmw")
                print(f"Utente {username} aggiunto al server FTP")
            except Exception as e:
                print(f"Errore nell'aggiunta dell'utente al server FTP: {e}")

            with user_ai_chats_lock:
                if username not in user_ai_chats:
                    # Inizializza una nuova sessione di chat AI per questo utente
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    user_ai_chats[username] = model.start_chat()
    client_socket.sendall(reply.encode('utf-8'))
    return username

def crea_gruppo(messaggio):

    nome_gruppo = messaggio.get("nome_gruppo")
    mittente = messaggio.get("mittente")

    gruppo_aggiunto_esistente = False
    with lock_for_locks:
        try:
            with open("datiGruppi.json", 'r', encoding='utf-8') as file:
                dati = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {"gruppi": []}
        gruppo_esistente = next((g for g in dati.get("gruppi", []) if g.get("nome") == nome_gruppo), None)
        if gruppo_esistente:
            gruppo_aggiunto_esistente = True
            if mittente not in gruppo_esistente.get("membri", []):
                gruppo_esistente.setdefault("membri", []).append(mittente)
        else:
            nuovo_gruppo = {"nome": nome_gruppo, "membri": [mittente]}
            dati.setdefault("gruppi", []).append(nuovo_gruppo)
        with open("datiGruppi.json", 'w', encoding='utf-8') as file:
            json.dump(dati, file, indent=4)
    file_gruppo_path = os.path.join("datiGruppi", f"{nome_gruppo}.json")
    with lock_for_locks:
        if nome_gruppo not in locks_chat:
            locks_chat[nome_gruppo] = threading.Lock()
        gruppo_lock = locks_chat[nome_gruppo]
    if not gruppo_aggiunto_esistente:
        with gruppo_lock:
            if not os.path.exists(file_gruppo_path):
                with open(file_gruppo_path, 'w', encoding='utf-8') as file:
                    json.dump({"gruppo": [{"mittente": "Il gruppo",
                                           "messaggio": f"Il gruppo '{nome_gruppo}' è stato creato.", }]},
                              file, indent=4)
    client_socket.sendall(b"Gruppo creato o aggiunto con successo")

def prepara_chat_AI(username, nome_utente):
    nome_file = genera_nome_file(username, nome_utente)

    storico = []
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))

    if nome_file in os.listdir(cartella_chat):
        with open(os.path.join('datiChat', nome_file), 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        for msg in chat_data.get("chat", []):
            storico.append(f"{msg['mittente']}: {msg['messaggio']} il {msg['orario']}")
        return f"Chat privata con '{nome_utente}'", storico

    else:
        return f"Il contatto '{nome_utente}' non esiste"

def gestisci_carica_chat(chat, username, nome_utente):

    if nome_utente == "tutti":
        all_chats = []
        cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
        for file_name in os.listdir(cartella_chat):
            if file_name.endswith(".json"):
                chat_name_parts = file_name[:-5].split('_')
                if username in chat_name_parts:
                    other_user = chat_name_parts[0] if chat_name_parts[1] == username else chat_name_parts[1]
                    try:
                        with open(os.path.join(cartella_chat, file_name), 'r', encoding='utf-8') as f:
                            chat_data = json.load(f)
                            messages = []
                            for msg in chat_data.get("chat", []):
                                messages.append(f"{msg['mittente']}: {msg['messaggio']} il {msg['orario']}")
                            if messages:
                                chat_context = f"\nChat con {other_user}:\n" + "\n".join(messages)
                                all_chats.append(chat_context)
                    except (FileNotFoundError, json.JSONDecodeError):
                        continue

        if all_chats:
            return chat.send_message("Ecco tutte le mie chat private:" + "\n".join(all_chats)).text
    else:
        storico = prepara_chat_AI(username, nome_utente)

        if type(storico) is str:
            return storico
        else:
            return chat.send_message(f"{storico[0]}:" + "\n".join(storico[1])).text

def prepara_gruppo_AI (username, nome_gruppo):
    storico = []

    with open("datiGruppi.json", 'r', encoding='utf-8') as file:
        gruppi = json.load(file)

    gruppi_utente = []
    gruppi = gruppi["gruppi"]
    for gruppo in gruppi:
        if username in gruppo["membri"]:
            gruppi_utente.append(gruppo["nome"])

    if nome_gruppo not in gruppi_utente:
        return f"Non appartieni a questo gruppo"

    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
    if f"{nome_gruppo}.json" in os.listdir(cartella_chat):
        with open(os.path.join('datiGruppi', f"{nome_gruppo}.json"), 'r', encoding='utf-8') as f:
            chat_data = json.load(f)

        for msg in chat_data.get("gruppo", []):
            storico.append(f"{msg['mittente']}: {msg['messaggio']} il {msg['orario']}")
        return f"Gruppo '{nome_gruppo}'", storico

    else:
        return f"Il gruppo '{nome_gruppo}' non esiste"

def gestisci_carica_gruppo(chat, username, nome_gruppo):
    if nome_gruppo == "tutti":
        all_groups = []
        try:
            with lock_for_locks:
                with open("datiGruppi.json", 'r', encoding='utf-8') as file:
                    dati = json.load(file)
                    for gruppo in dati.get("gruppi", []):
                        if username in gruppo.get("membri", []):
                            nome_gruppo = gruppo["nome"]
                            file_gruppo_path = os.path.join("datiGruppi", f"{nome_gruppo}.json")
                            try:
                                with open(file_gruppo_path, 'r', encoding='utf-8') as f:
                                    gruppo_data = json.load(f)
                                    messages = []
                                    for msg in gruppo_data.get("gruppo", []):
                                        messages.append(f"{msg['mittente']}: {msg['messaggio']} il {msg['orario']}")
                                    if messages:
                                        group_context = f"\nGruppo {nome_gruppo}:\n" + "\n".join(messages)
                                        all_groups.append(group_context)
                            except (FileNotFoundError, json.JSONDecodeError):
                                continue
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        if all_groups:
            return str(chat.send_message("Ecco tutti i miei gruppi:" + "\n".join(all_groups)).text)
    else:
        storico = prepara_gruppo_AI(username, nome_gruppo)
        if type(storico) is str:
            return storico
        else:
            return chat.send_message(f"{storico[0]}:" + "\n".join(storico[1])).text


def verifica_nomi(username):
    # Selezione di tutte le chat
    all_chats = []
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    for file_name in os.listdir(cartella_chat):
        if file_name.endswith(".json"):
            chat_name_parts = file_name[:-5].split('_')
            if username in chat_name_parts:
                other_user = chat_name_parts[0] if chat_name_parts[1] == username else chat_name_parts[1]
                all_chats.append(other_user)

    # Selezione dei nomi di tutti i gruppi:
    with open("datiGruppi.json", 'r', encoding='utf-8') as file:
        gruppi = json.load(file)

    gruppi_utente = []
    gruppi = gruppi["gruppi"]
    for gruppo in gruppi:
        if username in gruppo["membri"]:
            gruppi_utente.append(gruppo["nome"])

    return {
        "gruppi": gruppi_utente,
        "chat": all_chats
    }

def ai(messaggio, username):
    #Salvataggio del messaggio dell'utente
    messaggio_salvataggio = {"mittente": username, "destinatario": nome_AI, "messaggio": messaggio.get("messaggio"), "orario": messaggio["orario"]}
    salva_messaggio('datiChat', messaggio_salvataggio)

    with user_ai_chats_lock:
        if username in user_ai_chats:
            chat = user_ai_chats[username]

    # Gestione comandi speciali
    msg = messaggio.get("messaggio")
    msg = msg.split(":")
    comando = lower(msg[0])
    risposta = ""

    if comando == "carica chat":
        nome_utente = msg[1].strip()
        chat.send_message("In questo caso ti caricherò direttamente le chat, quindi non devi rispondermi con il comando che ti ho insegnato, ma con tipo 'caricata chat con e la persona'")
        risposta = gestisci_carica_chat(chat, username, nome_utente)

    elif comando == "carica gruppo":
        nome_gruppo = msg[1].strip()
        chat.send_message("In questo caso ti caricherò direttamente i gruppi, quindi non devi rispondermi con il comando che ti ho insegnato, ma con tipo 'caricato gruppo con il nome del gruppo'")

        risposta = gestisci_carica_gruppo(chat, username, nome_gruppo)
    else:
        # Comportamento normale per altri messaggi
        risposta = str(chat.send_message(messaggio.get("messaggio")).text)
        risposta = risposta.strip()
        esci = False
        while not esci:
            print(f"risposta: '{risposta}'")
            if "Carica tutti" in risposta:
              gestisci_carica_chat(chat, username, "tutti")
              risposta = gestisci_carica_gruppo(chat, username, "tutti")
              esci = True

            elif risposta.startswith("Carica chat:") or risposta.startswith("Carica gruppo:"):
                risposta = risposta.split(":")
                comando = lower(risposta[0])
                nome = risposta[1].strip().replace("'", "")

                if comando == "carica chat":
                    risposta = gestisci_carica_chat(chat, username, nome)

                elif comando == "carica gruppo":
                    risposta = gestisci_carica_gruppo(chat, username, nome)

                esci = True

            elif "Verifica nomi" in risposta:
                nomi = verifica_nomi(username)
                risposta = str(chat.send_message(f"Questi sono tutti gli utenti con cui ho delle chat: {nomi['chat']} questi sono i gruppi a cui faccio parte: {nomi['gruppi']}").text)
            else:
                esci = True



    # Invio della risposta
    messaggio_da_inoltrare = {"comando": "nuovo_messaggio_privato", "mittente": nome_AI,
                              "messaggio": risposta, "orario": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

    manda_messaggio(messaggio_da_inoltrare, nome_AI, username)
    messaggio_salvataggio = {"mittente": nome_AI, "destinatario": username, "messaggio": risposta, "orario": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") }
    print(messaggio_salvataggio)
    salva_messaggio('datiChat', messaggio_salvataggio)


def inoltra_messaggio(messaggio, logged_in_username):

    mittente = logged_in_username
    destinatario = messaggio.get("destinatario")
    testo_messaggio = messaggio.get("messaggio")


    if destinatario == nome_AI:
        ai(messaggio, mittente)
    else:
        gruppo, membri = is_group(destinatario)

        if gruppo:
            messaggio_da_inoltrare = {"comando": "nuovo_messaggio_gruppo", "nome_gruppo": destinatario,
                                      "mittente": mittente, "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            nuovo_messaggio_salvataggio = {"nome_gruppo": destinatario, "mittente": mittente, "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            salva_messaggio('datiGruppi', nuovo_messaggio_salvataggio)
        else:
            messaggio_da_inoltrare = {"comando": "nuovo_messaggio_privato", "mittente": mittente,
                                      "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            nuovo_messaggio_salvataggio = {"mittente": mittente, "destinatario": destinatario, "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

        manda_messaggio(messaggio_da_inoltrare, mittente, destinatario)

def inoltra_chiamata(messaggio, logged_in_username):

    print("entro in ilk=noltyra chiamata")

    comando = messaggio.get("comando")
    mittente = messaggio.get("mittente")
    destinatario = messaggio.get("destinatario")
    pacchetto_audio = messaggio.get("pacchetto_audio")

    gruppo, membri = is_group(destinatario)

    if gruppo:
        messaggio_da_inoltrare = {"comando": comando, "nome_gruppo": destinatario,
                                  "mittente": mittente, "pacchetto_audio": pacchetto_audio}
    else:
        messaggio_da_inoltrare = {"comando": comando, "mittente": mittente,
                                  "pacchetto_audio": pacchetto_audio}

    manda_messaggio(messaggio_da_inoltrare, mittente, destinatario)

    print("esco da inoltra chiamata")


def is_in_gruppo(messaggio, logged_in_username):
    if not logged_in_username:
        client_socket.sendall(b"error_not_logged_in")
    nome_gruppo = messaggio.get("nome_gruppo")
    mittente = logged_in_username
    if not nome_gruppo:
        client_socket.sendall(b"error_missing_group_name")
    is_member = False
    with lock_for_locks:
        try:
            with open("datiGruppi.json", 'r', encoding='utf-8') as file:
                dati = json.load(file)
                for gruppo in dati.get("gruppi", []):
                    if gruppo.get("nome") == nome_gruppo and mittente in gruppo.get("membri", []):
                        is_member = True
                        break
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    if is_member:
        client_socket.sendall(b"yes")
    else:
        client_socket.sendall(b"no")

def setting_AI(username):
    with user_ai_chats_lock:
        if username in user_ai_chats:
            chat = user_ai_chats[username]

            chat.send_message(
                f"Succesivamente ti farò delle domande, rispondi come se io fossi {username}, io ti chiamerò {nome_AI} per semplicità"
                "In caso dovessi porti delle domande sui file non citarmi la sezione di quest'ultimo."
                "Il metodo per caricare le chat è: Carica chat: 'Nome della chat', per caricare un gruppo: Carica gruppo: 'Nome del gruppo',"
                "se volessi caricare tutte le chat o gruppi al posto del nome devo mettere la parola 'tutti'"
                "Se ti accorgi che ti manca una chat o un gruppo in particolare o tutte le chat o gruppi dopo una mia domanda rispondimi solamente con i comandi precedentemente insegnati, non aggiungere altri particolati,"
                "poi ti verrà caricato ciò che ti manca per rispondere alla mia domanda,"
                "Se tu volessi verificare i nomi delle chat o gruppi a cui appattengo prima di lanciare il comando per caricare una chat specifica o gruppo usa il comando 'Verifica nomi', per non inserire il nome errato per magari delle maiuscole scambiate per minuscole o viceversa,"
                "o solamente per sapere queli sono le mie chat o i gruppi a cui appartengo"
            )

def setup_ftp_server():
    # Usa l'authorizer globale
    global ftp_authorizer

    # Leggi gli utenti registrati e aggiungili come utenti FTP
    try:
        with open('datiUtente.json', 'r', encoding='utf-8') as file:
            dati = json.load(file)
            for utente in dati.get("utenti", []):
                username = utente.get("username")
                password = utente.get("password")
                # Aggiungi l'utente con accesso alla cartella file_storage
                ftp_authorizer.add_user(username, password, os.path.join(os.getcwd(), "file_storage"),
                                    perm="elradfmw")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Errore nel caricamento degli utenti FTP: {e}")

    # Crea l'handler FTP
    handler = FTPHandler
    handler.authorizer = ftp_authorizer

    # Crea il server FTP
    ftp_server = FTPServer((HOST, FTP_PORT), handler)

    # Avvia il server FTP in un thread separato
    ftp_thread = threading.Thread(target=ftp_server.serve_forever)
    ftp_thread.daemon = True
    ftp_thread.start()

    print(f"[FTP SERVER] In ascolto su {HOST}:{FTP_PORT}")


def handle_client(client_socket, client_address):
    logged_in_username = None
    print(f"Nuova connessione da {client_address}")
    try:
        while True:
            try:
                data = client_socket.recv(8192)
                print(f"{client_address}: {data}")
                if not data:
                    print(f"Client {client_address} disconnesso.")
                    break
            except (ConnectionResetError, Exception):
                print(f"Errore ricezione da {client_address}. Disconnessione.")
                break

            try:
                messaggio = json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, Exception):
                print(f"Errore decodifica JSON da {client_address}.")
                continue

            comando = messaggio.get('comando')

            if comando == "login":
                logged_in_username = login(messaggio)
                setting = threading.Thread(target=setting_AI, args=(logged_in_username,))
                setting.start()
            elif comando == "signin":
                logged_in_username = signin(messaggio)
                setting = threading.Thread(target=setting_AI, args=(logged_in_username,))
                setting.start()
            elif comando == "crea_gruppo":
                crea_gruppo(messaggio)
            elif comando == "messaggio":
                inoltra = threading.Thread(target=inoltra_messaggio, args=(messaggio,logged_in_username,))
                inoltra.start()
            elif comando == "logout":

                if logged_in_username:

                    messaggio_da_inoltrare = {
                        "comando": "logout"
                    }

                    client_socket.send(json.dumps(messaggio_da_inoltrare).encode('utf-8'))

                    with clients_lock:
                        if logged_in_username in clients_sockets and clients_sockets[
                            logged_in_username] == client_socket:
                            del clients_sockets[logged_in_username]
                            del user_ai_chats[logged_in_username]



            elif comando == "is_in_gruppo":
                is_in_gruppo(messaggio, logged_in_username)
            elif comando == "ftp_file_notification":
                # Gestisce la notifica di trasferimento file completato via FTP
                if logged_in_username:
                    mittente = logged_in_username
                    destinatario = messaggio.get("destinatario")
                    nome_file = messaggio.get("nome_file")

                    # Registra il completamento del trasferimento file
                    messaggio_notifica = f"Ha completato il trasferimento del file: {nome_file} (via FTP)"

                    # Verifica se il destinatario è un gruppo
                    gruppo, membri = is_group(destinatario)
                    if gruppo:
                        nuovo_messaggio_salvataggio = {
                            "nome_gruppo": destinatario,
                            "mittente": mittente,
                            "messaggio": messaggio_notifica
                        }
                        salva_messaggio('datiGruppi', nuovo_messaggio_salvataggio)

                        # Notifica il gruppo
                        messaggio_da_inoltrare = {
                            "comando": "nuovo_messaggio_gruppo",
                            "nome_gruppo": destinatario,
                            "mittente": mittente,
                            "messaggio": messaggio_notifica,
                            "ftp": True
                        }
                    else:
                        nuovo_messaggio_salvataggio = {
                            "mittente": mittente,
                            "destinatario": destinatario,
                            "messaggio": messaggio_notifica
                        }
                        salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

                        # Notifica il destinatario privato
                        messaggio_da_inoltrare = {
                            "comando": "nuovo_messaggio_privato",
                            "mittente": mittente,
                            "messaggio": messaggio_notifica,
                            "ftp": True
                        }

                    manda_messaggio(messaggio_da_inoltrare, mittente, destinatario)

            elif comando in ["richiesta_chiamata", "chiamata", "chiamata_accettata", "chiamata_rifiutata"]:
                inoltra_chiamata(messaggio, logged_in_username)



    except Exception as e:
        print(f"Errore nel thread per {client_address}: {e}")
    finally:
        if logged_in_username:
            with clients_lock:
                if logged_in_username in clients_sockets and clients_sockets[logged_in_username] == client_socket:
                    del clients_sockets[logged_in_username]
                    del user_ai_chats[logged_in_username]
        client_socket.close()


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(server_address)
server_socket.listen(10)

# Crea le cartelle necessarie per il server
os.makedirs("datiChat", exist_ok=True)
os.makedirs("datiGruppi", exist_ok=True)
os.makedirs("file_storage", exist_ok=True)  # Nuova cartella per salvare i file

if not os.path.exists('datiUtente.json'):
    with open('datiUtente.json', 'w', encoding='utf-8') as f:
        json.dump({"utenti": []}, f, indent=4)
if not os.path.exists('datiGruppi.json'):
    with open('datiGruppi.json', 'w', encoding='utf-8') as f:
        json.dump({"gruppi": []}, f, indent=4)

# Avvia il server FTP
setup_ftp_server()
active_users_thread = threading.Thread(target=print_active_users)
active_users_thread.daemon = True
active_users_thread.start()

print(f"[SERVER] In ascolto su {server_address}")

while True:
    try:
        client_socket, client_address = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.daemon = True
        thread.start()
    except Exception as e:
        print(f"Errore nell'accettare connessione: {e}")
        pass