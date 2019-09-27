from util import *
import socketserver
import secrets
import hashlib
import sys
import traceback
import logging

logging.basicConfig(level=logging.INFO)

# server settings
AES_KEY = os.urandom(16)
HMAC_KEY = os.urandom(32)
DIFFICULTY = 18
TIMEOUT = 120

MENU = '''
   ___            __  
  / _ )___ ____  / /__
 / _  / _ `/ _ \/  '_/
/____/\_,_/_//_/_/\_\ 

1. Create a game account
2. Deploy a game contract
3. Request for flag
4. Get game contract source code

Game environment: Ropsten testnet

'''
TOPIC = 'SendFlag'

# get contract source and interface
with open('/app/sample.sol', 'r') as f:
    SRC_TEXT = f.read()
CONT_IF = compile_from_src(SRC_TEXT.replace('RN', '0'))

with open('/app/flag.txt', 'r') as f:
    FLAG = f.read()

def PoW(self):
    # PoW challenge
    prefix = secrets.token_urlsafe(16)
    self.request.sendall(f'sha256({prefix} + ???) == {"0"*DIFFICULTY}({DIFFICULTY})...\n'.encode())
    self.request.sendall('??? = '.encode())
    pow_answer = self.request.recv(1024).strip()

    # check PoW answer
    h = hashlib.sha256()
    h.update(prefix.encode() + pow_answer)
    bits = ''.join(bin(i)[2:].zfill(8) for i in h.digest())
    zeros = '0' * DIFFICULTY
    if bits[:DIFFICULTY] != zeros:
        exit()

def challenge(self):
    # get player's choice
    self.request.sendall(MENU.encode())
    self.request.sendall('Your choice: '.encode())
    ch = self.request.recv(1024).strip()
    ch = int(ch)

    if ch == 1:
        # create game account
        acct = create_game_account()
        self.request.sendall(f'Your game account: {acct.address}\n'.encode())

        # generate token
        data = acct.address.encode() + acct.key
        token = encrypt_then_mac(data, AES_KEY, HMAC_KEY)
        self.request.sendall(f'Your token: {token}\n'.encode())
        self.request.sendall('Please send enough ether to your game account in order to deploy a game contract\n'.encode())
        logging.info('GenAcc: acct = %s, key = %s', acct.address, acct.key.hex())

    elif ch == 2:
        # validate token
        self.request.sendall('Your token: '.encode())
        token = self.request.recv(1024).strip()
        data = validate_then_decrypt(token, AES_KEY, HMAC_KEY)
        assert len(data) == 74
        acct = validate_game_account(data)

        # set random number in contract
        source = SRC_TEXT.replace('RN', str(int.from_bytes(os.urandom(16), 'little')))
        cont_if = compile_from_src(source)
        est_gas = get_deploy_est_gas(cont_if)
        self.request.sendall(f'Estimate gas of deploying game contract (in wei): {est_gas}\n'.encode())

        # get gas price specified by player
        self.request.sendall('Set gas price (in wei): '.encode())
        gas_price = self.request.recv(1024).strip()
        gas_price = int(gas_price)

        # deploy game contract
        err, tx_hash = contract_deploy(acct, cont_if, gas_price, 0)

        # check if got error when sending transaction
        if err:
            if err.args[0]['code'] == -32000:
                msg = 'Error: ' + err.args[0]['message'] + '\n'
                self.request.sendall(msg.encode())
            raise err

        self.request.sendall(f'Transaction hash: {tx_hash.hex()}\n'.encode())

        # generate new token
        data = acct.address.encode() + acct.key + tx_hash
        new_token = encrypt_then_mac(data, AES_KEY, HMAC_KEY)
        self.request.sendall(f'Your new token: {new_token}\n'.encode())

        self.request.sendall(f'Your goal is to emit the `{TOPIC}` event in the game contract\n'.encode())
        logging.info('Deployed: acct = %s, tx_hash = %s', acct.address, tx_hash.hex())

    elif ch == 3:
        # validate new token
        self.request.sendall('Your new token: '.encode())
        new_token = self.request.recv(1024).strip()
        data = validate_then_decrypt(new_token, AES_KEY, HMAC_KEY)
        assert len(data) == 106
        data, tx_hash = data[:-32], data[-32:]
        acct = validate_game_account(data)
        addr = get_cont_addr(tx_hash)

        # get transaction hash from player
        self.request.sendall(f'Transaction hash (in hex string) that emitted `{TOPIC}` event: '.encode())
        tx_hash = self.request.recv(1024).strip()
        tx_hash = tx_hash.decode()

        # check if transaction emitted TOPIC
        res = check_if_has_topic(addr, tx_hash, CONT_IF, TOPIC)
        if res:
            self.request.sendall(FLAG.encode())
        else:
            self.request.sendall('Nope\n'.encode())
        status = 'Solved' if res else 'Failed'
        logging.info('%s: cont_addr = %s, tx_hash = %s', status, addr, tx_hash)

    elif ch == 4:
        # get source code
        self.request.sendall(SRC_TEXT.replace('RN', '0').encode())

    else:
        self.request.sendall('Invalid option\n'.encode())

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(TIMEOUT)
        PoW(self)
        try:
            challenge(self)
        except:
            call_stack = traceback.extract_tb(sys.exc_info()[2])[-1]
            msg = '{} {} {}'.format(call_stack[0], call_stack[1], call_stack[2])
            logging.info('Error: %s', msg)

if __name__ == '__main__':
    # start server
    socketserver.TCPServer.allow_reuse_address = True
    server = ThreadedTCPServer(('0.0.0.0', 12345), MyTCPHandler)
    logging.info('Server: start running...')
    logging.info(f'Server: AES_KEY = {AES_KEY.hex()}')
    logging.info(f'Server: HMAC_KEY = {HMAC_KEY.hex()}')
    server.serve_forever()
