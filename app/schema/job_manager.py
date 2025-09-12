from pydantic import BaseModel


class CreateJob(BaseModel):
    provider_address: str = "0x9Eededda12AB8124f349c58A4109F84D4B564788"
    from_address: str = "0x2Aa6189c6375dB807Ea231CD50E20b804ac2A27B"
    deadline: str = "10-10-2026"
    service_type: str = "Pintura"
    ipfs_hash: str = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    value: int = 20


class GetJob(BaseModel):
    job_id: str = "1e97c24742d3249620f7612bec38cee3da664e79e51fca5c16a21f18cae2b11b"