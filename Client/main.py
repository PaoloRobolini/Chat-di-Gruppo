import socket

nome_utente = input("Inserisci il tuo nome: ")
destinatario = input("Inserisci il destinatario: ")

server = ("127.0.0.1", 65432)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:
    messaggio = input(f"Inserisci un messaggio per {destinatario}: ")
    if messaggio == "exit":
        break
    s.sendto(messaggio.encode("utf-8"), server)
    messaggio_ricevuto, indirizzo_client = s.recvfrom(1024)
    print(f"{destinatario}: {messaggio_ricevuto.decode('utf-8')}")
