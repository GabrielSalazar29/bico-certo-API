from web3 import Web3
import json
import os

# Conectar ao Ganache
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

# Usar a primeira conta do Ganache como default
w3.eth.default_account = w3.eth.accounts[0]

# Arquivo onde os endereços serão salvos
CONTRACTS_FILE = "../deployed_contracts.json"


def deploy_contract(contract_name, *args):
    print(f"Fazendo deploy de {contract_name}...")
    build_path = '../build'
    
    with open(os.path.join(build_path, f'{contract_name}_sol_{contract_name}.abi'), 'r') as f:
        abi = json.load(f)
    with open(os.path.join(build_path, f'{contract_name}_sol_{contract_name}.bin'), 'r') as f:
        bytecode = f.read()
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Estimar gás
    tx_hash = contract.constructor(*args).transact()
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"{contract_name} implantado em: {tx_receipt.contractAddress}")
    return w3.eth.contract(address=tx_receipt.contractAddress, abi=abi)


def get_instance(contract_name, contract_address):
    build_path = '../build'
    
    with open(os.path.join(build_path, f'{contract_name}_sol_{contract_name}.abi'), 'r') as f:
        abi = json.load(f)
    
    return w3.eth.contract(address=contract_address, abi=abi)


def set_default_account(account_address):
    w3.eth.default_account = account_address
    print(f"Conta padrão definida para: {account_address}")


def save_contracts_addresses(contracts_dict):
    """Salva os endereços dos contratos em um arquivo JSON"""
    with open(CONTRACTS_FILE, 'w') as f:
        json.dump(contracts_dict, f, indent=2)


def load_contracts_addresses():
    """Carrega os endereços dos contratos do arquivo JSON"""
    if os.path.exists(CONTRACTS_FILE):
        with open(CONTRACTS_FILE, 'r') as f:
            return json.load(f)
    else:
        print(f"Arquivo {CONTRACTS_FILE} não encontrado")
        return None
