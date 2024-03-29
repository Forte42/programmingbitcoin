import time
from block import Block
from bloomfilter import BloomFilter
from ecc import PrivateKey
from helper import hash256, little_endian_to_int, encode_varint, read_varint, decode_base58, hash160, SIGHASH_ALL
from merkleblock import MerkleBlock
from network import (
    GetDataMessage,
    GetHeadersMessage,
    HeadersMessage,
    NetworkEnvelope,
    SimpleNode,
    TX_DATA_TYPE,
    FILTERED_BLOCK_DATA_TYPE,
)
from script import p2pkh_script, Script
from tx import Tx, TxIn, TxOut

last_block_hex = '0000000000004ffbc4098514044473c1df118c2de621decb5f8d33262f483677'

secret = little_endian_to_int(hash256(b'banana_lick_gtkhhz@gmail.com'))
private_key = PrivateKey(secret=secret)
addr = private_key.point.address(testnet=True)
h160 = decode_base58(addr)

target_address = 'mv4rnyY3Su5gjcDNzbMLKBQkBicCtHUtFB'
target_h160 = decode_base58(target_address)
target_script = p2pkh_script(target_h160)
fee = int(0.00000696 * 10**8)


# connect to testnet.programmingbitcoin.com in testnet mode
node = SimpleNode('testnet.programmingbitcoin.com', testnet=True, logging=False)
# create a bloom filter of size 30 and 5 functions. Add a tweak.
bf = BloomFilter(30, 5, 912)
# add the h160 to the bloom filter
bf.add(h160)
# complete the handshake
node.handshake()
# load the bloom filter with the filterload command
node.send(bf.filterload())
# set start block to last_block from above
start_block = bytes.fromhex(last_block_hex)
# send a getheaders message with the starting block
get_headers = GetHeadersMessage(start_block=start_block)
node.send(get_headers)
# wait for the headers message
headers = node.wait_for(HeadersMessage)
# store the last block as None
last_block = None
# initialize the GetDataMessage
get_data = GetDataMessage()
# loop through the blocks in the headers
for block in headers.blocks:
    # check that the proof of work on the block is valid
    if not block.check_pow():
        raise RuntimeError('Invalid proof of work')
    # check that this block's prev_block is the last block
    if last_block != None and block.prev_block != last_block:
        raise RuntimeError('Invalid prev_block')
    # add a new item to the get_data_message
    # should be FILTERED_BLOCK_DATA_TYPE and block hash
    get_data.add_data(FILTERED_BLOCK_DATA_TYPE, block.hash())
    # set the last block to the current hash
    last_block = block.hash()
# send the getdata message
node.send(get_data)
# initialize prev_tx, prev_amount and prev_index to None
prev_tx = None
prev_index = None
prev_amount = None
# loop while prev_tx is None
while prev_tx is None:
    # wait for the merkleblock or tx commands
    message = node.wait_for(MerkleBlock, Tx)
    # if we have the merkleblock command
    if message.command == b'merkleblock':
        # check that the MerkleBlock is valid
        if not message.is_valid():
            raise RuntimeError('Invalid MerkleBlock')
    # else we have the tx command
    else:
        # set the tx's testnet to be True
        message.testnet = True
        # loop through the tx outs
        for i, tx_out in enumerate(message.tx_outs):
            # if our output has the same address as our address we found it
            if tx_out.script_pubkey.address(testnet=True) == addr:
                # we found our utxo. set prev_tx, prev_index, and tx
                prev_index = i
                prev_tx = message.hash
                prev_amount = tx_out.amount
                print('found: {}:{}'.format(prev_tx.hex(), prev_index))
# create the TxIn
tx_in = TxIn(prev_tx, prev_index)
# calculate the output amount (previous amount minus the fee)
output_amount = prev_amount - fee
# create a new TxOut to the target script with the output amount
tx_out = TxOut(output_amount, target_script)
# create a new transaction with the one input and one output
tx = Tx(1, [tx_in], [tx_out], 0, testnet = True)
# sign the only input of the transaction
tx.sign_input(0, private_key)
# serialize and hex to see what it looks like
tx_hex = tx.serialize().hex()
print(tx_hex)
# send this signed transaction on the network
node.send(tx)
# wait a sec so this message goes through with time.sleep(1)
time.sleep(1) 
# now ask for this transaction from the other node
# create a GetDataMessage
get_data = GetDataMessage()
# ask for our transaction by adding it to the message
get_data.add_data(TX_DATA_TYPE, tx.hash())
# send the message
node.send(get_data)
# now wait for a Tx response
tx_response = node.wait_for(Tx)
# if the received tx has the same id as our tx, we are done!
if tx_response.id == tx.id:
    print('Transaction found!')
else:
    print('Uh-oh!')