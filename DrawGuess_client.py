import logging
import socket
import time

import select
import sys
import os
import json
from queue import Queue
os.environ['KIVY_NO_CONSOLELOG'] = '1'
import threading
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from kivy.config import Config
Config.set('graphics', 'resizable', False)
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
from kivy.app import App
from kivy.uix.label import Label
from kivy.core.text import LabelBase
from kivy.uix.image import Image
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
logging.getLogger("kivy").setLevel(logging.WARNING)
from tcp_by_size import send_with_size, recv_by_size


DEFAULT_IP = '127.0.0.1'
WIDTH = 1440
HEIGHT = 810
sign_up_username = b''
sign_up_password = b''
sign_in_username = b''
sign_in_password = b''
create_pressed = False
start_pressed = False
clear_pressed = False
guess = b''
join_code = b''
word = b''
global_username = ''
draw_end = False
lock = threading.Lock()


class DrawDataHandler:
    def __init__(self):
        self.send_q = Queue()

    def get_data_send(self):
        return self.send_q.get()

    def put_data_send(self, dic: dict):
        self.send_q.put(dic)

    def is_to_send(self):
        return not self.send_q.empty()


draw_data = DrawDataHandler()

class LockedTextInput(TextInput):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # If touch is inside the text input, return True to consume the touch event
            return True
        return super(LockedTextInput, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            # If touch is inside the text input, return True to consume the touch event
            return True
        return super(LockedTextInput, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            # If touch is inside the text input, return True to consume the touch event
            return True
        return super(LockedTextInput, self).on_touch_up(touch)


class Layout(FloatLayout):
    def __init__(self, **kwargs):
        super(Layout, self).__init__(**kwargs)
        Window.size = (WIDTH, HEIGHT)
        LabelBase.register(name='MyFont', fn_regular='Roboto-Regular.ttf')
        LabelBase.register(name='MyFontBold', fn_regular='Roboto-Black.ttf')
        self.max_username = 13
        self.names_gap = 81
        self.words_gap = 210
        self.colors_gap = 80
        self.curr_color = (0, 0, 0)
        self.last_valid_point = None
        # Define boundaries of the drawing area (box)
        self.drawing_area_x1 = 475  # Bottom-left corner x-coordinate
        self.drawing_area_y1 = 130  # Bottom-left corner y-coordinate
        self.drawing_area_x2 = 1407  # Top-right corner x-coordinate
        self.drawing_area_y2 = 757  # Top-right corner y-coordinate
        self.drawing_widget = Widget()
        self.add_widget(self.drawing_widget)
        self.local_draw_data = {}
        self.drawing_canvas = Widget()
        self.green = get_color_from_hex('#2E8B57')
        self.red = get_color_from_hex('#FF0000')
        self.orange = get_color_from_hex('#FFA500')
        self.yellow = get_color_from_hex('#FFFF00')
        self.green_draw = get_color_from_hex('#008000')
        self.blue = get_color_from_hex('#0000FF')
        self.purple = get_color_from_hex('#4B0082')
        self.pink = get_color_from_hex('#8A2BE2')
        self.black = get_color_from_hex('#000000')
        self.white = get_color_from_hex('#FFFFFF')

        self.game_name1 = LockedTextInput(text='', pos=(2, 650), size=(193, 70), readonly=True, size_hint=(None, None),
                                          font_size=21, multiline=False, background_color=(0, 0, 0, 0),
                                          font_name='MyFont')
        self.game_name2 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 1), size=(193, 70), readonly=True,
                                          size_hint=(None, None),font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_name3 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 2), size=(193, 70), readonly=True,
                                          size_hint=(None, None), font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_name4 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 3), size=(193, 70), readonly=True,
                                          size_hint=(None, None), font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_name5 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 4), size=(193, 70), readonly=True,
                                          size_hint=(None, None), font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_name6 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 5), size=(193, 70), readonly=True,
                                          size_hint=(None, None), font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_name7 = LockedTextInput(text='', pos=(2, 650 - self.names_gap * 6), size=(193, 70), readonly=True,
                                          size_hint=(None, None), font_size=21, multiline=False,
                                          background_color=(0, 0, 0, 0), font_name='MyFont')
        self.game_names = [self.game_name1, self.game_name2, self.game_name3, self.game_name4, self.game_name5,
                           self.game_name6, self.game_name7]
        self.word1_button = Button(pos=(610, 360), size=(200, 140), size_hint=(None, None), font_size=35,
                                   font_name='MyFontBold')
        self.word1_button.bind(on_press=self.on_word1_pick)
        self.word2_button = Button(pos=(610 + 1 * self.words_gap, 360), size=(200, 140), size_hint=(None, None),
                                   font_size=35, font_name='MyFontBold')
        self.word2_button.bind(on_press=self.on_word2_pick)
        self.word3_button = Button(pos=(610 + 2 * self.words_gap, 360), size=(200, 140), size_hint=(None, None),
                                   font_size=35, font_name='MyFontBold')
        self.word3_button.bind(on_press=self.on_word3_pick)
        self.words = [self.word1_button, self.word2_button, self.word3_button]
        self.select_word_text = TextInput(readonly=True, pos=(550, 540), size_hint=(None, None), size=(800, 110),
                                          text='Select a secret word to draw!', font_name='MyFontBold',
                                          font_size=60, background_color=(0, 0, 0, 0))
        self.winner = TextInput(readonly=True, size=(1300, 500), pos=(250, 50), font_size=180, size_hint=(None, None),
                                background_color=(0, 0, 0, 0))
        self.draw_time = False
        self.lobby_names_cnt = 0
        self.background = Image(source='graphics/menu.png', allow_stretch=True)  # declaring background image
        self.select = Image(source='graphics/select.png', allow_stretch=True)
        self.create_lobby = Image(source='graphics/create_lobby.png', allow_stretch=True)
        self.join_code = Image(source='graphics/join.png', allow_stretch=True)
        self.draw_bg = Image(source='graphics/art_bg.png', allow_stretch=True)
        self.color_palette = Image(source='graphics/palette.png', allow_stretch=True, size=(925, 100),
                                   size_hint=(None, None), pos=(480, 15))
        self.red_button = Button(size_hint=(None, None), pos=(496, 29), size=(69, 69), opacity=0)
        self.red_button.bind(on_press=self.on_red_button)
        self.orange_button = Button(size_hint=(None, None), pos=(496 + self.colors_gap, 29), size=(69, 69),
                                    opacity=0)
        self.orange_button.bind(on_press=self.on_orange_button)
        self.yellow_button = Button(size_hint=(None, None), pos=(496 + 2 * self.colors_gap, 29), size=(69, 69),
                                    opacity=0)
        self.yellow_button.bind(on_press=self.on_yellow_button)
        self.green_button = Button(size_hint=(None, None), pos=(496 + 3 * self.colors_gap, 29), size=(69, 69),
                                   opacity=0)
        self.green_button.bind(on_press=self.on_green_button)
        self.blue_button = Button(size_hint=(None, None), pos=(496 + 4 * self.colors_gap, 29), size=(69, 69), opacity=0)
        self.blue_button.bind(on_press=self.on_blue_button)
        self.purple_button = Button(size_hint=(None, None), pos=(496 + 5 * self.colors_gap, 29), size=(69, 69),
                                    opacity=0)
        self.purple_button.bind(on_press=self.on_purple_button)
        self.pink_button = Button(size_hint=(None, None), pos=(496 + 6 * self.colors_gap, 29), size=(69, 69), opacity=0)
        self.pink_button.bind(on_press=self.on_pink_button)
        self.black_button = Button(size_hint=(None, None), pos=(496 + 7 * self.colors_gap, 29), size=(69, 69),
                                   opacity=0)
        self.black_button.bind(on_press=self.on_black_button)
        self.colors_buttons = [self.red_button, self.orange_button, self.yellow_button, self.green_button,
                               self.blue_button, self.purple_button, self.pink_button, self.black_button]
        self.eraser = Button(size_hint=(None, None), pos=(1316, 29), size=(69, 69), opacity=0)
        self.eraser.bind(on_press=self.on_erase_button)
        self.clear_draw_tool = Button(size_hint=(None, None), pos=(1316 - self.colors_gap, 29), size=(69, 69),
                                      opacity=0)
        self.clear_draw_tool.bind(on_press=self.on_clear_button)
        self.word_was = TextInput(readonly=True, pos=(600, 320), size=(1000, 200), font_size=75, size_hint=(None, None),
                                  background_color=(0, 0, 0, 0))
        self.join_code_error = Image(source='graphics/code_not.png', allow_stretch=True, size=(700, 85), pos=(400, 130),
                                     size_hint=(None, None))
        self.full = Image(source='graphics/full.png', allow_stretch=True, size=(700, 85), pos=(400, 130),
                          size_hint=(None, None))
        self.winner_bg = Image(source='graphics/winner.png', allow_stretch=True)
        self.signup_error = Image(source='graphics/exists.png', allow_stretch=True, pos=(445, 110), size=(550, 80),
                                  size_hint=(None, None))
        self.signin_error = Image(source='graphics/signin_exists.png', allow_stretch=True, size=(700, 85),
                                  size_hint=(None, None), pos=(360, 110))
        self.lobby = Image(source='graphics/lobby.png', allow_stretch=True)
        self.password_input = TextInput(pos=(729, 315), size=(357, 58), size_hint=(None, None),  # password text box
                                        background_color=(0, 0, 0, 0), font_size=38, multiline=False, scroll_x=1)
        self.guess_input = TextInput(pos=(236, 142), size=(121, 50), size_hint=(None, None),
                                     font_size=21, multiline=False, scroll_x=1, background_color=(1, 1, 1, 0.5))
        self.now_drawing = TextInput(pos=(675, 20), size=(850, 70), multiline=False, scroll_x=1, readonly=True,
                                     text=' is drawing', font_size=40, size_hint=(None, None),
                                     background_color=(0, 0, 0, 0), font_name='MyFontBold')
        self.timer = TextInput(readonly=True, pos=(235, 15), size=(105, 100), size_hint=(None, None),
                               font_size=70, multiline=False, background_color=(0, 0, 0, 0), font_name='MyFontBold')
        self.chat = TextInput(readonly=True, pos=(233, 205), size=(215, 527), size_hint=(None, None), font_size=18,
                              background_color=(0, 0, 0, 0), text='')
        self.username_input = TextInput(pos=(729, 385), size=(357, 58), size_hint=(None, None),  # username text box
                                        background_color=(0, 0, 0, 0), font_size=38, multiline=False, scroll_x=1)
        self.username_input.bind(text=self.on_username_input)
        self.join_code_input = TextInput(pos=(400, 355), size=(530, 70), size_hint=(None, None),
                                         font_size=50, multiline=False, scroll_x=1, background_color=(0, 0, 0, 0))
        self.code_admin = Label(text='', pos=(460, 135), size=(380, 100), size_hint=(None, None), font_size=65,
                                color=(0, 0, 0, 1), font_name='MyFont')
        self.lobby_data = TextInput(text='', pos=(60, 165), size=(1300, 400),
                                    size_hint=(None, None), font_size=65, readonly=True, background_color=(0, 0, 0, 0))
        self.main_word = LockedTextInput(text='The word: ', pos=(650, 754), size=(800, 60), font_size=43,
                                         readonly=True, size_hint=(None, None), background_color=(0, 0, 0, 0),
                                         font_name='MyFontBold')
        self.signup_button = Button(size_hint=(None, None), pos=(432, 215), size=(236, 73), opacity=0)  # sign up button
        self.signup_button.bind(on_press=self.on_signup_button)
        self.signin_button = Button(size_hint=(None, None), pos=(772, 215), size=(236, 73), opacity=0)  # sign in button
        self.signin_button.bind(on_press=self.on_signin_button)
        self.create_button = Button(size_hint=(None, None), pos=(494, 361), size=(430, 85), opacity=0)
        self.create_button.bind(on_press=self.on_create_button)
        self.join_game_button = Button(size_hint=(None, None), pos=(494, 250), size=(430, 85), opacity=0)
        self.join_game_button.bind(on_press=self.on_join_game_button)
        self.join_code_button = Button(size_hint=(None, None), pos=(965, 345), size=(333, 85), opacity=0)
        self.join_code_button.bind(on_press=self.on_join_code_button)
        self.start_button = Button(size_hint=(None, None), pos=(969, 153), size=(237, 78), opacity=0)
        self.start_button.bind(on_press=self.on_start_button)
        self.guess_button = Button(pos=(354, 142), size=(100, 45), size_hint=(None, None), opacity=0)
        self.guess_button.bind(on_press=self.on_guess_button)
        self.add_widget(self.background)
        self.add_widget(self.password_input)
        self.add_widget(self.username_input)
        self.add_widget(self.signup_button)
        self.add_widget(self.signin_button)

    def on_username_input(self, instance, value):
        if len(value) > self.max_username:
            instance.text = value[:self.max_username]

    def on_signup_button(self, instance):
        global sign_up_password
        global sign_up_username
        if self.username_input.text.strip() and self.password_input.text.strip():
            lock.acquire()
            sign_up_username = self.username_input.text.strip().encode()
            sign_up_password = self.password_input.text.strip().encode()
            lock.release()
        else:
            print("pls give username and password before signing up")

    def on_touch_down(self, touch):
        global draw_data
        # Start drawing when the user touches the screen
        if self.draw_time:
            if (self.drawing_area_x1 <= touch.x <= self.drawing_area_x2 and
                    self.drawing_area_y1 <= touch.y <= self.drawing_area_y2):
                with self.canvas:
                    Color(*self.curr_color)  # Set color to red
                    if self.curr_color == self.white:
                        touch.ud['line'] = Line(points=(touch.x, touch.y), width=15)
                    else:
                        touch.ud['line'] = Line(points=(touch.x, touch.y), width=4)
                    draw_data.put_data_send({'step': 'click', 'x': touch.x, 'y': touch.y, 'color': self.curr_color})
                self.last_valid_point = touch.pos  # Update last valid point
                return True
            else:
                return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        global draw_data
        # Continue drawing while the user moves their finger
        if 'line' in touch.ud:
            if self.last_valid_point is not None:
                if (self.drawing_area_x1 <= touch.x <= self.drawing_area_x2 and
                        self.drawing_area_y1 <= touch.y <= self.drawing_area_y2):
                    touch.ud['line'].points += [touch.x, touch.y]
                    draw_data.put_data_send({'step': 'move', 'x': touch.x, 'y': touch.y, 'color': self.curr_color})
                    self.last_valid_point = touch.pos  # Update last valid point
                    return True
                else:
                    del touch.ud['line']
                    self.last_valid_point = None  # Reset last valid point
        return super().on_touch_move(touch)

    def draw_rec(self, data: list[dict]):
        with self.canvas:
            for i in range(len(data)):
                p1 = data[i]
                Color(*p1['color'])
                if p1['step'] == 'click':
                    if p1['color'] == self.white:
                        self.local_draw_data['line'] = Line(points=[p1['x'], p1['y']], width=15)
                    else:
                        self.local_draw_data['line'] = Line(points=[p1['x'], p1['y']], width=4)

                elif p1['step'] == 'move':
                    self.local_draw_data['line'].points += [p1['x'], p1['y']]

    def on_signin_button(self, instance):
        global sign_in_password
        global sign_in_username
        if self.username_input.text.strip() and self.password_input.text.strip():
            lock.acquire()
            sign_in_username = self.username_input.text.strip().encode()
            sign_in_password = self.password_input.text.strip().encode()
            lock.release()
        else:
            print("pls give username and password before signing up")

    def on_create_button(self, instance):
        global create_pressed
        lock.acquire()
        create_pressed = True
        lock.release()

    def on_clear_button(self, instance):
        global clear_pressed
        self.move_to_draw_game()
        self.allow_draw()
        self.add_widget(self.main_word)
        clear_pressed = True

    def on_red_button(self, instance):
        self.curr_color = self.red

    def on_orange_button(self, instance):
        self.curr_color = self.orange

    def on_yellow_button(self, instance):
        self.curr_color = self.yellow

    def on_green_button(self, instance):
        self.curr_color = self.green_draw

    def on_blue_button(self, instance):
        self.curr_color = self.blue

    def on_purple_button(self, instance):
        self.curr_color = self.purple

    def on_pink_button(self, instance):
        self.curr_color = self.pink

    def on_black_button(self, instance):
        self.curr_color = self.black

    def on_erase_button(self, instance):
        self.curr_color = self.white

    def on_word1_pick(self, instance):
        global word
        if word == b'':
            word = self.word1_button.text.encode()

    def on_word2_pick(self, instance):
        global word
        if word == b'':
            word = self.word2_button.text.encode()

    def on_word3_pick(self, instance):
        global word
        if word == b'':
            word = self.word3_button.text.encode()

    def on_guess_button(self, instance):
        global guess
        lock.acquire()
        guess = self.guess_input.text.encode()
        self.guess_input.text = ''
        lock.release()

    def on_join_code_button(self, instance):
        global join_code
        lock.acquire()
        join_code = self.join_code_input.text.encode()
        lock.release()

    def on_join_game_button(self, instance):
        self.move_to_join()

    def on_start_button(self, instance):
        global start_pressed
        lock.acquire()
        start_pressed = True
        lock.release()

    def change_time(self, time: str):
        self.timer.text = time

    def clear_data(self):
        self.username_input.text = ''
        self.password_input.text = ''

    def word_reveal(self, prev_word: str):
        self.word_was.text = f'The word was: \n{prev_word}'
        self.add_widget(self.word_was)

    def add_names_lobby(self, names: list[str]):
        for name in names:
            if self.lobby_names_cnt % 2 == 0:
                self.lobby_data.text += name + '\t\t'
            else:
                self.lobby_data.text += name + '\n'
            self.lobby_names_cnt += 1

    def add_chat(self, username: str, mes: str):
        self.chat.text += f'{username}:  {mes}\n'

    def add_game_names(self, names: list[str]):
        global global_username
        for i in range(len(names)):
            self.game_names[i].text = f'{names[i]}\n0'
            if names[i] == global_username:
                self.game_names[i].font_name = 'MyFontBold'

    def clear_lobby_names(self):
        self.lobby_names_cnt = 0
        self.lobby_data.text = ''

    def signup_exists(self):
        if self.signin_error in self.children:
            self.remove_widget(self.signin_error)
        if self.signup_error not in self.children:
            self.add_widget(self.signup_error)

    def signin_exists(self):
        if self.signup_error in self.children:
            self.remove_widget(self.signup_error)
        if self.signin_error not in self.children:
            self.add_widget(self.signin_error)

    def put_code_admin(self, code: str):
        self.code_admin.text = code
        self.add_widget(self.code_admin)

    def join_code_not_exists(self):
        if self.full in self.children:
            self.remove_widget(self.full)
        if self.join_code_error not in self.children:
            self.add_widget(self.join_code_error)
        self.join_code_input.text = ''

    def full_lobby(self):
        if self.join_code_error in self.children:
            self.remove_widget(self.join_code_error)
        if self.full not in self.children:
            self.add_widget(self.full)
        self.join_code_input.text = ''

    def right_guess(self, username: str, points: str, to_green: bool):
        for name in self.game_names:
            if name.text.startswith(username):
                if name.font_name == 'MyFontBold':
                    self.guess_input.readonly = True
                if to_green:
                    name.foreground_color = self.green
                name.text = username + '\n' + points
                break

    def clear_right_guess(self):
        for name in self.game_names:
            name.foreground_color = (0, 0, 0)

    def move_to_join(self):
        self.clear_widgets()
        self.join_code_input.text = ''
        self.add_widget(self.join_code)
        self.add_widget(self.join_code_input)
        self.add_widget(self.join_code_button)

    def move_to_selection(self):
        self.clear_widgets()
        self.add_widget(self.select)
        self.add_widget(self.create_button)
        self.add_widget(self.join_game_button)
        self.lobby_data.text = ''
        for name in self.game_names:
            name.text = ''
            name.font_name = 'MyFont'

    def move_to_create(self):
        self.clear_widgets()
        self.add_widget(self.create_lobby)
        self.add_widget(self.lobby_data)
        self.add_widget(self.start_button)

    def move_to_lobby(self):
        self.clear_widgets()
        self.add_widget(self.lobby)
        self.add_widget(self.lobby_data)

    def move_to_winner(self, username: str):
        self.clear_widgets()
        self.winner.text = username
        self.add_widget(self.winner_bg)
        self.add_widget(self.winner)

    def allow_draw(self):
        if self.select_word_text in self.children:
            self.remove_widget(self.select_word_text)
        if self.word1_button in self.children:
            self.remove_widget(self.word1_button)
        if self.word2_button in self.children:
            self.remove_widget(self.word2_button)
        if self.word3_button in self.children:
            self.remove_widget(self.word3_button)
        self.draw_time = True
        self.guess_input.text = ''
        self.guess_input.readonly = True
        if self.color_palette not in self.children:
            self.add_widget(self.color_palette)
        if self.now_drawing in self.children:
            self.remove_widget(self.now_drawing)
        for color_button in self.colors_buttons:
            if color_button not in self.children:
                self.add_widget(color_button)
        if self.eraser not in self.children:
            self.add_widget(self.eraser)
        if self.clear_draw_tool not in self.children:
            self.add_widget(self.clear_draw_tool)
        if self.word_was in self.children:
            self.remove_widget(self.word_was)

    def disallow_draw(self):
        self.draw_time = False
        self.guess_input.text = ''
        self.guess_input.readonly = False
        self.main_word.text = 'The word: '
        if self.main_word in self.children:
            self.remove_widget(self.main_word)
        if self.color_palette in self.children:
            self.remove_widget(self.color_palette)

    def pick_word(self, words_s: list[str]):
        self.add_widget(self.select_word_text)
        for i in range(3):
            self.words[i].text = words_s[i]
            self.add_widget(self.words[i])

    def add_secret_word(self, word: str):
        self.main_word.text += word
        self.add_widget(self.main_word)

    def clear_draw(self):
        self.move_to_draw_game()

    def clear_time(self):
        self.timer.text = ''

    def now_draw(self, username: str):
        if self.now_drawing not in self.children:
            self.add_widget(self.now_drawing)
        self.now_drawing.text = username + ' is drawing'
        self.word_was.text = ''
        if self.word_was in self.children:
            self.remove_widget(self.word_was)

    def move_to_draw_game(self):
        self.clear_widgets()
        self.add_widget(self.draw_bg)
        self.add_widget(self.guess_button)
        self.add_widget(self.guess_input)
        self.add_widget(self.chat)
        self.add_widget(self.timer)
        for name in self.game_names:
            self.add_widget(name)

class MainWindow(App):
    def __init__(self, layoutt, stop_event: threading.Event, **kwargs):
        super().__init__(**kwargs)
        self.layout = layoutt
        self.stop_event = stop_event

    def build(self):
        return self.layout

    def on_stop(self):
        self.stop_event.set()
        return True


def logging(bdata: bytes, encrypted_data: bytes, **kwargs):
    direction = kwargs['dir']
    mes = f"\n|{direction}|\tdata -> {bdata}\n|{direction}|\tencrypted -> {encrypted_data}"
    print(mes)


def generate_aes_key() -> bytes:
    """
    :return: random aes 16 bytes key
    """
    return get_random_bytes(16)


def aes_encrypt_cbc(key: bytes, plain_data: bytes) -> tuple:
    """
    encrypt the plain data in AES CBC
    :param key: AES key
    :param plain_data: data to encrypt
    :return: tuple (encrypted_data, iv, both bytes)
    """
    cipher = AES.new(key, AES.MODE_CBC)
    # in AES CBC, to encrypt data, need iv (initialization vector) -  a random sequence of bytes.
    # each block is XORed with the previous block before encryption, and the first block is XORed with the IV
    iv = cipher.iv
    # pad - in AES CBC encryption, the plain_data bytes length has to be a multiple of the block size (here, 16),the
    # padding fill the data to the nearest multiple of block size, each with value equal to the number of bytes to fill
    # EXAMPLE -> block size = 16, data = 'hello world', bytes to fill = 16 - 11 = 5,
    # pad -> 'hello world\x05\x05\x05\x05\x05'
    encrypted_data = cipher.encrypt(pad(plain_data, AES.block_size))
    # when sending encrypted data with AES CBC, need to first send iv and then the encrypted data
    return encrypted_data, iv


def aes_decrypt_cbc(key: bytes, encrypted_data: bytes, iv: bytes) -> bytes:
    """
    decrypt the encrypted data in AES CBC
    :param key: AES key
    :param encrypted_data: data to decrypt
    :param iv: iv of the encrypted data
    :return: plain_data
    """
    decrypt_cipher = AES.new(key, AES.MODE_CBC, iv)  # using the iv to decrypt the first block in decryption
    # if the decrypted data before unpad is a multiple of block size, the unpad removes number of bytes from the
    # last block, the number of bytes to remove is the value of the last byte (before of the padding)
    plain_data = unpad(decrypt_cipher.decrypt(encrypted_data), AES.block_size)
    return plain_data


def keys_swap(sock: socket.socket, aes_key: bytes):
    """
    swap the keys between the client and the server
    :param sock:
    :param aes_key:
    """
    pem_public_key = sock.recv(1024)  # step 1 - server send to client the public RSA key
    rsa_public_key = RSA.import_key(pem_public_key)
    rsa_cipher = PKCS1_OAEP.new(rsa_public_key)
    encrypted_aes_key = rsa_cipher.encrypt(aes_key)
    sock.send(encrypted_aes_key)  # step 2 - client send to server the AES key encrypted with RSA


def sign_up_to_send(username: bytes, password: bytes) -> bytes:
    """
    handle the sign-up, sending the sign-up and password from the kivy to the server
    :return: what to send to the server
    """
    global global_username
    global_username = username.decode()
    return b'SIUP~' + username + b'~' + password


def sign_in_to_send(username: bytes, password: bytes) -> bytes:
    """
    handle the sign-in, sending the sign-in and password from the kivy to the server
    :return: what to send to the server
    """
    global global_username
    global_username = username.decode()
    return b'SIIN~' + username + b'~' + password


def create_to_send() -> bytes:
    """
    handle the create game when pressed, sending the CREA message
    :return: what to send to the server
    """
    return b'CREA'


def join_code_to_send(code: bytes) -> bytes:
    """
    handle the join request when pressed, send the JOIN message with a code
    :return: what to send to the server
    """
    return b'JOIN~' + code


def start_to_send() -> bytes:
    """
    handle the start request when pressed, send the STRT message
    :return: what to send to the server
    """
    return b'STRT'


def guess_to_send(guess_: bytes) -> bytes:
    """
    handle the start guess when pressed, send the GUES message
    :return: what to send to the server
    """
    return b'GUES~' + guess_


def word_to_send(word_: bytes) -> bytes:
    """
    handle the start guess when pressed, send the SWRR message
    :return: what to send to the server
    """
    return b'SWRR~' + word_


def clear_to_send() -> bytes:
    """
    handle the start guess when pressed, send the SWRR message
    :return: what to send to the server
    """
    return b'CLEA'


def server_error_check(bdata: bytes) -> bool:
    """
    check if the message from server is '000' error message or not, return True if yes
    :param bdata:
    """
    if b'ERRR~000' in bdata:
        return True
    return False


def handle_sign_up_response(bdata: bytes, layout: Layout) -> bool:
    if b'ERRR~001' in bdata:
        Clock.schedule_once(lambda dt: layout.clear_data(), 0)
        Clock.schedule_once(lambda dt: layout.signup_exists(), 0)
        print("username already exits")
        return False
    else:
        Clock.schedule_once(lambda dt: layout.move_to_selection(), 0)
        print("signed up successfully")
        return True


def handle_sign_in_response(bdata: bytes, layout: Layout) -> bool:
    if b'ERRR~002' in bdata:
        Clock.schedule_once(lambda dt: layout.clear_data(), 0)
        Clock.schedule_once(lambda dt: layout.signin_exists(), 0)
        print("username and password doesn't exist")
        return False
    else:
        Clock.schedule_once(lambda dt: layout.move_to_selection(), 0)
        print("signed in successfully")
        return True


def handle_draw(sock: socket.socket, aes_key: bytes):
    global draw_data
    global draw_end
    send_lst = []
    send_at_time = 3
    while not draw_end:
        if draw_data.is_to_send():
            send_lst.append(draw_data.get_data_send())
        if len(send_lst) >= send_at_time:
            to_send = b'DRAW~' + json.dumps(send_lst).encode()
            encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
            send_with_size(sock, iv)
            send_with_size(sock, encrypted_to_send)
            logging(to_send, encrypted_to_send, dir='sent')
            send_lst = []
            time.sleep(0.03)


def handle_game(bdata: bytes, layout: Layout):
    global word
    global draw_end
    code = bdata[:4]
    if code == b'GUER':
        sections = bdata.split(b'~')
        Clock.schedule_once(lambda dt: layout.right_guess(sections[1].decode(), sections[2].decode(), True), 0)
        Clock.schedule_once(lambda dt: layout.right_guess(sections[3].decode(), sections[4].decode(), False), 0)
    if code == b'CHAT':
        sections = bdata.split(b'~')
        Clock.schedule_once(lambda dt: layout.add_chat(sections[1].decode(), sections[2].decode()))
    if code == b'SWRD':
        de_data = bdata[5:].decode().split('~')
        Clock.schedule_once(lambda dt: layout.pick_word(de_data), 0)
    if code == b'TIME':
        sections = bdata.split(b'~')
        Clock.schedule_once(lambda dt: layout.change_time(sections[1].decode()), 0)
    if code == b'DRAR':
        data = bdata[5:].decode()
        data_lst = json.loads(data)
        Clock.schedule_once(lambda dt: layout.draw_rec(data_lst), 0)
    if code == b'ENDO':
        sections = bdata.split(b'~')
        Clock.schedule_once(lambda dt: layout.clear_draw(), 0)
        Clock.schedule_once(lambda dt: layout.clear_time(), 0)
        Clock.schedule_once(lambda dt: layout.disallow_draw(), 0)
        Clock.schedule_once(lambda dt: layout.clear_right_guess(), 0)
        Clock.schedule_once(lambda dt: layout.word_reveal(sections[2].decode()), 0)
        time.sleep(5)
        Clock.schedule_once(lambda dt: layout.now_draw(sections[1].decode()), 0)
    if code == b'CLER':
        Clock.schedule_once(lambda dt: layout.clear_draw(), 0)
    if code == b'ENDG':
        sections = bdata.split(b'~')
        Clock.schedule_once(lambda dt: layout.move_to_winner(sections[1].decode()), 0)
    if code == b'ERRR':
        sections = bdata.split(b'~')
        if sections[1] == b'006':
            draw_end = True
            Clock.schedule_once(lambda dt: layout.move_to_selection(), 0)
            return True


def comm_game(layout: Layout, sock: socket.socket, aes_key: bytes):
    global guess
    global word
    global clear_pressed
    global draw_end
    finish = False
    print("MOVE TO GAME")
    draw_end = False
    draw_thread = threading.Thread(target=handle_draw, args=(sock, aes_key))
    draw_thread.start()
    while not finish:
        try:
            #  if async message came - read and manage it
            ready, _, _ = select.select([sock], [], [], 0.1)
            if ready:
                iv = recv_by_size(sock)
                encrypted_data = recv_by_size(sock)
                bdata = aes_decrypt_cbc(aes_key, encrypted_data, iv)
                logging(bdata, encrypted_data, dir='received')
                finish = server_error_check(bdata)
                if not finish:
                    finish = handle_game(bdata, layout)
                    ready, _, _ = select.select([sock], [], [], 0.1)
            if guess:
                lock.acquire()
                guess_ = guess
                guess = b''
                lock.release()
                to_send = guess_to_send(guess_)
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
            if word:
                lock.acquire()
                word_ = word
                word = b''
                lock.release()
                to_send = word_to_send(word_)
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
                Clock.schedule_once(lambda dt: layout.allow_draw(), 0)
                Clock.schedule_once(lambda dt: layout.add_secret_word(word_.decode()), 0)
            if clear_pressed:
                lock.acquire()
                clear_pressed = False
                lock.release()
                to_send = clear_to_send()
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')

        except socket.error as err:
            print(f"Socket error, client disconnecting\n{err}")
            return True
        except Exception as err:
            print(f"General error, client disconnecting\n{err}")
            return True


def handle_create_join(bdata: bytes, layout: Layout):
    code = bdata[:4]
    if code == b'JOIR':
        sections = bdata.split(b'~')
        if sections[0] == b'JOIR':
            Clock.schedule_once(lambda dt: layout.move_to_lobby(), 0)
            print("joined the lobby")
    if code == b'CRER':
        sections = bdata.split(b'~')
        if b'CRER' == sections[0]:
            Clock.schedule_once(lambda dt: layout.move_to_create(), 0)
            Clock.schedule_once(lambda dt: layout.put_code_admin(sections[1].decode()), 0)
            Clock.schedule_once(lambda dt: layout.add_names_lobby([sections[2].decode()]), 0)
            print("moved to the lobby")
        else:
            print("ERROR!")
    if code == b'LOBD':
        de_bdata = bdata[5:].decode()
        usernames = de_bdata.split('~')
        Clock.schedule_once(lambda dt: layout.clear_lobby_names(), 0)
        Clock.schedule_once(lambda dt: layout.add_names_lobby(usernames), 0)
    if code == b'STRR':
        de_bdata = bdata[5:].decode()
        usernames = de_bdata.split('~')
        Clock.schedule_once(lambda dt: layout.move_to_draw_game(), 0)
        Clock.schedule_once(lambda dt: layout.add_game_names(usernames), 0)
        Clock.schedule_once(lambda dt: layout.now_draw(usernames[0]), 0)
    if code == b'ERRR':
        sections = bdata.split(b'~')
        if sections[1] == b'005':
            return True
        if sections[1] == b'003':
            Clock.schedule_once(lambda dt: layout.join_code_not_exists(), 0)
        if sections[1] == b'004':
            Clock.schedule_once(lambda dt: layout.full_lobby(), 0)
        if sections[1] == b'007':
            print("cant open a game alone")



def comm_create_join(layout: Layout, sock: socket.socket, aes_key: bytes):
    """
    execute all the communication between the server and the client, in the lobbies screens
    If a server error occurred, get back to the last screen
    """
    global create_pressed
    global join_code
    global start_pressed
    finish = False
    while not finish:
        try:
            #  if async message came - read and manage it
            ready, _, _ = select.select([sock], [], [], 0.1)
            if ready:
                iv = recv_by_size(sock)
                encrypted_data = recv_by_size(sock)
                bdata = aes_decrypt_cbc(aes_key, encrypted_data, iv)
                logging(bdata, encrypted_data, dir='received')
                finish = server_error_check(bdata)
                if not finish:
                    if handle_create_join(bdata, layout):
                        finish = True
                    if bdata.startswith(b'STRR'):
                        comm_game(layout, sock, aes_key)
                    ready, _, _ = select.select([sock], [], [], 0.1)
            # when the create button in the selection screen is pressed, send a request to create a lobby
            if create_pressed:
                lock.acquire()
                create_pressed = False
                lock.release()
                to_send = create_to_send()
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
            # when the join button in the join code screen is pressed, send a request to join a lobby
            if join_code:
                lock.acquire()
                code = join_code
                join_code = b''
                lock.release()
                to_send = join_code_to_send(code)
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
            if start_pressed:
                lock.acquire()
                start_pressed = False
                lock.release()
                to_send = start_to_send()
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
        except socket.error as err:
            print(f"Socket error, client disconnecting\n{err}")
            return True
        except Exception as err:
            print(f"General error, client disconnecting\n{err}")
            return True
    return False


def comm_menu(sock: socket.socket, aes_key: bytes, layout: Layout):
    """
    execute all the communication between the server and the client, in the main menu screen
    """
    global sign_up_password
    global sign_up_username
    global sign_in_password
    global sign_in_username
    finish = False
    while not finish:
        try:
            if sign_up_username and sign_up_password:  # if the sign-up button is pressed and the data is given
                lock.acquire()
                to_send = sign_up_to_send(sign_up_username, sign_up_password)
                sign_up_username = b''
                sign_up_password = b''
                lock.release()
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
                iv = recv_by_size(sock)
                encrypted_data = recv_by_size(sock)
                bdata = aes_decrypt_cbc(aes_key, encrypted_data, iv)
                logging(bdata, encrypted_data, dir='received')
                finish = server_error_check(bdata)
                if not finish:
                    if handle_sign_up_response(bdata, layout):
                        finish = comm_create_join(layout, sock, aes_key)
                        Clock.schedule_once(lambda dt: layout.move_to_selection(), 0)
            if sign_in_username and sign_in_password:  # if the sign-in button is pressed and the data is given
                lock.acquire()
                to_send = sign_in_to_send(sign_in_username, sign_in_password)
                sign_in_username = b''
                sign_in_password = b''
                lock.release()
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(sock, iv)
                send_with_size(sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')
                iv = recv_by_size(sock)
                encrypted_data = recv_by_size(sock)
                bdata = aes_decrypt_cbc(aes_key, encrypted_data, iv)
                logging(bdata, encrypted_data, dir='received')
                finish = server_error_check(bdata)
                if not finish:
                    if handle_sign_in_response(bdata, layout):
                        finish = comm_create_join(layout, sock, aes_key)
                        Clock.schedule_once(lambda dt: layout.move_to_selection(), 0)
        except socket.error as err:
            print(f"Socket error, client disconnecting\n{err}")
            finish = True
        except Exception as err:
            print(f"General error, client disconnecting\n{err}")
            finish = True


def main(ip):
    sock = socket.socket()
    port = 1233
    sock.connect((ip, port))
    print(f"Connect succeeded -> {ip} | {port}")
    aes_key = generate_aes_key()
    keys_swap(sock, aes_key)
    print(f"AES key -> {aes_key}")
    layout = Layout()
    stop_event = threading.Event()
    main_window = MainWindow(layoutt=layout, stop_event=stop_event)
    comm_thread = threading.Thread(target=comm_menu, args=(sock, aes_key, layout))
    comm_thread.daemon = True
    comm_thread.start()
    main_window.run()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Didn't get an ip argument. proceeding with the default ip")
        main(DEFAULT_IP)
