import socketserver
import sys
import traceback
import logging
from util import *

logging.basicConfig(level=logging.INFO)

# server settings
HOST, PORT = '0.0.0.0', 12345
TIMEOUT = 120
GAS_PRICE = 2000000000
AES_KEY = bytes.fromhex(os.environ['AES_KEY'])
HMAC_KEY = bytes.fromhex(os.environ['HMAC_KEY'])
CHAL_FILE = os.environ['CHAL_FILE']
CONT_NAME = os.environ['CONT_NAME']

with open('/app/flag.txt', 'r') as f:
    FLAG = f.read().strip()

# get contract source
with open(f'/app/{CHAL_FILE}', 'r') as f:
    SRC_TEXT = f.read().strip()

# banner and menu
with open('/app/art.txt', 'r') as f:
    ART_TEXT = f.read()

MENU = ART_TEXT + f'''
All game contracts will be deployed on ** {DEPLOY_NETWORK} testnet **
Please follow the instructions below:

1. Create a game account
2. Deploy a game contract
3. Request for the flag
'''

def check_solved(addr, cont_if, tx_hash):
    #return check_has_topic(addr, cont_if, tx_hash, 'SendFlag')
    return get_public_var(addr, cont_if, 'sendFlag') == True

def challenge(self):
    cont_if = compile_from_src(SRC_TEXT, CONT_NAME)
    self.sendline(MENU)

    # get player's choice
    self.send('Input your choice: ')
    ch = self.recv()
    ch = int(ch) if ch else -1

    if ch == 1:
        # create a game account
        acct = create_game_account()
        self.sendline(f'Your game account: {acct.address}')

        # generate account token
        data = acct.address.encode() + acct.key
        acct_token = encrypt_then_mac(data, AES_KEY, HMAC_KEY)
        self.sendline(f'Your account token: {acct_token}')
        self.sendline('')
        self.sendline('Please keep your account token, and send some Ether to the game account.')
        self.sendline('The sent Ether is for transaction fee of the game contract deployment.')
        self.sendline('After that, continue to Choice 2 to deploy a game contract.')
        logging.info(f'GenAcc: acct = {acct.address}, key = {acct.key.hex()}')

    elif ch == 2:
        # validate token
        self.send('Input your account token: ')
        acct_token = self.recv()
        self.sendline('')
        data = validate_then_decrypt(acct_token, AES_KEY, HMAC_KEY)
        assert len(data) == 74
        acct = validate_game_account(data)

        # get estimated gas
        est_gas = get_deploy_est_gas(cont_if)
        self.sendline(f'Estimated gas for deploying the game contract (in wei): {est_gas}')

        # get gas price specified by player
        self.send(f'Input gas price (in wei, default {GAS_PRICE}): ')
        gas_price = self.recv()
        gas_price = int(gas_price) if gas_price else GAS_PRICE
        self.sendline('')

        # deploy game contract
        err, tx_hash = contract_deploy(acct, cont_if, gas_price, 0)

        # check if got error when sending transaction
        if err:
            if err.args[0]['code'] == -32000:
                self.sendline(f'Error: {err.args[0]["message"]}')
            raise err

        self.sendline(f'Game contract is deploying...')
        self.sendline(f'Transaction hash of game contract deployment: {tx_hash.hex()}')

        # generate new token
        data = acct.address.encode() + acct.key + tx_hash
        cont_token = encrypt_then_mac(data, AES_KEY, HMAC_KEY)
        self.sendline(f'Your contract token: {cont_token}')

        self.sendline('')
        self.sendline(f'Keep your contract token and solve the challenge now!')
        self.sendline(f'Your goal is to set the `sendFlag` variable in the game contract to `true`.')
        self.sendline(f'Once you solve the challenge, continue to Choice 3 to request for the flag.')
        logging.info(f'Deployed: acct = {acct.address}, tx_hash = {tx_hash.hex()}')

    elif ch == 3:
        # validate new token
        self.send('Input your contract token: ')
        cont_token = self.recv()
        self.sendline('')
        data = validate_then_decrypt(cont_token, AES_KEY, HMAC_KEY)
        assert len(data) == 106
        data, tx_hash = data[:-32], data[-32:]
        acct = validate_game_account(data)
        addr = get_cont_addr(tx_hash)

        # send the flag if the challange is solved
        is_solved = check_solved(addr, cont_if, None)
        if is_solved:
            self.sendline(f'Congrats! Here is your flag: {FLAG}')
        else:
            self.sendline('Nope, try harder!')
        status = 'Solved' if is_solved else 'Failed'
        logging.info(f'{status}: cont_addr = {addr}')

    else:
        self.sendline('Invalid option!')

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.send = lambda s: self.request.sendall(s.encode())
        self.sendline = lambda s: self.send(s + '\n')
        self.recv = lambda: self.request.recv(1024).strip()
        self.request.settimeout(TIMEOUT)
        try:
            challenge(self)
        except Exception as e:
            self.sendline('Error!')
            call_stack = traceback.extract_tb(sys.exc_info()[2])[-1]
            logging.info(f'Error: {call_stack[0]} {call_stack[1]} {call_stack[2]}')

if __name__ == '__main__':
    # start server
    socketserver.TCPServer.allow_reuse_address = True
    server = ThreadedTCPServer((HOST, PORT), MyTCPHandler)
    logging.info('Server: start running...')
    server.serve_forever()
