from util.w3_util import *


class BicoCertoRegistry:
    
    def __init__(
        self,
        contract_address: str = "",
        deploy: bool = False
    ):
        self.w3 = w3
        if deploy:
            self.contract = deploy_contract("BicoCertoRegistry")
            return
        self.contract = get_instance("BicoCertoRegistry", contract_address)      

    def set_admin(self, admin_address: str):
        """Set the admin contract address"""
        tx = self.contract.functions.setAdmin(admin_address).transact()
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return receipt
    
    def set_job_manager(self, job_manager_address: str):
        """Set the job manager contract address"""
        tx = self.contract.functions.setJobManager(job_manager_address).transact()
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return receipt
    
    def set_payment_gateway(self, payment_gateway_address: str):
        """Set the payment gateway contract address"""
        tx = self.contract.functions.setPaymentGateway(payment_gateway_address).transact()
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return receipt

    def set_reputation(self, reputation_address: str):
        """Set the reputation contract address"""
        tx = self.contract.functions.setReputation(reputation_address).transact()
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return receipt

    def set_dispute_resolver(self, dispute_resolver_address: str):
        """Set the dispute resolver contract address"""
        tx = self.contract.functions.setDisputeResolver(dispute_resolver_address).transact()
        receipt = self.w3.eth.wait_for_transaction_receipt(tx)
        return receipt
    
    def get_admin(self) -> str:
        """Get the admin contract address"""
        return self.contract.functions.getAdmin().call()
    
    def get_job_manager(self) -> str:
        """Get the job manager contract address"""
        return self.contract.functions.getJobManager().call()

    def get_payment_gateway(self) -> str:
        """Get the payment gateway contract address"""
        return self.contract.functions.getPaymentGateway().call()

    def get_reputation(self) -> str:
        """Get the reputation contract address"""
        return self.contract.functions.getReputation().call()

    def get_dispute_resolver(self) -> str:
        """Get the dispute resolver contract address"""
        return self.contract.functions.getDisputeResolver().call()

    def get_address(self) -> str:
        """Get the contract address"""
        return self.contract.address
