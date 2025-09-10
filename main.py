from utils.deploy_utils import *
from model.bico_certo_main import *
from model.bico_certo_registry import *
import datetime

bicoCertoRegistry = BicoCertoRegistry(deploy=True)
bicoCerto = BicoCerto(deploy=True, registry_address=bicoCertoRegistry.get_address())
bicoCertoAdmin = deploy_contract("BicoCertoAdmin", bicoCertoRegistry.get_address(), 5)
bicoCertoJobManager = deploy_contract("BicoCertoJobManager", bicoCertoRegistry.get_address(), bicoCerto.get_address(), 100000000000000000, 259200)
bicoCertoPaymentGateway = deploy_contract("BicoCertoPaymentGateway", bicoCertoRegistry.get_address(), w3.eth.default_account)
bicoCertoReputation = deploy_contract("BicoCertoReputation", bicoCertoRegistry.get_address())
bicoCertoDisputeResolver = deploy_contract("BicoCertoDisputeResolver", bicoCertoRegistry.get_address())

bicoCertoRegistry.set_admin(bicoCertoAdmin.address)
bicoCertoRegistry.set_job_manager(bicoCertoJobManager.address)
bicoCertoRegistry.set_payment_gateway(bicoCertoPaymentGateway.address)
bicoCertoRegistry.set_reputation(bicoCertoReputation.address)
bicoCertoRegistry.set_dispute_resolver(bicoCertoDisputeResolver.address)

print(bicoCertoRegistry.get_job_manager())

data = datetime.datetime(2025, 9, 11, 0, 0, 0)
timestamp_float = data.timestamp()

timestamp_int = int(timestamp_float)

job_id = bicoCerto.create_job(w3.eth.accounts[2], timestamp_int, "web development", "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG", 5, w3.eth.accounts[1])



print(bicoCerto.get_job(job_id))