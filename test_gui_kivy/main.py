from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

Builder.load_file("chat.kv")

class LoginScreen(Screen):
    def login(self):
        username = self.ids.username_input.text.strip()
        if username:
            chat_screen = self.manager.get_screen('chat')
            chat_screen.username = username
            self.manager.current = 'chat'


class ChatScreen(Screen):
    username = StringProperty("")
    chat_history = StringProperty("")

    def send_message(self):
        message = self.ids.message_input.text.strip()
        if message:
            self.chat_history += f"\n{self.username}: {message}"
            self.chat_history += f"\nBot: Ciao {self.username}, hai detto: \"{message}\""
            self.ids.message_input.text = ""


class ChatApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(ChatScreen(name='chat'))
        return sm


if __name__ == '__main__':
    ChatApp().run()