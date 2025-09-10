from utils.w3_utils import *
from model.bico_certo_main import BicoCerto
from model.bico_certo_registry import BicoCertoRegistry


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


# def create_sample_job(bico_certo):
#     """Cria um job de exemplo"""
#     data = datetime.datetime(2025, 9, 11, 0, 0, 0)
#     timestamp_int = int(data.timestamp())
#
#     job_id = bico_certo.create_job(
#         w3.eth.accounts[2],
#         timestamp_int,
#         "web development",
#         "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
#         5,
#         w3.eth.accounts[1]
#     )
#
#     print(f"✅ Job criado com ID: {job_id}")
#     print(f"Detalhes do Job: {bico_certo.get_job(job_id)}")
#     return job_id


# Script principal
if __name__ == "__main__":
    contracts = deploy_all_contracts()
