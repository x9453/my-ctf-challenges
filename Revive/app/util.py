from web3 import Web3, WebsocketProvider
from solcx import compile_source
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base64 import b64encode, b64decode
import hashlib
import hmac
import os

# connect to node
INFURA_PROJ_ID = os.environ['INFURA_PROJ_ID']
w3 = Web3(WebsocketProvider(f'wss://ropsten.infura.io/ws/v3/{INFURA_PROJ_ID}'))

# aes and hmac
def encrypt_then_mac(data, aes_key, hmac_key):
    cipher = AES.new(aes_key, AES.MODE_CBC)
    msg = cipher.iv + cipher.encrypt(pad(data, AES.block_size))
    sig = hmac.new(hmac_key, msg, hashlib.sha256).digest()
    token = b64encode(msg + sig).decode()
    return token

def validate_then_decrypt(token, aes_key, hmac_key):
    s = b64decode(token)
    msg, sig = s[:-32], s[-32:]
    assert sig == hmac.new(hmac_key, msg, hashlib.sha256).digest()
    iv, ct = msg[:16], msg[16:]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv=iv)
    data = unpad(cipher.decrypt(ct), AES.block_size)
    return data

# solc
def compile_from_src(source):
    compiled_sol = compile_source(source)
    _, cont_if = compiled_sol.popitem()
    return cont_if

# web3
def get_deploy_est_gas(cont_if):
    instance = w3.eth.contract(
        abi=cont_if['abi'],
        bytecode=cont_if['bin']
    )
    return instance.constructor().estimateGas()

def contract_deploy(acct, cont_if, gas_price, value):
    instance = w3.eth.contract(
        abi=cont_if['abi'],
        bytecode=cont_if['bin']
    )
    construct_tx = instance.constructor().buildTransaction({
        'chainId': 3, # ropsten
        'from': acct.address,
        'nonce': w3.eth.getTransactionCount(acct.address),
        'value': w3.toWei(value, 'ether'),
        'gasPrice': gas_price
    })
    signed_tx = acct.signTransaction(construct_tx)
    try:
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    except Exception as err:
        return err, None
    return None, tx_hash

def get_cont_addr(tx_hash):
    tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
    assert tx_receipt != None
    return tx_receipt['contractAddress']

def check_if_has_topic(addr, tx_hash, cont_if, topic):
    contract = w3.eth.contract(abi=cont_if['abi'])
    tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
    logs = contract.events[topic]().processReceipt(tx_receipt)
    for d in logs:
        if d['address'] == addr:
            return True
    return False

# game account
def create_game_account():
    acct = w3.eth.account.create(os.urandom(32))
    return acct

def validate_game_account(data):
    addr, priv_key = data[:-32], data[-32:]
    acct = w3.eth.account.from_key(priv_key)
    assert acct.address.encode() == addr
    return acct
