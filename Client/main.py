import socket

nome_utente = input("Inserisci il tuo nome: ")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 5000))

