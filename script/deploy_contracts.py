import sys
import os

# Adicionar o diretório raiz do projeto ao Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.util.w3_util import *
from app.model.bico_certo_main import BicoCerto
from app.model.bico_certo_registry import BicoCertoRegistry


def deploy_all_contracts():
    """Deploy de todos os contratos e salva os endereços"""

    # Deploy dos contratos
    bico_certo_registry = BicoCertoRegistry(deploy=True)
    bico_certo = BicoCerto(deploy=True, registry_address=bico_certo_registry.get_address())
    bico_certo_admin = deploy_contract("BicoCertoAdmin", bico_certo_registry.get_address(), 5)
    bico_certo_job_manager = deploy_contract("BicoCertoJobManager",
                                             bico_certo_registry.get_address(),
                                             bico_certo.get_address(),
                                             100000000000000000,
                                             259200)
    bico_certo_payment_gateway = deploy_contract("BicoCertoPaymentGateway",
                                                 bico_certo_registry.get_address(),
                                                 w3.eth.default_account)
    bico_certo_reputation = deploy_contract("BicoCertoReputation",
                                            bico_certo_registry.get_address())
    bico_certo_dispute_resolver = deploy_contract("BicoCertoDisputeResolver",
                                                  bico_certo_registry.get_address())

    # Configuração do Registry
    bico_certo_registry.set_admin(bico_certo_admin.address)
    bico_certo_registry.set_job_manager(bico_certo_job_manager.address)
    bico_certo_registry.set_payment_gateway(bico_certo_payment_gateway.address)
    bico_certo_registry.set_reputation(bico_certo_reputation.address)
    bico_certo_registry.set_dispute_resolver(bico_certo_dispute_resolver.address)

    # Cria dicionário com todos os endereços
    contracts_dict = {
        "BicoCertoRegistry": bico_certo_registry.get_address(),
        "BicoCerto": bico_certo.get_address()
    }

    # Salva os endereços
    save_contracts_addresses(contracts_dict)

    # Retorna os objetos dos contratos para uso imediato
    return {
        "registry": bico_certo_registry,
        "main": bico_certo,
        "admin": bico_certo_admin,
        "job_manager": bico_certo_job_manager,
        "payment_gateway": bico_certo_payment_gateway,
        "reputation": bico_certo_reputation,
        "dispute_resolver": bico_certo_dispute_resolver
    }


if __name__ == "__main__":
    contracts = deploy_all_contracts()
