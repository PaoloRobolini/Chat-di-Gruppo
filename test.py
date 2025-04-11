def kwargs (**kwargs):
    print(kwargs)

dizionario = {}

for i in range(1, 11):
    dizionario[f"Parametro{i}"] = f"Opzione {i}"

kwargs(**dizionario)

kwargs(Parametro1="Opzione 1", parametro2="Opzione 2", parametro3="Opzione 3",parametro4="Opzione 4", parametro5="Opzione 5"
       , parametro6="Opzione 6", parametro7="Opzione 7", parametro8="Opzione 8", parametro9="Opzione 9", parametro10="Opzione 10")