from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict

from starlette.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.service.ipfs_service import IPFSService
from app.model.bico_certo_main import BicoCerto, JobStatus
from app.model.wallet import Wallet
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.model.user import User
from app.service.report_generator import ReportGenerator
from app.util.responses import APIResponse

router = APIRouter(prefix="/api", tags=["dashboard"])

bico_certo = BicoCerto()
ipfs_service = IPFSService()


@router.get("/provider/dashboard")
async def get_provider_dashboard(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Dashboard completo do prestador"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa a nova função getProviderProfile para obter dados como Provider
        provider_profile = bico_certo.contract.functions.getProviderProfile(user_address).call()
        # provider_profile retorna: (averageRating, totalRatings, totalJobs, totalEarned)
        average_rating = provider_profile[0] / 100.0  # Converte de 425 para 4.25
        total_ratings = provider_profile[1]
        total_jobs_completed = provider_profile[2]
        total_earned_wei = provider_profile[3]

        provider_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() == user_address.lower():
                    provider_jobs.append({
                        'id': job_id,
                        'data': job_data
                    })
            except Exception:
                continue

        active_jobs = sum(
            1 for job in provider_jobs
            if JobStatus(job['data'][9]) in [JobStatus.ACCEPTED, JobStatus.IN_PROGRESS]
        )

        completed_jobs = sum(
            1 for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        total_earnings = sum(
            float(bico_certo.w3.from_wei(job['data'][3], 'ether'))
            for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        now = datetime.now()
        last_month_start = now - timedelta(days=30)
        previous_month_start = now - timedelta(days=60)

        last_month_completed = sum(
            1 for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
            and job['data'][7] > 0
            and datetime.fromtimestamp(job['data'][7]) >= last_month_start
        )

        previous_month_completed = sum(
            1 for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
            and job['data'][7] > 0
            and previous_month_start <= datetime.fromtimestamp(job['data'][7]) < last_month_start
        )

        if previous_month_completed > 0:
            jobs_trend = ((last_month_completed - previous_month_completed) / previous_month_completed) * 100
        else:
            jobs_trend = 100 if last_month_completed > 0 else 0

        last_month_earnings = sum(
            float(bico_certo.w3.from_wei(job['data'][3], 'ether'))
            for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
            and job['data'][7] > 0
            and datetime.fromtimestamp(job['data'][7]) >= last_month_start
        )

        previous_month_earnings = sum(
            float(bico_certo.w3.from_wei(job['data'][3], 'ether'))
            for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
            and job['data'][7] > 0
            and previous_month_start <= datetime.fromtimestamp(job['data'][7]) < last_month_start
        )

        if previous_month_earnings > 0:
            earnings_trend = ((last_month_earnings - previous_month_earnings) / previous_month_earnings) * 100
        else:
            earnings_trend = 100 if last_month_earnings > 0 else 0

        monthly_earnings = _calculate_monthly_data(provider_jobs, is_provider=True)
        category_performance = _calculate_category_performance(provider_jobs)
        recent_activity = _calculate_recent_activity(provider_jobs, days=7)

        try:
            proposal_ids = bico_certo.contract.functions.getProviderProposals(user_address).call()
            pending_proposals = 0
            total_proposals = len(proposal_ids)
            accepted_proposals = 0

            for proposal_id in proposal_ids:
                try:
                    proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
                    status = proposal_data[6]
                    if status == 1:
                        pending_proposals += 1
                    elif status == 2:
                        accepted_proposals += 1
                except:
                    continue

            proposal_acceptance_rate = int((accepted_proposals / total_proposals * 100) if total_proposals > 0 else 0)
        except Exception:
            pending_proposals = 0
            proposal_acceptance_rate = 0

        motivation_message = _get_motivation_message(
            average_rating=average_rating,
            jobs_trend=jobs_trend,
            earnings_trend=earnings_trend,
            completed_jobs=completed_jobs,
            proposal_acceptance_rate=proposal_acceptance_rate
        )

        completed_job_list = [
            job for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        ]

        average_job_value = (total_earnings / len(completed_job_list)) if completed_job_list else 0

        delivery_times = []
        for job in completed_job_list:
            job_data = job['data']
            accepted_at = job_data[6]
            completed_at = job_data[7]
            if accepted_at > 0 and completed_at > 0:
                days = (completed_at - accepted_at) / 86400
                delivery_times.append(days)

        average_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        highest_earning = max(
            (float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in completed_job_list),
            default=0
        )

        last_job_date = None
        if completed_job_list:
            latest_job = max(completed_job_list, key=lambda j: j['data'][7])
            last_job_date = datetime.fromtimestamp(latest_job['data'][7]).strftime('%Y-%m-%d')

        unique_clients = set(job['data'][1] for job in completed_job_list)

        return APIResponse.success_response(
            data={
                "completedJobs": completed_jobs,
                "totalEarnings": total_earnings,
                "averageRating": round(average_rating, 2),  # Usa a média do Provider
                "totalRatings": total_ratings,  # Número total de avaliações
                "proposalAcceptanceRate": proposal_acceptance_rate,
                "activeJobs": active_jobs,
                "pendingProposals": pending_proposals,
                "monthlyEarnings": monthly_earnings,
                "jobsByCategory": category_performance,
                "recentActivity": recent_activity,
                "trends": {
                    "jobsTrend": round(jobs_trend, 1),
                    "earningsTrend": round(earnings_trend, 1),
                    "motivationMessage": motivation_message
                },
                "metrics": {
                    "averageJobValue": round(average_job_value, 2),
                    "averageDeliveryTime": round(average_delivery_time, 1),
                    "totalClients": len(unique_clients),
                    "highestEarningJob": round(highest_earning, 2),
                    "lastJobDate": last_job_date
                }
            },
            message="Dashboard carregado com sucesso"
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dashboard: {str(e)}")


@router.get("/provider/dashboard/quick-stats")
async def get_provider_quick_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Estatísticas rápidas do prestador"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getProviderAverageRating para obter apenas a média
        average_rating_raw = bico_certo.contract.functions.getProviderAverageRating(user_address).call()
        average_rating = average_rating_raw / 100.0  # Converte de 425 para 4.25

        active_jobs = 0
        completed_jobs = 0
        total_earnings = 0.0

        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() != user_address.lower():
                    continue

                status = JobStatus(job_data[9])
                if status in [JobStatus.ACCEPTED, JobStatus.IN_PROGRESS]:
                    active_jobs += 1
                elif status == JobStatus.APPROVED:
                    completed_jobs += 1
                    total_earnings += float(bico_certo.w3.from_wei(job_data[3], 'ether'))
            except Exception:
                continue

        return APIResponse.success_response(
            data={
                "activeJobs": active_jobs,
                "completedJobs": completed_jobs,
                "totalEarnings": total_earnings,
                "rating": round(average_rating, 2)
            }
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provider/dashboard/earnings")
async def get_provider_earnings(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        months: int = 6
):
    """Ganhos mensais do prestador"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        provider_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() == wallet.address.lower():
                    provider_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        monthly_data = _calculate_monthly_data(provider_jobs, is_provider=True, months=months)

        return APIResponse.success_response(data=monthly_data).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provider/dashboard/categories")
async def get_provider_categories(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Performance por categoria"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        provider_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() == wallet.address.lower():
                    provider_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        categories = _calculate_category_performance(provider_jobs)

        return APIResponse.success_response(data=categories).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provider/dashboard/export/pdf")
async def export_provider_dashboard_pdf(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Exporta dashboard do prestador em PDF"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getProviderProfile
        provider_profile = bico_certo.contract.functions.getProviderProfile(user_address).call()
        average_rating = provider_profile[0] / 100.0

        provider_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() == user_address.lower():
                    provider_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        active_jobs = sum(
            1 for job in provider_jobs if JobStatus(job['data'][9]) in [JobStatus.ACCEPTED, JobStatus.IN_PROGRESS])
        completed_jobs = sum(1 for job in provider_jobs if JobStatus(job['data'][9]) == JobStatus.APPROVED)
        total_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                             JobStatus(job['data'][9]) == JobStatus.APPROVED)

        now = datetime.now()
        last_month_start = now - timedelta(days=30)
        previous_month_start = now - timedelta(days=60)

        last_month_completed = sum(1 for job in provider_jobs if
                                   JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                       7] > 0 and datetime.fromtimestamp(job['data'][7]) >= last_month_start)
        previous_month_completed = sum(1 for job in provider_jobs if
                                       JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                           7] > 0 and previous_month_start <= datetime.fromtimestamp(
                                           job['data'][7]) < last_month_start)

        jobs_trend = ((
                              last_month_completed - previous_month_completed) / previous_month_completed) * 100 if previous_month_completed > 0 else 100 if last_month_completed > 0 else 0

        last_month_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                                  JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                      7] > 0 and datetime.fromtimestamp(job['data'][7]) >= last_month_start)
        previous_month_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                                      JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                          7] > 0 and previous_month_start <= datetime.fromtimestamp(
                                          job['data'][7]) < last_month_start)

        earnings_trend = ((
                                  last_month_earnings - previous_month_earnings) / previous_month_earnings) * 100 if previous_month_earnings > 0 else 100 if last_month_earnings > 0 else 0

        proposal_ids = bico_certo.contract.functions.getProviderProposals(user_address).call()
        pending_proposals = 0
        accepted_proposals = 0
        for proposal_id in proposal_ids:
            try:
                proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
                if proposal_data[6] == 1:
                    pending_proposals += 1
                elif proposal_data[6] == 2:
                    accepted_proposals += 1
            except:
                continue

        proposal_acceptance_rate = int((accepted_proposals / len(proposal_ids) * 100) if len(proposal_ids) > 0 else 0)

        completed_job_list = [
            job for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        ]

        average_job_value = (total_earnings / len(completed_job_list)) if completed_job_list else 0

        delivery_times = []
        for job in completed_job_list:
            job_data = job['data']
            accepted_at = job_data[6]
            completed_at = job_data[7]
            if accepted_at > 0 and completed_at > 0:
                days = (completed_at - accepted_at) / 86400
                delivery_times.append(days)

        average_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        highest_earning = max(
            (float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in completed_job_list),
            default=0
        )

        last_job_date = None
        if completed_job_list:
            latest_job = max(completed_job_list, key=lambda j: j['data'][7])
            last_job_date = datetime.fromtimestamp(latest_job['data'][7]).strftime('%Y-%m-%d')

        unique_clients = set(job['data'][1] for job in completed_job_list)

        dashboard_data = {
            "completedJobs": completed_jobs,
            "totalEarnings": total_earnings,
            "averageRating": round(average_rating, 2),
            "proposalAcceptanceRate": proposal_acceptance_rate,
            "activeJobs": active_jobs,
            "pendingProposals": pending_proposals,
            "monthlyEarnings": _calculate_monthly_data(provider_jobs, is_provider=True),
            "jobsByCategory": _calculate_category_performance(provider_jobs),
            "trends": {
                "jobsTrend": round(jobs_trend, 1),
                "earningsTrend": round(earnings_trend, 1),
            },
            "metrics": {
                "averageJobValue": round(average_job_value, 2),
                "averageDeliveryTime": round(average_delivery_time, 1),
                "totalClients": len(unique_clients),
                "highestEarningJob": round(highest_earning, 2),
                "lastJobDate": last_job_date
            }
        }

        pdf_buffer = ReportGenerator.generate_provider_pdf(dashboard_data, current_user.full_name)

        filename = f"dashboard_prestador_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")


@router.get("/provider/dashboard/export/excel")
async def export_provider_dashboard_excel(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Exporta dashboard do prestador em Excel"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getProviderProfile
        provider_profile = bico_certo.contract.functions.getProviderProfile(user_address).call()
        average_rating = provider_profile[0] / 100.0

        provider_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[2].lower() == user_address.lower():
                    provider_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        active_jobs = sum(
            1 for job in provider_jobs if JobStatus(job['data'][9]) in [JobStatus.ACCEPTED, JobStatus.IN_PROGRESS])
        completed_jobs = sum(1 for job in provider_jobs if JobStatus(job['data'][9]) == JobStatus.APPROVED)
        total_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                             JobStatus(job['data'][9]) == JobStatus.APPROVED)

        now = datetime.now()
        last_month_start = now - timedelta(days=30)
        previous_month_start = now - timedelta(days=60)

        last_month_completed = sum(1 for job in provider_jobs if
                                   JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                       7] > 0 and datetime.fromtimestamp(job['data'][7]) >= last_month_start)
        previous_month_completed = sum(1 for job in provider_jobs if
                                       JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                           7] > 0 and previous_month_start <= datetime.fromtimestamp(
                                           job['data'][7]) < last_month_start)

        jobs_trend = ((
                              last_month_completed - previous_month_completed) / previous_month_completed) * 100 if previous_month_completed > 0 else 100 if last_month_completed > 0 else 0

        last_month_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                                  JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                      7] > 0 and datetime.fromtimestamp(job['data'][7]) >= last_month_start)
        previous_month_earnings = sum(float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in provider_jobs if
                                      JobStatus(job['data'][9]) == JobStatus.APPROVED and job['data'][
                                          7] > 0 and previous_month_start <= datetime.fromtimestamp(
                                          job['data'][7]) < last_month_start)

        earnings_trend = ((
                                  last_month_earnings - previous_month_earnings) / previous_month_earnings) * 100 if previous_month_earnings > 0 else 100 if last_month_earnings > 0 else 0

        proposal_ids = bico_certo.contract.functions.getProviderProposals(user_address).call()
        pending_proposals = 0
        accepted_proposals = 0
        for proposal_id in proposal_ids:
            try:
                proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
                if proposal_data[6] == 1:
                    pending_proposals += 1
                elif proposal_data[6] == 2:
                    accepted_proposals += 1
            except:
                continue

        proposal_acceptance_rate = int((accepted_proposals / len(proposal_ids) * 100) if len(proposal_ids) > 0 else 0)

        completed_job_list = [
            job for job in provider_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        ]

        average_job_value = (total_earnings / len(completed_job_list)) if completed_job_list else 0

        delivery_times = []
        for job in completed_job_list:
            job_data = job['data']
            accepted_at = job_data[6]
            completed_at = job_data[7]
            if accepted_at > 0 and completed_at > 0:
                days = (completed_at - accepted_at) / 86400
                delivery_times.append(days)

        average_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        highest_earning = max(
            (float(bico_certo.w3.from_wei(job['data'][3], 'ether')) for job in completed_job_list),
            default=0
        )

        last_job_date = None
        if completed_job_list:
            latest_job = max(completed_job_list, key=lambda j: j['data'][7])
            last_job_date = datetime.fromtimestamp(latest_job['data'][7]).strftime('%Y-%m-%d')

        unique_clients = set(job['data'][1] for job in completed_job_list)

        dashboard_data = {
            "completedJobs": completed_jobs,
            "totalEarnings": total_earnings,
            "averageRating": round(average_rating, 2),
            "proposalAcceptanceRate": proposal_acceptance_rate,
            "activeJobs": active_jobs,
            "pendingProposals": pending_proposals,
            "monthlyEarnings": _calculate_monthly_data(provider_jobs, is_provider=True),
            "jobsByCategory": _calculate_category_performance(provider_jobs),
            "trends": {
                "jobsTrend": round(jobs_trend, 1),
                "earningsTrend": round(earnings_trend, 1),
            },
            "metrics": {
                "averageJobValue": round(average_job_value, 2),
                "averageDeliveryTime": round(average_delivery_time, 1),
                "totalClients": len(unique_clients),
                "highestEarningJob": round(highest_earning, 2),
                "lastJobDate": last_job_date
            }
        }

        excel_buffer = ReportGenerator.generate_provider_excel(dashboard_data, current_user.full_name)

        filename = f"dashboard_prestador_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar Excel: {str(e)}")


@router.get("/client/dashboard")
async def get_client_dashboard(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Dashboard completo do cliente"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getClientProfile para obter dados como Cliente
        client_profile = bico_certo.contract.functions.getClientProfile(user_address).call()
        # client_profile retorna: (averageRating, totalRatings, totalJobs, totalSpent)
        client_average_rating = client_profile[0] / 100.0  # Converte de 425 para 4.25
        client_total_ratings = client_profile[1]

        client_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() == user_address.lower():
                    client_jobs.append({'id': job_id, 'data': job_data})
            except Exception:
                continue

        active_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) in [
                JobStatus.CREATED, JobStatus.OPEN, JobStatus.ACCEPTED,
                JobStatus.IN_PROGRESS, JobStatus.COMPLETED
            ]
        )

        completed_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        total_spent = sum(
            float(bico_certo.w3.from_wei(job['data'][3] + job['data'][4], 'ether'))
            for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        monthly_spending = _calculate_monthly_data(client_jobs, is_provider=False)
        spending_by_category = _calculate_spending_by_category(client_jobs)
        jobs_by_status = _calculate_jobs_by_status(client_jobs)
        recent_jobs = _get_recent_jobs(client_jobs, limit=10, db=db)

        approved_jobs = [
            job for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        ]
        average_job_cost = total_spent / len(approved_jobs) if approved_jobs else 0

        completion_rate = int((completed_jobs / len(client_jobs) * 100) if client_jobs else 0)

        pending_approvals = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.COMPLETED
        )

        providers_hired = len(set(
            job['data'][2] for job in client_jobs
            if job['data'][2] != '0x0000000000000000000000000000000000000000'
        ))

        return APIResponse.success_response(
            data={
                "activeJobs": active_jobs,
                "completedJobs": completed_jobs,
                "totalSpent": total_spent,
                "averageJobCost": round(average_job_cost, 2),
                "providersHired": providers_hired,
                "pendingApprovals": pending_approvals,
                "monthlySpending": monthly_spending,
                "spendingByCategory": spending_by_category,
                "jobsByStatus": jobs_by_status,
                "recentJobs": recent_jobs,
                "metrics": {
                    "clientRating": round(client_average_rating, 2),  # Avaliação do cliente
                    "clientTotalRatings": client_total_ratings,  # Total de avaliações recebidas
                    "completionRate": completion_rate,
                    "favoriteCategory": spending_by_category[0]["category"] if spending_by_category else "N/A"
                }
            },
            message="Dashboard carregado com sucesso"
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/dashboard/quick-stats")
async def get_client_quick_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Estatísticas rápidas do cliente"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        active_jobs = 0
        completed_jobs = 0
        total_spent = 0.0

        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() != wallet.address.lower():
                    continue

                status = JobStatus(job_data[9])
                if status in [JobStatus.CREATED, JobStatus.OPEN, JobStatus.ACCEPTED, JobStatus.IN_PROGRESS]:
                    active_jobs += 1
                elif status == JobStatus.APPROVED:
                    completed_jobs += 1
                    total_spent += float(bico_certo.w3.from_wei(job_data[3] + job_data[4], 'ether'))
            except Exception:
                continue

        return APIResponse.success_response(
            data={
                "activeJobs": active_jobs,
                "completedJobs": completed_jobs,
                "totalSpent": total_spent,
                "savedProviders": 0
            }
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/dashboard/spending")
async def get_client_spending(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        months: int = 6
):
    """Gastos mensais do cliente"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        client_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() == wallet.address.lower():
                    client_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        monthly_data = _calculate_monthly_data(client_jobs, is_provider=False, months=months)

        return APIResponse.success_response(data=monthly_data).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/dashboard/recent-jobs")
async def get_client_recent_jobs(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = 10
):
    """Jobs recentes do cliente"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        client_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() == wallet.address.lower():
                    client_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        recent = _get_recent_jobs(client_jobs, limit=limit, db=db)

        return APIResponse.success_response(data=recent).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/dashboard/export/pdf")
async def export_client_dashboard_pdf(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Exporta dashboard do cliente em PDF"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getClientProfile
        client_profile = bico_certo.contract.functions.getClientProfile(user_address).call()
        client_average_rating = client_profile[0] / 100.0

        client_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() == user_address.lower():
                    client_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        active_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) in [
                JobStatus.CREATED, JobStatus.OPEN, JobStatus.ACCEPTED,
                JobStatus.IN_PROGRESS, JobStatus.COMPLETED
            ]
        )

        completed_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        total_spent = sum(
            float(bico_certo.w3.from_wei(job['data'][3] + job['data'][4], 'ether'))
            for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        providers_hired = len(set(
            job['data'][2] for job in client_jobs
            if job['data'][2] != '0x0000000000000000000000000000000000000000'
        ))

        pending_approvals = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.COMPLETED
        )

        completion_rate = int((completed_jobs / len(client_jobs) * 100) if client_jobs else 0)

        spending_by_category = _calculate_spending_by_category(client_jobs)
        favorite_category = spending_by_category[0]["category"] if spending_by_category else "N/A"

        dashboard_data = {
            "activeJobs": active_jobs,
            "completedJobs": completed_jobs,
            "totalSpent": total_spent,
            "providersHired": providers_hired,
            "pendingApprovals": pending_approvals,
            "monthlySpending": _calculate_monthly_data(client_jobs, is_provider=False),
            "spendingByCategory": spending_by_category,
            "metrics": {
                "clientRating": round(client_average_rating, 2),
                "completionRate": completion_rate,
                "favoriteCategory": favorite_category
            }
        }

        pdf_buffer = ReportGenerator.generate_client_pdf(dashboard_data, current_user.full_name)

        filename = f"dashboard_cliente_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")


@router.get("/client/dashboard/export/excel")
async def export_client_dashboard_excel(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Exporta dashboard do cliente em Excel"""
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
        if not wallet:
            raise HTTPException(status_code=400, detail="Carteira não encontrada")

        user_address = wallet.address
        user_jobs = bico_certo.contract.functions.getUserJobs(user_address).call()

        # Usa getClientProfile
        client_profile = bico_certo.contract.functions.getClientProfile(user_address).call()
        client_average_rating = client_profile[0] / 100.0

        client_jobs = []
        for job_id in user_jobs:
            try:
                job_data = bico_certo.contract.functions.getJob(job_id).call()
                if job_data[1].lower() == user_address.lower():
                    client_jobs.append({'id': job_id, 'data': job_data})
            except:
                continue

        active_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) in [
                JobStatus.CREATED, JobStatus.OPEN, JobStatus.ACCEPTED,
                JobStatus.IN_PROGRESS, JobStatus.COMPLETED
            ]
        )

        completed_jobs = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        total_spent = sum(
            float(bico_certo.w3.from_wei(job['data'][3] + job['data'][4], 'ether'))
            for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.APPROVED
        )

        providers_hired = len(set(
            job['data'][2] for job in client_jobs
            if job['data'][2] != '0x0000000000000000000000000000000000000000'
        ))

        pending_approvals = sum(
            1 for job in client_jobs
            if JobStatus(job['data'][9]) == JobStatus.COMPLETED
        )

        completion_rate = int((completed_jobs / len(client_jobs) * 100) if client_jobs else 0)

        spending_by_category = _calculate_spending_by_category(client_jobs)
        favorite_category = spending_by_category[0]["category"] if spending_by_category else "N/A"

        dashboard_data = {
            "activeJobs": active_jobs,
            "completedJobs": completed_jobs,
            "totalSpent": total_spent,
            "providersHired": providers_hired,
            "pendingApprovals": pending_approvals,
            "monthlySpending": _calculate_monthly_data(client_jobs, is_provider=False),
            "spendingByCategory": spending_by_category,
            "metrics": {
                "clientRating": round(client_average_rating, 2),
                "completionRate": completion_rate,
                "favoriteCategory": favorite_category
            }
        }

        excel_buffer = ReportGenerator.generate_client_excel(dashboard_data, current_user.full_name)

        filename = f"dashboard_cliente_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar Excel: {str(e)}")


def _calculate_monthly_data(jobs: List[Dict], is_provider: bool = True, months: int = 6) -> List[Dict]:
    """Calcula dados mensais (ganhos ou gastos)"""
    monthly = defaultdict(float)

    for job in jobs:
        try:
            job_data = job['data']
            status = JobStatus(job_data[9])

            if status != JobStatus.APPROVED:
                continue

            completed_at = job_data[7]
            if completed_at == 0:
                continue

            date = datetime.fromtimestamp(completed_at)
            month_key = date.strftime('%b')

            if is_provider:
                amount = float(bico_certo.w3.from_wei(job_data[3], 'ether'))
            else:
                amount = float(bico_certo.w3.from_wei(job_data[3] + job_data[4], 'ether'))

            monthly[month_key] += amount
        except Exception:
            continue

    result = []
    now = datetime.now()
    for i in range(months):
        date = now - timedelta(days=30 * i)
        month_key = date.strftime('%b')
        result.insert(0, {
            "month": month_key,
            "value": round(monthly.get(month_key, 0), 2)
        })

    return result


def _calculate_category_performance(jobs: List[Dict]) -> List[Dict]:
    """Calcula performance por categoria"""
    categories = defaultdict(lambda: {"count": 0, "earnings": 0.0})

    for job in jobs:
        try:
            job_data = job['data']
            status = JobStatus(job_data[9])

            if status != JobStatus.APPROVED:
                continue

            category = job_data[10]
            categories[category]["count"] += 1
            categories[category]["earnings"] += float(bico_certo.w3.from_wei(job_data[3], 'ether'))
        except Exception:
            continue

    result = [
        {
            "category": cat,
            "count": data["count"],
            "earnings": round(data["earnings"], 2)
        }
        for cat, data in categories.items()
    ]
    result.sort(key=lambda x: x["earnings"], reverse=True)

    return result[:5]


def _calculate_recent_activity(jobs: List[Dict], days: int = 7) -> List[Dict]:
    """Calcula atividade recente (últimos N dias)"""
    activity = defaultdict(int)
    cutoff_date = datetime.now() - timedelta(days=days)

    for job in jobs:
        try:
            job_data = job['data']
            completed_at = job_data[7]

            if completed_at == 0:
                continue

            date = datetime.fromtimestamp(completed_at)
            if date < cutoff_date:
                continue

            date_key = date.strftime('%Y-%m-%d')
            activity[date_key] += 1
        except Exception:
            continue

    result = []
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_key = date.strftime('%Y-%m-%d')
        result.insert(0, {
            "date": date_key,
            "jobs": activity.get(date_key, 0)
        })

    return result


def _calculate_spending_by_category(jobs: List[Dict]) -> List[Dict]:
    """Calcula gastos por categoria"""
    categories = defaultdict(lambda: {"count": 0, "spent": 0.0})

    for job in jobs:
        try:
            job_data = job['data']
            status = JobStatus(job_data[9])

            if status != JobStatus.APPROVED:
                continue

            category = job_data[10]
            categories[category]["count"] += 1
            categories[category]["spent"] += float(bico_certo.w3.from_wei(job_data[3] + job_data[4], 'ether'))
        except Exception:
            continue

    result = [
        {
            "category": cat,
            "count": data["count"],
            "spent": round(data["spent"], 2)
        }
        for cat, data in categories.items()
    ]
    result.sort(key=lambda x: x["spent"], reverse=True)

    return result[:5]


def _calculate_jobs_by_status(jobs: List[Dict]) -> List[Dict]:
    """Calcula distribuição de jobs por status"""
    status_count = defaultdict(int)
    total = len(jobs)

    for job in jobs:
        try:
            job_data = job['data']
            status = JobStatus(job_data[9]).name.lower()
            status_count[status] += 1
        except Exception:
            continue

    result = []
    for status, count in status_count.items():
        percentage = (count / total * 100) if total > 0 else 0
        result.append({
            "status": status,
            "count": count,
            "percentage": round(percentage, 1)
        })

    return result


def _get_recent_jobs(jobs: List[Dict], limit: int = 10, db: Session = None) -> List[Dict]:
    """Retorna jobs recentes com dados do IPFS e nome do provider"""
    sorted_jobs = sorted(jobs, key=lambda x: x['data'][5], reverse=True)

    result = []
    for job in sorted_jobs[:limit]:
        try:
            job_id = job['id']
            job_data = job['data']
            status = JobStatus(job_data[9])

            job_obj = bico_certo.get_job(job_id)

            ipfs_data = {}
            try:
                ipfs_data = ipfs_service.get_job_data(job_obj.ipfs_hash)
            except Exception:
                ipfs_data = {
                    'title': 'Serviço sem título',
                    'category': job_obj.service_type
                }

            provider_name = "Provider sem nome"
            provider_address = job_obj.provider

            if provider_address and provider_address != '0x0000000000000000000000000000000000000000':
                try:
                    if db:
                        wallet = db.query(Wallet).filter(
                            Wallet.address == provider_address
                        ).first()

                        if wallet and wallet.user:
                            provider_name = wallet.user.full_name
                        else:
                            provider_name = f"{provider_address[:6]}...{provider_address[-4:]}"
                    else:
                        provider_name = f"{provider_address[:6]}...{provider_address[-4:]}"
                except Exception:
                    provider_name = f"{provider_address[:6]}...{provider_address[-4:]}"

            job_title = ipfs_data[2]['data']['title'].title()
            category = job_obj.service_type
            full_title = f"{job_title} - {category}"

            result.append({
                "title": full_title,
                "provider": provider_name,
                "date": datetime.fromtimestamp(job_obj.created_at).strftime('%Y-%m-%d'),
                "value": float(job_obj.amount + job_obj.platform_fee),
                "status": status.name.lower()
            })

        except Exception:
            continue

    return result


def _get_motivation_message(
        average_rating: float,
        jobs_trend: float,
        earnings_trend: float,
        completed_jobs: int,
        proposal_acceptance_rate: int
) -> str:
    """Gera mensagem de motivação baseada no desempenho do provider"""

    if average_rating >= 4.5 and jobs_trend > 20 and earnings_trend > 20:
        return "Você está arrasando! Continue assim! 🚀"

    if average_rating >= 4.0 and (jobs_trend > 10 or earnings_trend > 10):
        return "Seu desempenho está ótimo! 🌟"

    if jobs_trend > 0 or earnings_trend > 0:
        return "Você está crescendo! Continue evoluindo! 📈"

    if proposal_acceptance_rate > 70:
        return "Suas propostas são muito valorizadas! 💪"

    if average_rating >= 4.0:
        return "Seus clientes adoram seu trabalho! ⭐"

    if completed_jobs >= 10:
        return "Experiência consolidada na plataforma! 🎯"

    if completed_jobs < 5:
        return "Bem-vindo! Vamos começar sua jornada! 🎉"

    if jobs_trend < -10 or earnings_trend < -10:
        return "Hora de revisar suas estratégias! 💡"

    return "Continue trabalhando e crescendo! 💼"