diz = {
    0 : (12, "Baolo"),
    1 : (13, "Marco"),
    2: (1449, "Terrone")
}
valori = diz.values()
for ip, nome in valori:
    if nome == "Terrone":
        print(ip)