import datetime
from app.model.bico_certo_main import BicoCerto
from app.schema.job_manager import CreateJob, GetJob
from fastapi import APIRouter, Depends, Request
from app.util.responses import APIResponse
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.model.user import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["JobManager"])
bico_certo = BicoCerto()


@router.post("/createJob", response_model=APIResponse)
def create_job(job_data: CreateJob, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    date_split = job_data.deadline.split("-")
    date = datetime.datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), 0, 0, 0)
    timestamp_int = int(date.timestamp())

    job_id = bico_certo.create_job(
        job_data.provider_address,
        timestamp_int,
        job_data.service_type,
        job_data.ipfs_hash,
        job_data.value,
        job_data.from_address
    )

    return APIResponse.success_response(
        data={
            "job_id": job_id.hex()
        },
        message="Serviço criado com sucesso!"
    )


@router.post("/", response_model=APIResponse)
def get_job(job: GetJob, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    job_data = bico_certo.get_job(job.job_id).to_dict()

    return APIResponse.success_response(
        data={
            **job_data
        },
        message="Dados do serviço recuperados com sucesso!"
    )
