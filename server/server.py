import json
import socket
import threading
import os
import base64
import time
from tempfile import NamedTemporaryFile

HOST = "127.0.0.1"
PORT = 65432
server_address = (HOST, PORT)

lock_datiUtente = threading.Lock()
clients_sockets = {}
clients_lock = threading.Lock()
lock_for_locks = threading.Lock()
locks_chat = {}

# Dizionario per tenere traccia dei file in fase di trasferimento
file_transfers = {}
file_transfers_lock = threading.Lock()


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
            'messaggio': nuovo_messaggio['messaggio'].strip()
        }
    elif 'nome_gruppo' in nuovo_messaggio:
        nome_file = f"{nuovo_messaggio['nome_gruppo']}.json"
        chat_key = nuovo_messaggio['nome_gruppo']
        list_key = 'gruppo'
        message_data = {
            'mittente': nuovo_messaggio['mittente'].strip(),
            'messaggio': nuovo_messaggio['messaggio'].strip()
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


def manda_gruppi_client(client_socket, username):
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

    client_socket.sendall(str(len(gruppi_utente)).encode())
    time.sleep(0.05)

    for gruppo_info in gruppi_utente:
        nome_gruppo = gruppo_info["nome"]
        file_name = f"{nome_gruppo}.json"
        file_path = os.path.join(cartella_chat, file_name)
        messaggio_gruppo = {"nome": file_name, "contenuto": {"gruppo": []}}

        with lock_for_locks:
            if nome_gruppo not in locks_chat:
                locks_chat[nome_gruppo] = threading.Lock()
            gruppo_lock = locks_chat[nome_gruppo]

        with gruppo_lock:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        messaggio_gruppo["contenuto"] = json.load(f)
                        if not isinstance(messaggio_gruppo["contenuto"].get('gruppo'), list):
                            messaggio_gruppo["contenuto"] = {"gruppo": []}
                except (FileNotFoundError, json.JSONDecodeError):
                    messaggio_gruppo["contenuto"] = {"gruppo": []}

        client_socket.sendall(json.dumps(messaggio_gruppo).encode())


def manda_chat_client(client_socket, username):
    cartella_chat = os.path.abspath(os.path.join(os.getcwd(), 'datiChat'))
    os.makedirs(cartella_chat, exist_ok=True)
    file_da_mandare = []
    for file_name in os.listdir(cartella_chat):
        if file_name.endswith(".json"):
            chat_name_parts = file_name[:-5].split('_')
            if len(chat_name_parts) == 2 and username in chat_name_parts:
                file_da_mandare.append(file_name)
    dato = str(len(file_da_mandare))
    client_socket.sendall(dato.encode())

    for nome_file in file_da_mandare:
        file_path = os.path.join(cartella_chat, nome_file)
        chat_key = nome_file[:-5]
        messaggio_chat = {"nome": nome_file, "contenuto": {"chat": []}}

        with lock_for_locks:
            if chat_key not in locks_chat:
                locks_chat[chat_key] = threading.Lock()
            file_lock = locks_chat[chat_key]

        with file_lock:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        messaggio_chat['contenuto'] = json.load(f)
                        if not isinstance(messaggio_chat["contenuto"].get('chat'), list):
                            messaggio_chat["contenuto"] = {"chat": []}
                except (FileNotFoundError, json.JSONDecodeError):
                    messaggio_chat["contenuto"] = {"chat": []}
        print(messaggio_chat)
        client_socket.sendall(json.dumps(messaggio_chat).encode())


def handle_client(client_socket, client_address):
    logged_in_username = None
    print(f"Nuova connessione da {client_address}")

    try:
        while True:
            try:
                data = client_socket.recv(4096)
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
                    logged_in_username = username_trovato
                    client_socket.sendall(json.dumps(username_trovato).encode('utf-8'))
                    manda_chat_client(client_socket, username_trovato)
                    manda_gruppi_client(client_socket, username_trovato)
                else:
                    client_socket.sendall(b"1")
            elif comando == "signin":
                username = messaggio.get("username")
                mail = messaggio.get("mail")
                password = messaggio.get("password")
                reply = ""
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
                client_socket.sendall(reply.encode('utf-8'))
            elif comando == "crea_gruppo":

                if not logged_in_username:
                    continue
                nome_gruppo = messaggio.get("nome_gruppo")
                mittente = logged_in_username
                if not nome_gruppo:
                    continue
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
            elif comando == "messaggio":

                if not logged_in_username:
                    continue
                mittente = logged_in_username
                destinatario = messaggio.get("destinatario")
                testo_messaggio = messaggio.get("messaggio")
                if not destinatario or not testo_messaggio:
                    continue

                gruppo, membri = is_group(destinatario)

                if gruppo:
                    messaggio_da_inoltrare = {"comando": "nuovo_messaggio_gruppo", "nome_gruppo": destinatario,"mittente": mittente, "messaggio": testo_messaggio}
                    nuovo_messaggio_salvataggio = {"nome_gruppo": destinatario, "mittente": mittente,"messaggio": testo_messaggio}
                    salva_messaggio('datiGruppi', nuovo_messaggio_salvataggio)
                else:
                    messaggio_da_inoltrare = {"comando": "nuovo_messaggio_privato", "mittente": mittente,"messaggio": testo_messaggio}
                    nuovo_messaggio_salvataggio = {"mittente": mittente, "destinatario": destinatario,"messaggio": testo_messaggio}
                    salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

                manda_messaggio(messaggio_da_inoltrare, mittente, destinatario)

            elif comando == "is_in_gruppo":
                if not logged_in_username:
                    client_socket.sendall(b"error_not_logged_in")
                    continue
                nome_gruppo = messaggio.get("nome_gruppo")
                mittente = logged_in_username
                if not nome_gruppo:
                    client_socket.sendall(b"error_missing_group_name")
                    continue
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
            elif comando == "inizia_trasferimento_file":

                if not logged_in_username:
                    continue
                mittente = logged_in_username
                destinatario = messaggio.get("destinatario")
                nome_file = messaggio.get("nome_file")
                file_size = messaggio.get("file_size")

                if not destinatario or not nome_file:
                    continue

                # Crea una chiave univoca per questo trasferimento
                transfer_key = f"{mittente}_{destinatario}_{nome_file}_{file_size}"

                # Prepara la struttura per salvare il file sul server
                with file_transfers_lock:
                    file_transfers[transfer_key] = {
                        "chunks": {},
                        "total_chunks": 0,
                        "completed": False,
                        "nome_file": nome_file,
                        "mittente": mittente,
                        "destinatario": destinatario,
                        "file_size": file_size
                    }

                # Registra il file in arrivo nelle chat
                messaggio_notifica = f"Ha iniziato il trasferimento del file: {nome_file}"
                nuovo_messaggio_salvataggio = {"mittente": mittente, "destinatario": destinatario,
                                               "messaggio": messaggio_notifica}
                salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

            elif comando == "trasferimento_file_chunk":

                if not logged_in_username:
                    continue
                mittente = logged_in_username
                destinatario = messaggio.get("destinatario")
                nome_file = messaggio.get("nome_file")
                chunk = messaggio.get("chunk")
                chunk_id = messaggio.get("chunk_id")
                total_chunks = messaggio.get("total_chunks")

                if not destinatario or not nome_file:
                    continue

                # Chiave univoca per questo trasferimento
                transfer_key = f"{mittente}_{destinatario}_{nome_file}_{messaggio.get('file_size', '0')}"

                # Salva il chunk nella struttura temporanea
                with file_transfers_lock:
                    if transfer_key in file_transfers:
                        file_transfers[transfer_key]["chunks"][chunk_id] = chunk
                        file_transfers[transfer_key]["total_chunks"] = total_chunks

            elif comando == "fine_trasferimento_file":

                if not logged_in_username:
                    continue

                mittente = logged_in_username
                destinatario = messaggio.get("destinatario")
                nome_file = messaggio.get("nome_file")
                file_size = messaggio.get("file_size", "0")

                if not destinatario or not nome_file:
                    continue

                # Chiave univoca per questo trasferimento
                transfer_key = f"{mittente}_{destinatario}_{nome_file}_{file_size}"

                # Salva il file completo su disco nella cartella file_storage
                os.makedirs("file_storage", exist_ok=True)


                gruppo, membri = is_group(destinatario)
                if gruppo:
                    chat_dir = os.path.join("file_storage",destinatario)
                else:
                    chat_dir = os.path.join("file_storage", genera_nome_file(mittente, destinatario).replace(".json", ""))

                os.makedirs(chat_dir, exist_ok=True)

                file_path = os.path.join(chat_dir, nome_file)
                file_saved = False

                with clients_lock:
                    if destinatario in clients_sockets:
                        destinatario_socket = clients_sockets[destinatario]

                with file_transfers_lock:
                    if transfer_key in file_transfers and len(file_transfers[transfer_key]["chunks"]) == \
                            file_transfers[transfer_key]["total_chunks"]:
                        # Ordina i chunk e scrivili su file
                        try:
                            with open(file_path, 'wb') as file_out:
                                for i in range(file_transfers[transfer_key]["total_chunks"]):
                                    chunk_data = file_transfers[transfer_key]["chunks"].get(i)
                                    if chunk_data:
                                        decoded_chunk = base64.b64decode(chunk_data)
                                        file_out.write(decoded_chunk)

                            file_transfers[transfer_key]["completed"] = True
                            file_saved = True
                            print(f"File {nome_file} salvato con successo in {file_path}")

                            # Registra il completamento del trasferimento file nelle chat
                            messaggio_notifica = f"Ha completato il trasferimento del file: {nome_file} (salvato sul server)"
                            nuovo_messaggio_salvataggio = {"mittente": mittente, "destinatario": destinatario,
                                                           "messaggio": messaggio_notifica}
                            salva_messaggio('datiChat', nuovo_messaggio_salvataggio)

                        except Exception as e:
                            print(f"Errore nel salvataggio del file: {e}")

                        # Pulizia dopo il salvataggio
                        del file_transfers[transfer_key]

                # Adesso il server inizia a inviare il file al destinatario
                if file_saved:
                    print(f"📤 File selezionato: {file_path}")
                    nome_file_basename = os.path.basename(file_path)

                    # Ottieni dimensione del file e calcola numero di chunk
                    file_size = os.path.getsize(file_path)
                    chunk_size = 2048  # Dimensione di ogni chunk in bytes
                    total_chunks = (file_size + chunk_size - 1) // chunk_size  # Arrotonda per eccesso

                    # Invio le informazioni di inizio trasferimento
                    inizia_trasferimento = {
                        "comando": "trasferimento_file_inizio",
                        "mittente": logged_in_username,
                        "destinatario": destinatario,
                        "nome_file": nome_file_basename,
                        "file_size": file_size
                    }

                    print(inizia_trasferimento)
                    manda_messaggio(inizia_trasferimento, mittente, destinatario)

                    time.sleep(0.5)

                    # Leggi e invia i chunk del file
                    with open(file_path, "rb") as file:
                        for chunk_id in range(total_chunks):
                            # Posizionati all'inizio del chunk corrente
                            file.seek(chunk_id * chunk_size)
                            chunk_data = file.read(chunk_size)
                            if not chunk_data:  # Fine del file
                                break

                            # Converti il chunk in base64 per sicurezza nella trasmissione JSON
                            chunk_base64 = base64.b64encode(chunk_data).decode('utf-8')

                            # Crea un messaggio per ogni chunk
                            chunk_msg = {
                                "comando": "trasferimento_file_chunk",
                                "mittente": logged_in_username,
                                "destinatario": destinatario,
                                "nome_file": nome_file_basename,
                                "chunk": chunk_base64,
                                "chunk_id": chunk_id,
                                "total_chunks": total_chunks,
                                "chunk_size": len(chunk_data),
                                "file_size": file_size
                            }

                            # Invia il chunk
                            print(chunk_msg)
                            manda_messaggio(chunk_msg,mittente, destinatario)


                            # Piccola pausa per evitare sovraccarichi
                            time.sleep(0.05)

                    # Notifica il server che il trasferimento è completo
                    fine_trasferimento = {
                        "comando": "trasferimento_file_fine",
                        "mittente": logged_in_username,
                        "destinatario": destinatario,
                        "nome_file": nome_file_basename,
                        "file_size": file_size
                    }
                    print(fine_trasferimento)
                    manda_messaggio(fine_trasferimento, mittente, destinatario)
    except Exception as e:
        print(f"Errore nel thread per {client_address}: {e}")
    finally:
        if logged_in_username:
            with clients_lock:
                if logged_in_username in clients_sockets and clients_sockets[logged_in_username] == client_socket:
                    del clients_sockets[logged_in_username]
        client_socket.close()


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(server_address)
server_socket.listen(5)

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

print(f"[SERVER] In ascolto su {server_address}")

while True:
    try:
        client_socket, client_address = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.start()
    except Exception as e:
        print(f"Errore nell'accettare connessione: {e}")
        pass