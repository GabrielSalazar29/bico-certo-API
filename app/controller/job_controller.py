import datetime
from app.model.bico_certo_main import BicoCerto
from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["JobManager"])
bico_certo = BicoCerto()


@router.post("/createJob")
def create_job(provider_address: str,
              from_address: str,
              deadline: str,
              service_type: str,
              ipfs_hash: str,
              value: int,
              ):

    date_split = deadline.split("-")
    date = datetime.datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), 0, 0, 0)
    timestamp_int = int(date.timestamp())

    job_id = bico_certo.create_job(
        provider_address,
        timestamp_int,
        service_type,
        ipfs_hash,
        value,
        from_address
    )

    return {"job_id": job_id.hex()}


@router.post("/")
def get_job(job_id: str):
    return bico_certo.get_job(job_id).to_dict()
