import json
import socket
import threading
import os
import time
from tempfile import NamedTemporaryFile
from typing import Union, Tuple, List, Optional

import google.generativeai as genai
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from soupsieve.util import lower
import datetime

HOST = "0.0.0.0"
PORT = 50000
FTP_PORT = 21
server_address = (HOST, PORT)

nome_AI = "AI"

# Lock per i file dei dati degli utenti e dei gruppi
lock_datiUtente = threading.Lock()
lock_datiGruppi = threading.Lock()

# Dizionari dei dati degli utenti e dei gruppi
datiUtente = {}
datiGruppi = {}

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


def salva_dati():
    while True:
        try:
            with lock_datiUtente:
                with open("datiUtente.json", "w", encoding="utf-8") as file:
                    json.dump(datiUtente, file, ensure_ascii=False, indent=4)
                print("Dati degli utenti salvati correttamente")
        except Exception as e:
            print(f"Eccezione durante il salvatraggio dei dati degli utenti: {e}")

        try:
            with lock_datiGruppi:
                with open("datiGruppi.json", "w", encoding="utf-8") as file:
                    json.dump(datiGruppi, file, ensure_ascii=False, indent=4)
                print("Dati dei gruppi salvati correttamente")
        except Exception as e:
            print(f"Eccezione durante il salvatraggio dei dati dei gruppi: {e}")

        time.sleep(30)


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
    with lock_datiGruppi:
        for gruppo in datiGruppi.get("gruppi", []):
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


def manda_gruppi_client(username):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
    os.makedirs(cartella_chat, exist_ok=True)
    gruppi_utente = []

    # Cerco tutti i gruppi in cui è presente l'utente
    with lock_datiGruppi:
        gruppi_utente = [g for g in datiGruppi.get("gruppi", []) if username in g.get("membri", [])]

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


def manda_chat_client(username):
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
        dati = datiUtente

    # Verifico la presenza dell'utente
    for utente in dati.get("utenti", []):
        if utente.get("email") == mail and utente.get("password") == password:
            username_trovato = utente.get("username")
            break

    if username_trovato:
        with clients_lock:
            if username_trovato in list(clients_sockets.keys()):
                client_socket.sendall(b"0")
                return None
            clients_sockets[username_trovato] = client_socket

        client_socket.sendall(json.dumps(username_trovato).encode('utf-8'))

        chat = manda_chat_client(username_trovato)
        gruppi = manda_gruppi_client(username_trovato)

        # Invia direttamente le informazioni sui file
        dato_da_inviare = {
            "comando": "files_ready",
            "cartella": f"temp_{username_trovato}",
            "chat": chat,
            "gruppi": gruppi
        }
        print(f"File da mandare a {client_address}: {dato_da_inviare}")
        client_socket.sendall(json.dumps(dato_da_inviare).encode())

        return username_trovato

    else:
        client_socket.sendall(b"1")

    return None


def signin(messaggio):
    username = messaggio.get("username")
    mail = messaggio.get("mail")
    password = messaggio.get("password")

    with lock_datiUtente:
        dati = datiUtente

    if any(u.get("email") == mail for u in dati.get("utenti", [])):
        reply = "1"
    elif "@" not in mail:
        reply = "2"
    elif any(u.get("username") == username for u in dati.get("utenti", [])):
        reply = "3"
    else:
        reply = "0"
        nuovo_utente = {"email": mail, "password": password, "username": username}

        with lock_datiUtente:
            datiUtente.setdefault("utenti", []).append(nuovo_utente)

    # Aggiungi l'utente al server FTP usando l'authorizer globale
    try:
        ftp_authorizer.add_user(username, password, os.path.join(os.getcwd(), "file_storage"),
                                perm="elradfmw")
        print(f"Utente {username} aggiunto al server FTP")
    except Exception as e:
        print(f"Errore nell'aggiunta dell'utente al server FTP: {e}")

    client_socket.sendall(reply.encode('utf-8'))
    return username


def crea_gruppo(messaggio):
    """
    Crea un nuovo gruppo o aggiunge un utente a un gruppo esistente.
    I dati sono mantenuti in memoria e salvati periodicamente dal thread dedicato.
    """
    nome_gruppo = messaggio.get("nome_gruppo")
    mittente = messaggio.get("mittente")
    esiste_gruppo = False

    # Acquisiamo prima il lock per i dati dei gruppi
    with lock_datiGruppi:
        # Controlliamo se il gruppo esiste
        gruppo_esistente = next((g for g in datiGruppi.get("gruppi", []) if g.get("nome") == nome_gruppo), None)

        # Se il gruppo esiste, aggiungiamo il mittente se non è già presente
        if gruppo_esistente:
            esiste_gruppo = True
            if mittente not in gruppo_esistente.get("membri", []):
                gruppo_esistente.setdefault("membri", []).append(mittente)
        # Se il gruppo non esiste, lo creiamo
        else:
            nuovo_gruppo = {"nome": nome_gruppo, "membri": [mittente]}
            # Inizializziamo la lista dei gruppi se non esiste
            if "gruppi" not in datiGruppi:
                datiGruppi["gruppi"] = []
            datiGruppi["gruppi"].append(nuovo_gruppo)

    # Gestiamo il file di chat del gruppo solo se è un nuovo gruppo
    if not esiste_gruppo:
        file_gruppo_path = os.path.join("datiGruppi", f"{nome_gruppo}.json")

        # Creiamo o otteniamo il lock per questo gruppo
        with lock_for_locks:
            if nome_gruppo not in locks_chat:
                locks_chat[nome_gruppo] = threading.Lock()
            gruppo_lock = locks_chat[nome_gruppo]

        # Inizializziamo il file di chat del gruppo se è nuovo
        with gruppo_lock:
            os.makedirs("datiGruppi", exist_ok=True)
            if not os.path.exists(file_gruppo_path):
                with open(file_gruppo_path, 'w', encoding='utf-8') as file:
                    json.dump({
                        "gruppo": [{
                            "mittente": "Il gruppo",
                            "messaggio": f"Il gruppo '{nome_gruppo}' è stato creato.",
                            "orario": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }]
                    }, file, indent=4)

    client_socket.sendall(b"Gruppo creato o aggiunto con successo")


def _leggi_json_file(file_path: str) -> Optional[dict]:
    """
    Legge e restituisce il contenuto di un file JSON.
    È una funzione interna usata per riusabilità e gestione degli errori.
    """
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Qui puoi aggiungere un log dell'errore (ad esempio, usando il modulo 'logging')
        # print(f"Errore nella lettura del file {file_path}: {e}")
        return None


def _formatta_messaggi_per_gemini(messages: List[dict]) -> List[str]:
    """
    Formatta una lista di dizionari di messaggi in stringhe leggibili per Gemini.
    Gestisce chiavi mancanti con valori di default per maggiore robustezza.
    """
    formatted_messages = []
    for msg in messages:
        formatted_messages.append(
            f"{msg.get('mittente', 'Sconosciuto')}: {msg.get('messaggio', '')} il {msg.get('orario', 'data sconosciuta')}"
        )
    return formatted_messages


# --- FUNZIONI DI PREPARAZIONE (OTTIMIZZATE MA CON FIRMA ORIGINALE) ---

def prepara_chat_AI(username: str, nome_utente: str) -> Union[str, Tuple[str, List[str]]]:
    """
    Prepara lo storico di una chat privata specifica.
    Restituisce un messaggio di errore (stringa) o una tupla (descrizione, storico formattato).
    Questa funzione è pensata per un singolo nome_utente, non per il caso "tutti".
    """
    nome_file = genera_nome_file(username, nome_utente)
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    file_path = os.path.join(cartella_chat, nome_file)

    chat_data = _leggi_json_file(file_path)
    if chat_data:
        storico_raw = chat_data.get("chat", [])
        storico_formattato = _formatta_messaggi_per_gemini(storico_raw)
        return f"Chat privata con '{nome_utente}'", storico_formattato
    else:
        return f"Il contatto '{nome_utente}' non esiste o non ci sono dati di chat validi."


def prepara_gruppo_AI(username: str, nome_gruppo: str) -> Union[str, Tuple[str, List[str]]]:
    """
    Prepara lo storico di un gruppo specifico.
    Restituisce un messaggio di errore (stringa) o una tupla (descrizione, storico formattato).
    Questa funzione è pensata per un singolo nome_gruppo, non per il caso "tutti".
    """
    # Si assume che 'datiGruppi' e 'lock_datiGruppi' siano disponibili globalmente
    global datiGruppi, lock_datiGruppi

    with lock_datiGruppi:
        gruppi_utente = [g for g in datiGruppi.get("gruppi", []) if username in g.get("membri", [])]

    if not any(g["nome"] == nome_gruppo for g in gruppi_utente):
        return f"Non appartieni al gruppo '{nome_gruppo}'."

    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
    file_path = os.path.join(cartella_chat, f"{nome_gruppo}.json")

    gruppo_data = _leggi_json_file(file_path)
    if gruppo_data:
        storico_raw = gruppo_data.get("gruppo", [])
        storico_formattato = _formatta_messaggi_per_gemini(storico_raw)
        return f"Gruppo '{nome_gruppo}'", storico_formattato
    else:
        return f"Il gruppo '{nome_gruppo}' non esiste o non ci sono dati di gruppo validi."


# --- FUNZIONI DI GESTIONE (OTTIMIZZATE E CON LA CORREZIONE PER "tutti") ---

def gestisci_carica_chat(chat, username, nome_utente):
    """
    Gestisce il caricamento e l'invio dello storico delle chat private a Gemini.
    Mantiene la firma originale della funzione.
    Il caso 'nome_utente == "tutti"' è gestito qui direttamente per aggregare tutti gli storici.
    """
    if nome_utente.lower() == "tutti":  # Usiamo .lower() per una maggiore robustezza nel confronto
        all_chats_context = []
        cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))

        # Itera su tutti i file nella cartella delle chat private
        for file_name in os.listdir(cartella_chat):
            if file_name.endswith(".json"):
                chat_name_parts = file_name[:-5].split('_')
                # Controlla se il file della chat include l'username corrente
                if username in chat_name_parts:
                    # Determina il nome dell'altro utente coinvolto nella chat
                    other_user = chat_name_parts[0] if chat_name_parts[1] == username else chat_name_parts[1]

                    # Costruisci il percorso completo al file della chat
                    file_path = os.path.join(cartella_chat, file_name)

                    # Leggi direttamente i dati della chat dal file
                    chat_data = _leggi_json_file(file_path)

                    if chat_data:
                        storico_raw = chat_data.get("chat", [])
                        storico_messaggi = _formatta_messaggi_per_gemini(storico_raw)
                        if storico_messaggi:  # Aggiungi lo storico solo se ci sono messaggi
                            all_chats_context.append(
                                f"\n--- Chat privata con '{other_user}' ---\n" + "\n".join(storico_messaggi))

        if all_chats_context:
            # Invia un UNICO messaggio a Gemini con tutti gli storici concatenati
            return chat.send_message("Ecco tutte le mie chat private:" + "\n".join(all_chats_context)).text
        else:
            return "Nessuno storico chat privato trovato per il tuo utente."
    else:
        # Carica una singola chat privata (qui è corretto usare prepara_chat_AI)
        storico_result = prepara_chat_AI(username, nome_utente)

        if isinstance(storico_result, str):  # Se il risultato è una stringa, è un messaggio di errore
            return storico_result
        else:  # Altrimenti è una tupla (descrizione, lista_di_messaggi_formattati)
            desc, storico_messaggi = storico_result
            if storico_messaggi:
                return chat.send_message(f"{desc}\n" + "\n".join(storico_messaggi)).text
            else:
                return f"Nessun messaggio trovato per '{nome_utente}'."


def gestisci_carica_gruppo(chat, username, nome_gruppo):
    """
    Gestisce il caricamento e l'invio dello storico dei gruppi a Gemini.
    Mantiene la firma originale della funzione.
    Il caso 'nome_gruppo == "tutti"' è gestito qui direttamente per aggregare tutti gli storici.
    """
    if nome_gruppo.lower() == "tutti":  # Usiamo .lower() per una maggiore robustezza nel confronto
        all_groups_context = []

        # Si assume che 'datiGruppi' e 'lock_datiGruppi' siano disponibili globalmente
        global datiGruppi, lock_datiGruppi

        with lock_datiGruppi:
            # Itera sui gruppi definiti in datiGruppi
            for gruppo_info in datiGruppi.get("gruppi", []):
                current_group_name = gruppo_info.get("nome")
                # Controlla se il nome del gruppo esiste e se l'utente è un membro
                if current_group_name and username in gruppo_info.get("membri", []):
                    # Costruisci il percorso al file JSON del gruppo
                    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiGruppi'))
                    file_path = os.path.join(cartella_chat, f"{current_group_name}.json")

                    # Leggi direttamente i dati del gruppo dal file
                    gruppo_data = _leggi_json_file(file_path)

                    if gruppo_data:
                        storico_raw = gruppo_data.get("gruppo", [])
                        storico_messaggi = _formatta_messaggi_per_gemini(storico_raw)
                        if storico_messaggi:  # Aggiungi lo storico solo se ci sono messaggi
                            all_groups_context.append(
                                f"\n--- Gruppo '{current_group_name}' ---\n" + "\n".join(storico_messaggi))

        if all_groups_context:
            # Invia un UNICO messaggio a Gemini con tutti gli storici dei gruppi concatenati
            return chat.send_message("Ecco tutti i miei gruppi:" + "\n".join(all_groups_context)).text
        else:
            return "Nessuno storico gruppo trovato per il tuo utente."
    else:
        # Carica un singolo gruppo (qui è corretto usare prepara_gruppo_AI)
        storico_result = prepara_gruppo_AI(username, nome_gruppo)

        if isinstance(storico_result, str):  # Se il risultato è una stringa, è un messaggio di errore
            return storico_result
        else:  # Altrimenti è una tupla (descrizione, lista_di_messaggi_formattati)
            desc, storico_messaggi = storico_result
            if storico_messaggi:
                return chat.send_message(f"{desc}\n" + "\n".join(storico_messaggi)).text
            else:
                return f"Nessun messaggio trovato per il gruppo '{nome_gruppo}'."


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
    with lock_datiGruppi:
        gruppi_utente = [g for g in datiGruppi.get("gruppi", []) if username in g.get("membri", [])]

    return {
        "gruppi": gruppi_utente,
        "chat": all_chats
    }


def ai(messaggio, username):
    # Salvataggio del messaggio dell'utente
    messaggio_salvataggio = {"mittente": username, "destinatario": nome_AI, "messaggio": messaggio.get("messaggio"),
                             "orario": messaggio["orario"]}
    salva_messaggio('datiChat', messaggio_salvataggio)

    with user_ai_chats_lock:
        if username not in user_ai_chats:
            model = genai.GenerativeModel('gemini-2.5-flash')
            user_ai_chats[username] = model.start_chat()
            setting_AI(username)

        chat = user_ai_chats[username]


    # Gestione comandi speciali
    msg = messaggio.get("messaggio")
    msg = msg.split(":")
    comando = lower(msg[0])
    risposta = ""

    if comando == "carica chat":
        nome_utente = msg[1].strip()
        chat.send_message(
            "In questo caso ti caricherò direttamente le chat, quindi non devi rispondermi con il comando che ti ho insegnato, ma con tipo 'caricata chat con e la persona'")
        risposta = gestisci_carica_chat(chat, username, nome_utente)

    elif comando == "carica gruppo":
        nome_gruppo = msg[1].strip()
        chat.send_message(
            "In questo caso ti caricherò direttamente i gruppi, quindi non devi rispondermi con il comando che ti ho insegnato, ma con tipo 'caricato gruppo con il nome del gruppo'")

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
                risposta = str(chat.send_message(
                    f"Questi sono tutti gli utenti con cui ho delle chat: {nomi['chat']} questi sono i gruppi a cui faccio parte: {nomi['gruppi']}").text)
            else:
                esci = True

    # Invio della risposta
    messaggio_da_inoltrare = {"comando": "nuovo_messaggio_privato", "mittente": nome_AI,
                              "messaggio": risposta, "orario": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

    manda_messaggio(messaggio_da_inoltrare, nome_AI, username)
    if risposta:
        messaggio_salvataggio = {"mittente": nome_AI, "destinatario": username, "messaggio": risposta,
                                 "orario": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
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
            nuovo_messaggio_salvataggio = {"nome_gruppo": destinatario, "mittente": mittente,
                                           "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            salva_messaggio('datiGruppi', nuovo_messaggio_salvataggio)
        else:
            messaggio_da_inoltrare = {"comando": "nuovo_messaggio_privato", "mittente": mittente,
                                      "messaggio": testo_messaggio, "orario": messaggio["orario"]}
            nuovo_messaggio_salvataggio = {"mittente": mittente, "destinatario": destinatario,
                                           "messaggio": testo_messaggio, "orario": messaggio["orario"]}
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


def setting_AI(username):
    chat = user_ai_chats[username]
    instructions = f"""
    Mi presento come {username} e interagirò con te come se tu fossi {nome_AI}.

    Comandi disponibili:
    1. Per caricare chat private:
    `Carica chat: [nome_utente]`
    
    2. Per caricare gruppi:
    `Carica gruppo: [nome_gruppo]`
    
    3. Per caricare tutto:
    Usa 'tutti' come nome (es: `Carica chat: tutti`)
    
    4. Per verificare nomi disponibili delle chat e dei gruppi:
    `Verifica nomi`

    Linee guida:
    - Non citare sezioni specifiche dei file nelle risposte
    - Quando mancano informazioni, rispondi solo con il comando appropriato
    - Usa 'Verifica nomi' per controllare l'ortografia esatta di chat e gruppi
    - Dopo la verifica dei nomi, usa il comando di caricamento appropriato

    La verifica dei nomi ti aiuterà a:
    - Evitare errori di maiuscole/minuscole
    - Vedere tutte le chat e gruppi disponibili
    - Usare i nomi esatti nei comandi
    """
    chat.send_message(instructions)



def setup_ftp_server():
    # Usa l'authorizer globale
    global ftp_authorizer

    # Leggi gli utenti registrati e aggiungili come utenti FTP
    with lock_datiUtente:
        dati = datiUtente

    for utente in dati.get("utenti", []):
        username = utente.get("username")
        password = utente.get("password")
        # Aggiungi l'utente con accesso alla cartella file_storage
        ftp_authorizer.add_user(username, password, os.path.join(os.getcwd(), "file_storage"), perm="elradfmw")

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
            elif comando == "signin":
                logged_in_username = signin(messaggio)
            elif comando == "crea_gruppo":
                crea_gruppo(messaggio)
            elif comando == "messaggio":
                inoltra = threading.Thread(target=inoltra_messaggio, args=(messaggio, logged_in_username,))
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

            elif comando == "ftp_file_notification":
                # Gestisce la notifica di trasferimento file completato via FTP
                if logged_in_username:
                    mittente = logged_in_username
                    destinatario = messaggio.get("destinatario")
                    nome_file = messaggio.get("nome_file")
                    orario = messaggio.get("orario")

                    # Registra il completamento del trasferimento file
                    messaggio_notifica = f"Ha completato il trasferimento del file: {nome_file} (via FTP)"

                    # Verifica se il destinatario è un gruppo
                    gruppo, membri = is_group(destinatario)
                    if gruppo:
                        nuovo_messaggio_salvataggio = {
                            "nome_gruppo": destinatario,
                            "mittente": mittente,
                            "messaggio": messaggio_notifica,
                            "orario": orario
                        }
                        salva_messaggio('datiGruppi', nuovo_messaggio_salvataggio)

                        # Notifica il gruppo
                        messaggio_da_inoltrare = {
                            "comando": "nuovo_messaggio_gruppo",
                            "nome_gruppo": destinatario,
                            "mittente": mittente,
                            "messaggio": messaggio_notifica,
                            "orario": orario,
                            "ftp": True
                        }
                    else:
                        nuovo_messaggio_salvataggio = {
                            "mittente": mittente,
                            "destinatario": destinatario,
                            "messaggio": messaggio_notifica,
                            "orario": orario
                        }
                        salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

                        # Notifica il destinatario privato
                        messaggio_da_inoltrare = {
                            "comando": "nuovo_messaggio_privato",
                            "mittente": mittente,
                            "messaggio": messaggio_notifica,
                            "orario": orario,
                            "ftp": True
                        }

                    manda_messaggio(messaggio_da_inoltrare, mittente, destinatario)

            elif comando in ["richiesta_chiamata", "chiamata", "chiamata_accettata", "chiamata_rifiutata",
                             "chiamata_terminata"]:
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
os.makedirs("file_storage", exist_ok=True)

# Inizializza il file "datiUtente.json" se non esiste
if not os.path.exists('datiUtente.json'):
    with open('datiUtente.json', 'w', encoding='utf-8') as f:
        json.dump({"utenti": []}, f, indent=4)

# inizializza il file "datiGruppi.json" se non esiste
if not os.path.exists('datiGruppi.json'):
    with open('datiGruppi.json', 'w', encoding='utf-8') as f:
        json.dump({"gruppi": []}, f, indent=4)

# Carico i dati degli utenti
with open("datiUtente.json", "r", encoding="utf-8") as f:
    datiUtente = json.load(f)

# Carico i dati dei gruppi
with open("datiGruppi.json", "r", encoding="utf-8") as f:
    datiGruppi = json.load(f)

# Thread per salvare i dati degli utenti e gruppi
salva_file = threading.Thread(target=salva_dati)
salva_file.daemon = True
salva_file.start()

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