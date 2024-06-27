import socket
import select
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import os
import threading
import time
import sys
import hashlib
from tcp_by_size import send_with_size, recv_by_size
import pickle
from Crypto.Random import get_random_bytes
import random
from queue import Queue


clients_cnt = 0
MAX_CLIENTS = 100
MAX_LOBBY_PLAYERS = 7
TIME_SEC = 99
ROUNDS = 2
POINTS_PER_GUESS = [60, 50, 40, 30]
POINTS_PRE_DRAW = 15
lock = threading.Lock()
pepper = b''
words = []
connected_users = {}  # {sock: username}
lobby_codes = {}  # {code: [sock...]}
lobby_admins = {}  # {sock: code}
game_sock_word = {}  # {sock: word}
game_id_sock_lst = {}  # {game_id: [sock]}
game_sock_id = {}  # {sock: game_id}
game_sock_points = {}  # {sock: points}
timer_manage = {}  # {id: time}
game_sock_guess = {}  # {sock: bool}
game_id_cnt = {}  # {game_id: cnt}


class AsyncManager:
    def __init__(self):
        self.dic = {}  # {sock: [bdata, bdata...]}

    def put_message(self, sock: socket.socket, bdata: bytes):
        if sock in self.dic:
            self.dic[sock].put(bdata)
            return
        self.dic[sock] = Queue()
        self.dic[sock].put(bdata)

    def get_message(self, sock: socket.socket) -> bytes:
        if sock not in self.dic:
            return b''
        if self.dic[sock].empty():
            return b''
        return self.dic[sock].get()

    def is_to_send(self, sock: socket.socket):
        if sock not in self.dic:
            return False
        if self.dic[sock].empty():
            return False
        return True


async_manager = AsyncManager()


def logging(bdata: bytes, encrypted_data: bytes, **kwargs):
    direction = kwargs['dir']
    mes = f"\n|{direction}|\tdata -> {bdata}\n|{direction}|\tencrypted -> {encrypted_data}"
    print(mes)


def gen_rsa_keys() -> tuple:
    """
    both the private key and the public key
    :return: tuple (public key, private key, both in RsaKey format)
    """
    private_key = RSA.generate(2048)
    public_key = private_key.public_key()
    return private_key, public_key


def save_rsa_key(private_key: RSA.RsaKey, public_key: RSA.RsaKey):
    """
    saves both the RsaKeys in pem format in pem files, each key in a separate file
    :param private_key:
    :param public_key:
    """
    with open('private_key.pem', 'wb') as f:
        f.write(private_key.export_key())
    with open('public_key.pem', 'wb') as f:
        f.write(public_key.export_key())


def get_saved_rsa_keys() -> tuple:
    """
    get both the private and public rsa keys in pem format from their relatives pem files.
    """
    with open('private_key.pem', 'rb') as f:
        pem_private_key = f.read()
    with open('public_key.pem', 'rb') as f:
        pem_public_key = f.read()
    return pem_private_key, pem_public_key


def is_valid_rsa(pem_key: bytes) -> bool:
    """
    check if a PEM format RSA key is valid or not
    :param pem_key:
    :return: bool
    """
    try:
        RSA.import_key(pem_key)
        return True
    except ValueError:
        return False


def aes_encrypt_cbc(key: bytes, plain_data: bytes) -> tuple:
    """
    encrypt the plain data in AES CBC
    :param key: AES key
    :param plain_data: data to encrypt
    :return: tuple (encrypted_data, iv, both bytes)
    """
    cipher = AES.new(key, AES.MODE_CBC)
    # in AES CBC, to encrypt data, need iv (initialization vector) - a random sequence of bytes.
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


def keys_swap(cli_sock: socket.socket, pem_public_key: bytes, rsa_cipher: PKCS1_OAEP.PKCS1OAEP_Cipher) -> bytes:
    """
    execute the keys swap communication in the start with the client
    """
    cli_sock.send(pem_public_key)  # step 1 - server send to client the public rsa key
    encrypted_aes_key = cli_sock.recv(1024)  # step 2 - client send to server the AES key encrypted with RSA
    aes_key = rsa_cipher.decrypt(encrypted_aes_key)
    return aes_key


def generate_game_code() -> bytes:
    """
    get a random game code
    """
    global lobby_codes
    # a cnt to counter how many times the server tried to generate a game code, if tried X times, stop and send an error
    cnt = 0
    lock.acquire()
    while True:
        cnt += 1
        code = str(random.randint(0, 9999999)).zfill(7)
        code = code.encode()
        if code not in lobby_codes:
            lock.release()
            return code
        if cnt >= 1000:
            lock.release()
            return b'ERROR'


def generate_game_id() -> bytes:
    global game_id_sock_lst
    while True:
        game_id = str(random.randint(0, 9999999)).encode()
        if game_id not in game_id_sock_lst:
            break
    return game_id


def sign_in(username: bytes, password: bytes, cli_sock: socket.socket) -> bytes:
    """
    checks if the username and the password combination is in the pickle file, return the answer to the
    sign in
    """
    global connected_users
    global pepper
    if not os.path.exists('users.pkl'):
        to_send = b'ERRR~002~username and password doesnt exist'
    else:
        lock.acquire()
        try:
            with open('users.pkl', 'rb') as f:
                loaded_users = pickle.load(f)  # dic {username: (hashed_password, salt)}
        except EOFError:
            print("Empty pickle file")
            lock.release()
            return b'ERRR~000~SERVER ERROR'
        except Exception as err:
            print(f"error while pickling signing in\n{err}")
            lock.release()
            return b'ERRR~000~SERVER ERROR'
        lock.release()
        if type(loaded_users) == dict:  # if the loaded data is a dic
            if username in loaded_users:  # if the username is a key in the dic
                hashed_password, salt = loaded_users[username]  # dic {username: (hashed_password, salt)}
                # if the hash of password + pepper + given salt == the hashed password in the dic
                if hashlib.sha256(password + salt + pepper).hexdigest() == hashed_password:
                    if username not in connected_users.values():  # if the user is not already connected
                        to_send = b'SIIR~success'  # correct
                    else:
                        to_send = b'ERRR~002~username and password doesnt exist'
                else:
                    to_send = b'ERRR~002~username and password doesnt exist'
            else:
                to_send = b'ERRR~002~username and password doesnt exist'
        else:
            print("WRONG PICKLE DATA")
            return b'ERRR~000~SERVER ERROR'
    if to_send[:4] == b'SIIR':
        lock.acquire()
        connected_users[cli_sock] = username  # register the username in the connected users dic
        lock.release()
    return to_send


def sign_up(username: bytes, password: bytes, cli_sock: socket.socket) -> bytes:
    """
    checks if the username is already exits in the users database, if not, signs up the user in the pickle,
    in this dictionary format -> { username: (hashed password + salt + pepper, salt) }
    """
    global pepper
    global connected_users
    salt = get_random_bytes(18)
    hashed_password = hashlib.sha256(password + salt + pepper).hexdigest()
    user = {username: (hashed_password, salt)}
    if not os.path.exists('users.pkl'):  # if the pickle file not exists, create one and sign up
        lock.acquire()
        try:
            with open('users.pkl', 'wb') as f:
                pickle.dump(user, f)
            to_send = b'SIUR~success'
        except Exception as err:
            print(f"error while pickling signing up\n{err}")
            lock.release()
            return b'ERRR~000~SERVER ERROR'
        lock.release()
    else:
        lock.acquire()
        try:
            with open('users.pkl', 'rb') as f:
                loaded_users = pickle.load(f)
        except EOFError:
            print("Empty pickle file")
            lock.release()
            return b'ERRR~000~SERVER ERROR'
        except Exception as err:
            print(f"error while pickling signing up\n{err}")
            lock.release()
            return b'ERRR~000~SERVER ERROR'
        lock.release()
        if type(loaded_users) == dict:
            if username in loaded_users:
                to_send = b'ERRR~001~username already exists'
            else:
                updated_users = {**loaded_users, **user}
                lock.acquire()
                try:
                    with open('users.pkl', 'wb') as f:
                        pickle.dump(updated_users, f)
                except Exception as err:
                    print(f"error while pickling signing up\n{err}")
                    lock.release()
                    return b'ERRR~000~SERVER ERROR'
                lock.release()
                to_send = b'SIUR~success'
        else:
            print("WRONG PICKLE DATA")
            return b'ERRR~000~SERVER ERROR'
    if to_send[:4] == b'SIUR':
        lock.acquire()
        connected_users[cli_sock] = username  # register the username in the connected users dic
        lock.release()
    return to_send


def create(cli_sock: socket.socket) -> bytes:
    """
    handle the response for the CREA message
    """
    global lobby_codes
    global connected_users
    global lobby_admins
    code = generate_game_code()
    if code == b'ERROR':
        to_send = b'ERRR~000'
    else:
        lock.acquire()
        lobby_codes[code] = [cli_sock]  # sign up the code in the dic, with the socket of the admin
        lobby_admins[cli_sock] = code
        lock.release()
        to_send = b'CRER~' + code + b'~' + connected_users[cli_sock]
    return to_send


def join(code: bytes, cli_sock: socket.socket) -> bytes:
    global lobby_codes
    lock.acquire()
    if code not in lobby_codes:
        lock.release()
        return b'ERRR~003~code game doesnt exist'
    if len(lobby_codes[code]) > MAX_LOBBY_PLAYERS:
        lock.release()
        return b'ERRR~004~the game is full'
    lobby_codes[code].append(cli_sock)
    lock.release()
    return b'JOIR~success'


def lobby_data(code: bytes):
    global lobby_codes
    global connected_users
    to_send = b'LOBD'
    lock.acquire()
    if lobby_codes[code][0] == 'END':
        lobby_codes[code].remove('END')
        lock.release()
        return lobby_codes[code], b'ERRR~005~lobby closed'
    for sock in lobby_codes[code]:
        to_send += b'~' + connected_users[sock]  # get the username by the socket
    lock.release()
    return lobby_codes[code], to_send


def start_game(cli_sock: socket.socket):
    global lobby_admins
    global lobby_codes
    global game_sock_word
    global game_sock_id
    global game_sock_points
    global game_id_sock_lst
    global game_id_cnt
    to_send = b'STRR'
    lock.acquire()
    if cli_sock not in lobby_admins:
        lock.release()
        return lobby_codes[lobby_admins[cli_sock]], b'ERRR~000~not admin tried to start the game'
    if len(lobby_codes[lobby_admins[cli_sock]]) < 2:
        lock.release()
        return [cli_sock], b'ERRR~007~not enough players to start the game'
    for sock in lobby_codes[lobby_admins[cli_sock]]:
        to_send += b'~' + connected_users[sock]
    sock_list = lobby_codes[lobby_admins[cli_sock]]  # save the sock list of the game before deleting
    del lobby_codes[lobby_admins[cli_sock]]
    del lobby_admins[cli_sock]
    game_id = generate_game_id()
    game_id_sock_lst[game_id] = sock_list  # a dic to get sock list by game id
    for sock in game_id_sock_lst[game_id]:
        game_sock_word[sock] = b''  # a dic to get word by sock
        game_sock_id[sock] = game_id  # a dic to get id by sock
        game_sock_points[sock] = 0  # a dic to get points by sock
        game_sock_guess[sock] = False
    game_id_cnt[game_id] = 0
    lock.release()
    return sock_list, to_send


def get_points_guess(sec: int):
    if sec > 0.9 * TIME_SEC:
        return POINTS_PER_GUESS[0]
    elif sec > 0.8 * TIME_SEC:
        return POINTS_PER_GUESS[1]
    elif sec > 0.7 * TIME_SEC:
        return POINTS_PER_GUESS[2]
    return POINTS_PER_GUESS[3]


def guess_check(guess: bytes, cli_sock: socket.socket):
    global connected_users
    global game_sock_word
    global game_sock_id
    global game_sock_points
    global timer_manage
    lock.acquire()
    game_id = game_sock_id[cli_sock]  # get the game id by the socket
    sock_list = game_id_sock_lst[game_id]  # who to send to (everybody in the game id)
    for sock in game_id_sock_lst[game_id]:  # go by every socket to get every word, in socket list got by game id
        if game_sock_word[sock] != b'':  # if the word got by socket, is not b'' (the player is drawing)
            if guess.lower() != game_sock_word[sock].lower():  # if the guess is the right word
                lock.release()
                return sock_list, b'CHAT~' + connected_users[cli_sock] + b'~' + guess
            else:
                game_sock_points[cli_sock] += get_points_guess(timer_manage[game_id])  # add points
                game_sock_points[sock] += POINTS_PRE_DRAW
                game_sock_guess[cli_sock] = True
                if end_guess_check(game_id):
                    timer_manage[game_id] = -100
                lock.release()
                return (sock_list, b'GUER~' + connected_users[cli_sock] + b'~' +
                        str(game_sock_points[cli_sock]).encode() + b'~' + connected_users[sock] + b'~' +
                        str(game_sock_points[sock]).encode())
    sock_list = game_id_sock_lst[game_id]
    return sock_list, b'CHAT~' + connected_users[cli_sock] + b'~' + guess


def end_guess_check(game_id: bytes):
    cnt = 0
    for sock in game_id_sock_lst[game_id]:
        if not game_sock_guess[sock]:
            cnt += 1
            if cnt > 1:
                return False
    return True


def get_next_word_sock(game_id: bytes):
    global game_sock_word
    global game_id_sock_lst
    sock_list = game_id_sock_lst[game_id]
    for i in range(len(sock_list) - 1):
        if game_sock_word[sock_list[i]] != b'':
            word_ = game_sock_word[sock_list[i]]
            game_sock_word[sock_list[i]] = b''
            sock_to_send = sock_list[i+1]
            return sock_to_send, word_
    word_ = game_sock_word[sock_list[len(sock_list) - 1]]
    game_sock_word[sock_list[len(sock_list) - 1]] = b''
    return sock_list[0], word_


def put_secret_word(word: bytes, cli_sock: socket.socket):
    global game_sock_word
    game_sock_word[cli_sock] = word


def secret_word_generator():
    global words
    while True:
        word1 = words[random.randint(0, len(words) - 1)].encode()
        word2 = words[random.randint(0, len(words) - 1)].encode()
        word3 = words[random.randint(0, len(words) - 1)].encode()
        if word2 != word3 and word2 != word1 and word3 != word1:
            break
    return word1, word2, word3


def secret_word_mes(cli_sock):
    word1, word2, word3 = secret_word_generator()
    return [cli_sock], b'SWRD~' + word1 + b'~' + word2 + b'~' + word3


def put_message_to_sock_list(sock_list: list[socket.socket], to_put):
    global async_manager
    for sock in sock_list:
        async_manager.put_message(sock, to_put)


def draw(bdata: bytes, cli_sock: socket.socket):
    global game_sock_id
    global game_id_sock_lst
    sock_list = []
    for sock in game_id_sock_lst[game_sock_id[cli_sock]]:
        if sock != cli_sock:
            sock_list.append(sock)
    return sock_list, b'DRAR~' + bdata


def new_round(next_sock: socket.socket, word_: bytes):
    global game_sock_id
    global game_id_sock_lst
    game_id = game_sock_id[next_sock]
    sock_list = game_id_sock_lst[game_id]
    for sock in sock_list:
        game_sock_guess[sock] = False
    username = connected_users[next_sock]
    return sock_list, b'ENDO~' + username + b'~' + word_


def clear(cli_sock: socket.socket):
    global game_sock_id
    global game_id_sock_lst
    sock_list = []
    for sock in game_id_sock_lst[game_sock_id[cli_sock]]:
        if sock != cli_sock:
            sock_list.append(sock)
    return sock_list, b'CLER'


def end_game(game_id: bytes):
    global game_id_sock_lst
    sock_list = game_id_sock_lst[game_id]
    max_points = 0
    max_sock = sock_list[0]
    for sock in sock_list:
        if game_sock_points[sock] > max_points:
            max_points = game_sock_points[sock]
            max_sock = sock
    return sock_list, b'ENDG~' + connected_users[max_sock]


def exit_game(game_id: bytes, cli_sock: socket.socket):
    sock_list = []
    for sock in game_id_sock_lst[game_id]:
        if sock != cli_sock:
            sock_list.append(sock)
    return sock_list, b'ERRR~006~game finished early'


def delete_game(game_id: bytes):
    global game_sock_points
    global game_sock_guess
    global game_sock_word
    if game_id in game_id_sock_lst:
        for sock in game_id_sock_lst[game_id]:
            game_sock_points[sock] = 0
            game_sock_guess[sock] = False
            game_sock_word[sock] = b''
            if sock in game_sock_id:
                del game_sock_id[sock]
        del game_id_sock_lst[game_id]
    if game_id in game_id_cnt:
        del game_id_cnt[game_id]


def handle_timer(cli_sock: socket.socket):
    global game_id_sock_lst
    global game_sock_id
    global timer_manage
    global game_id_cnt
    game_id = game_sock_id[cli_sock]
    sock_list = game_id_sock_lst[game_id]
    timer_manage[game_id] = TIME_SEC
    while timer_manage[game_id] >= 0:
        if cli_sock not in connected_users:
            return
        to_send = b'TIME~' + str(timer_manage[game_id]).encode()
        put_message_to_sock_list(sock_list, to_send)
        time.sleep(1)
        timer_manage[game_id] -= 1
    game_id_cnt[game_id] += 1
    if game_id_cnt[game_id] >= ROUNDS * len(sock_list):
        sock_list, to_put = end_game(game_id)
        put_message_to_sock_list(sock_list, to_put)
        return
    next_sock, word_ = get_next_word_sock(game_id)
    sock_list, to_put = new_round(next_sock, word_)
    put_message_to_sock_list(sock_list, to_put)
    time.sleep(5)
    sock_list, to_put = secret_word_mes(next_sock)
    put_message_to_sock_list(sock_list, to_put)


def handle_req(bdata: bytes, cli_sock: socket.socket):
    """
    handle to who and what to send, by the message data and the message code
    """
    finish = False
    if bdata == b'':
        finish = True
    sections = bdata.split(b'~')
    code = sections[0]
    if code == b'SIUP':
        to_send = sign_up(sections[1], sections[2], cli_sock)
    elif code == b'SIIN':
        to_send = sign_in(sections[1], sections[2], cli_sock)
    elif code == b'CREA':
        to_send = create(cli_sock)
    elif code == b'JOIN':
        to_send = join(sections[1], cli_sock)
        if to_send.startswith(b'JOIR'):
            sock_list, to_put = lobby_data(sections[1])
            put_message_to_sock_list(sock_list, to_put)
    elif code == b'STRT':
        sock_list, to_put = start_game(cli_sock)
        put_message_to_sock_list(sock_list, to_put)
        if to_put.startswith(b'STRR'):
            sock_list, to_put = secret_word_mes(cli_sock)
            put_message_to_sock_list(sock_list, to_put)
        to_send = b''
    elif code == b'SWRR':
        put_secret_word(sections[1], cli_sock)
        timer_t = threading.Thread(target=handle_timer, args=(cli_sock,))
        timer_t.start()
        to_send = b''
    elif code == b'GUES':
        sock_list, to_put = guess_check(sections[1], cli_sock)
        put_message_to_sock_list(sock_list, to_put)
        to_send = b''
    elif code == b'DRAW':
        sock_list, to_put = draw(sections[1], cli_sock)
        put_message_to_sock_list(sock_list, to_put)
        to_send = b''
    elif code == b'CLEA':
        sock_list, to_put = clear(cli_sock)
        put_message_to_sock_list(sock_list, to_put)
        to_send = b''
    else:
        to_send = b'ERRR~000~CODE ERROR'
    if b'ERRR~000' in to_send:
        finish = True
    return to_send, finish


def handle_client(cli_sock: socket.socket, address, pem_public_key: bytes, rsa_cipher: PKCS1_OAEP.PKCS1OAEP_Cipher):
    """
    The main handle client, handle the communication. checking with the 'select' if a message is ready to be received,
    if not, check if a message is ready to be sent checking with the 'async_manager' class
    """
    global clients_cnt
    global connected_users
    global async_manager
    global lobby_codes
    global lobby_admins
    print(f"Got client {address}")
    aes_key = keys_swap(cli_sock, pem_public_key, rsa_cipher)
    print(f"AES key -> {aes_key}")
    finish = False
    while not finish:
        try:
            ready_sock_list, _, _ = select.select([cli_sock], [], [], 0.1)
            if ready_sock_list:  # if a message is ready to be received
                iv = recv_by_size(cli_sock)  # receive the iv
                encrypted_data = recv_by_size(cli_sock)  # receive the encrypted data
                bdata = aes_decrypt_cbc(aes_key, encrypted_data, iv)  # decrypt
                logging(bdata, encrypted_data, dir='received')
                to_send, finish = handle_req(bdata, cli_sock)  # get what to send by the handle request method
                if to_send != b'':
                    encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)  # encrypt
                    send_with_size(cli_sock, iv)  # send iv
                    send_with_size(cli_sock, encrypted_to_send)  # send the encrypted data
                    logging(to_send, encrypted_to_send, dir='sent')

            while async_manager.is_to_send(cli_sock):
                to_send = async_manager.get_message(cli_sock)
                encrypted_to_send, iv = aes_encrypt_cbc(aes_key, to_send)
                send_with_size(cli_sock, iv)
                send_with_size(cli_sock, encrypted_to_send)
                logging(to_send, encrypted_to_send, dir='sent')

        except socket.error as err:
            print(f"Socket error, disconnecting the client\n{err}")
            finish = True
        except Exception as err:
            print(f"General error, disconnecting the client\n{err}")
            finish = True
    lock.acquire()
    clients_cnt -= 1
    if cli_sock in connected_users:
        del connected_users[cli_sock]  # remove the socket from the connected users dic
    if cli_sock in game_sock_id:
        sock_list, to_put = exit_game(game_sock_id[cli_sock], cli_sock)
        put_message_to_sock_list(sock_list, to_put)
        delete_game(game_sock_id[cli_sock])
    for code in lobby_codes:
        if cli_sock in lobby_codes[code]:
            if cli_sock in lobby_admins:
                lobby_codes[code][0] = 'END'
                del lobby_admins[cli_sock]
            else:
                lobby_codes[code].remove(cli_sock)
            lock.release()
            code_sock_list, to_put = lobby_data(code)
            lock.acquire()
            put_message_to_sock_list(code_sock_list, to_put)
            break
    lock.release()
    cli_sock.close()
    print("client disconnected")


def main():
    global pepper
    global clients_cnt
    global words
    # if none RSA keys generated so far, generate them and save them in PEM files
    try:
        if not os.path.exists('private_key.pem'):
            private_key, public_key = gen_rsa_keys()
            save_rsa_key(private_key, public_key)
        # get the RSA keys from the PEM files, in pem format
        pem_private_key, pem_public_key = get_saved_rsa_keys()
        # check if the keys are valid or not, if not, generate
        if not is_valid_rsa(pem_private_key) or not is_valid_rsa(pem_public_key):
            private_key, public_key = gen_rsa_keys()
            save_rsa_key(private_key, public_key)
            pem_private_key, pem_public_key = get_saved_rsa_keys()
        rsa_cipher = PKCS1_OAEP.new(RSA.import_key(pem_private_key))
        print("\nServer has RSA keys")
    except Exception as err:
        print(f"ERROR WHILE GETTING THE RSA KEYS\n{err}\nServer shut down...")
        sys.exit()

    try:
        if not os.path.exists('pepper.txt'):
            print("PEPPER FILE DOESN'T EXIST! pls tell to the server admin\nServer shut down...")
            sys.exit()
        else:
            with open('pepper.txt', 'rb') as f:
                pepper = f.read()
            print('server has pepper')
    except Exception as err:
        print(f'ERROR WHILE GETTING THE PEPPER\n{err}\nServer shut down...')
        sys.exit()

    try:
        if not os.path.exists('words.txt'):
            print("WORDS FILE DOESN'T EXIST! pls tell to the server admin\nServer shut down...")
            sys.exit()
        else:
            with open('words.txt', 'r') as f:
                words = f.read()
            print('server has pepper')
    except Exception as err:
        print(f'ERROR WHILE GETTING THE PEPPER\n{err}\nServer shut down...')
        sys.exit()
    words = words.split(',')
    for i in range(len(words)):
        words[i] = words[i].strip()

    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket
    srv_sock.bind(('0.0.0.0', 1233))
    srv_sock.listen(50)
    threads = []
    finish = False
    while not finish:
        print("\nMain Thread: before accepting ...")
        cli_sock, address = srv_sock.accept()
        t = threading.Thread(target=handle_client, args=(cli_sock, address, pem_public_key, rsa_cipher))
        t.start()
        threads.append(t)
        lock.acquire()
        clients_cnt += 1
        if clients_cnt >= MAX_CLIENTS:
            finish = True
        lock.release()

    print("TOO MUCH CLIENTS\nServer shut down...")
    for t in threads:
        t.join()
    srv_sock.close()


if __name__ == '__main__':
    main()
