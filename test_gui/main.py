import dearpygui.dearpygui as dpg
from dati_costanti import *


def invia_messaggio():
    messaggio = dpg.get_value("input_messaggio")
    dpg.set_value("chat_testo", dpg.get_value("chat_testo") + f"\n\n{messaggio}")


if __name__ == '__main__':
    dpg.create_context()
    dpg.create_viewport(title="Chat", width=1280, height=720, min_width=800, min_height=600)
    dpg.setup_dearpygui()

    with dpg.window(label="Lista Gruppi", tag="lista_gruppi", width=LARGHEZZA_WIDGET, no_move=True, no_resize=True, no_close=True, no_collapse=True):
        dpg.add_text("Lista Gruppi")

    with dpg.window(label="Chat", tag="chat", pos=(LARGHEZZA_WIDGET, 0), no_move=True, no_resize=True, no_close=True, no_collapse=True):
        dpg.add_text(tag="chat_testo")
        dpg.set_y_scroll("chat", dpg.get_item_height("chat"))

    with dpg.window(label="Input", tag="input", height=ALTEZZA_WIDGET, no_move=True, no_resize=True, no_close=True, no_collapse=True):
        dpg.add_input_text(tag="input_messaggio")
        dpg.add_button(tag="bottone_messaggio", label="Invia messaggio", callback=invia_messaggio)

    with dpg.window(label="Lista Persone Gruppo", tag="lista_persone", width=LARGHEZZA_WIDGET, no_move=True, no_resize=True, no_close=True, no_collapse=True):
        dpg.add_text("Lista Persone Gruppo")

    dpg.show_viewport()

    while dpg.is_dearpygui_running():
        dpg.set_item_height("lista_gruppi", dpg.get_viewport_height())

        dpg.set_item_width("chat", dpg.get_viewport_width() - (LARGHEZZA_WIDGET * 2))
        dpg.set_item_height("chat", dpg.get_viewport_height() - ALTEZZA_WIDGET)

        dpg.set_item_width("input", dpg.get_viewport_width() - (LARGHEZZA_WIDGET * 2))
        dpg.set_item_pos("input", [LARGHEZZA_WIDGET, dpg.get_viewport_height() - ALTEZZA_WIDGET])

        dpg.set_item_height("lista_persone", dpg.get_viewport_height())
        dpg.set_item_pos("lista_persone", [dpg.get_viewport_width() - LARGHEZZA_WIDGET, 0])

        dpg.render_dearpygui_frame()

    dpg.destroy_context()
