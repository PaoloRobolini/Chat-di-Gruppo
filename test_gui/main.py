import dearpygui.dearpygui as dpg

def invia_messaggio():
    messaggio = dpg.get_value("input_messaggio")
    dpg.set_value("chat_testo", messaggio)

if __name__ == '__main__':
    dpg.create_context()
    dpg.create_viewport(title="Chat", width=1280, height=720)
    dpg.add_viewport_menu_bar()

    with dpg.viewport_menu_bar():
        with dpg.menu(label="Opzioni"):
            dpg.add_menu_item(label="Attiva/Disattiva Schermo Intero", callback=dpg.toggle_viewport_fullscreen)

    with dpg.window(tag="chat", width=600, height=600, pos=(0, 19), no_move=True, no_resize=True, no_close=True, no_title_bar=True):
        dpg.add_text(tag="chat_testo")

    with dpg.window(tag="input", width=600, height=100, pos=(0, 619), no_move=True, no_resize=True, no_close=True, no_title_bar=True):
        dpg.add_input_text(tag="input_messaggio")
        dpg.add_button(tag="bottone_messaggio", label="Invia messaggio", callback=invia_messaggio)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()