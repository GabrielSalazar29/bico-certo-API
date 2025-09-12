import re
from typing import Optional


class PasswordValidator:
    @staticmethod
    def validate(password: str) -> tuple[bool, Optional[str]]:
        """Valida força da senha"""
        if len(password) < 8:
            return False, "Senha deve ter pelo menos 8 caracteres"

        if not re.search(r"[A-Z]", password):
            return False, "Senha deve conter pelo menos uma letra maiúscula"

        if not re.search(r"[a-z]", password):
            return False, "Senha deve conter pelo menos uma letra minúscula"

        if not re.search(r"\d", password):
            return False, "Senha deve conter pelo menos um número"

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Senha deve conter pelo menos um caractere especial"

        return True, None


class EmailValidator:
    @staticmethod
    def validate(email: str) -> bool:
        """Valida formato de email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def is_disposable(email: str) -> bool:
        """Verifica se é email temporário/descartável"""
        disposable_domains = [
            'tempmail.com', 'throwaway.email', 'guerrillamail.com',
            '10minutemail.com', 'mailinator.com'
        ]
        domain = email.split('@')[1].lower()
        return domain in disposable_domains
