import logging
import json
from datetime import datetime
from typing import Any, Dict
from ..config.settings import fuso_local

# Configurar logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AuditLogger:
    @staticmethod
    def log_auth_event(
            event_type: str,
            user_id: str = None,
            email: str = None,
            ip_address: str = None,
            device_id: str = None,
            success: bool = True,
            details: Dict[str, Any] = None
    ):
        """Log de eventos de autenticação para auditoria"""
        log_entry = {
            "timestamp": datetime.now(fuso_local).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "email": email,
            "ip_address": ip_address,
            "device_id": device_id,
            "success": success,
            "details": details or {}
        }

        # Log para arquivo específico de auditoria
        with open('logs/audit.log', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Log no logger principal também
        if success:
            logger.info(f"Auth Event: {event_type} - User: {email} - IP: {ip_address}")
        else:
            logger.warning(f"Auth Failed: {event_type} - User: {email} - IP: {ip_address}")