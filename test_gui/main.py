import dearpygui.dearpygui as dpg

if __name__ == '__main__':
    dpg.create_context()
    dpg.create_viewport(title="Chat", width=800, height=600)

    with dpg.window(label="Chat", width=800, height=600, no_move=True, no_resize=True):
        dpg.add_text("Questa è la chat")

    with dpg.window(label="Input", width=800, height=100, no_move=True, no_resize=True):
        dpg.add_input_text()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()