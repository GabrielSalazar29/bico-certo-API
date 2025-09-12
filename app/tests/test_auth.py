"""
Testes automatizados para os endpoints de autenticação
Arquivo: tests/test_auth.py
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, UTC
import uuid
import json
from unittest.mock import Mock, patch, MagicMock

# Imports do projeto
from app.main import app
from app.config.database import Base, get_db
from app.model.user import User, RefreshToken
from app.model.device import Device
from app.model.session import Session
from app.util.security import hash_password
from app.auth.jwt_handler import create_tokens
from app.config.settings import settings

# Configuração do banco de dados de teste
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Fixtures
@pytest.fixture(scope="function")
def test_db():
    """Cria banco de dados de teste limpo para cada teste"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Cria sessão de banco de dados para teste"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Cria cliente de teste com banco de dados mockado"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis():
    """Mock do Redis para testes"""
    with patch('app.config.redis_config.get_redis') as mock:
        redis_mock = MagicMock()
        redis_mock.incr.return_value = 1
        redis_mock.expire.return_value = True
        redis_mock.ttl.return_value = 60
        mock.return_value = redis_mock
        yield redis_mock


@pytest.fixture
def sample_user_data():
    """Dados de usuário para teste"""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }


@pytest.fixture
def sample_device_info():
    """Informações de dispositivo para teste"""
    return {
        "device_id": str(uuid.uuid4()),
        "platform": "android",
        "model": "Pixel 5",
        "os_version": "12",
        "app_version": "1.0.0"
    }


@pytest.fixture
def existing_user(db_session, sample_user_data):
    """Cria um usuário existente no banco"""
    user = User(
        email=sample_user_data["email"],
        full_name=sample_user_data["full_name"],
        password_hash=hash_password(sample_user_data["password"]),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ==================== TESTES DE REGISTRO ====================

class TestRegister:
    """Testes para o endpoint de registro"""

    def test_register_success(self, client, sample_user_data, mock_redis):
        """Teste de registro bem-sucedido"""
        response = client.post("/auth/register", json=sample_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Usuário criado com sucesso! Verifique seu email."
        assert data["data"]["email"] == sample_user_data["email"]
        assert data["data"]["full_name"] == sample_user_data["full_name"]
        assert "user_id" in data["data"]

    def test_register_duplicate_email(self, client, existing_user, sample_user_data, mock_redis):
        """Teste de registro com email duplicado"""
        response = client.post("/auth/register", json=sample_user_data)

        assert response.status_code == 422
        data = response.json()
        assert "Este email já está cadastrado" in str(data)

    def test_register_invalid_email_format(self, client, mock_redis):
        """Teste de registro com formato de email inválido"""
        invalid_data = {
            "email": "invalid-email",
            "password": "TestPassword123!",
            "full_name": "Test User"
        }
        response = client.post("/auth/register", json=invalid_data)

        assert response.status_code == 422
        data = response.json()
        assert "email" in str(data).lower()

    def test_register_disposable_email(self, client, mock_redis):
        """Teste de registro com email temporário"""
        disposable_data = {
            "email": "test@tempmail.com",
            "password": "TestPassword123!",
            "full_name": "Test User"
        }
        response = client.post("/auth/register", json=disposable_data)

        assert response.status_code == 422
        data = response.json()
        assert "temporários não são permitidos" in str(data)

    def test_register_weak_password(self, client, mock_redis):
        """Teste de registro com senha fraca"""
        weak_password_data = {
            "email": "test@example.com",
            "password": "weak",
            "full_name": "Test User"
        }
        response = client.post("/auth/register", json=weak_password_data)

        assert response.status_code == 422
        data = response.json()
        assert "Senha" in str(data)

    def test_register_rate_limit(self, client, sample_user_data):
        """Teste de rate limiting no registro"""
        with patch('app.middleware.rate_limiter.RateLimiter.__call__') as mock_limiter:
            # Simula rate limit excedido
            from app.util.exceptions import RateLimitException
            mock_limiter.side_effect = RateLimitException(retry_after=60)

            response = client.post("/auth/register", json=sample_user_data)
            assert response.status_code == 429


# ==================== TESTES DE LOGIN ====================

class TestLogin:
    """Testes para o endpoint de login"""

    def test_login_success(self, client, existing_user, sample_user_data, sample_device_info, mock_redis):
        """Teste de login bem-sucedido"""
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
        assert data["data"]["user"]["email"] == sample_user_data["email"]

    def test_login_wrong_password(self, client, existing_user, sample_user_data, sample_device_info, mock_redis):
        """Teste de login com senha incorreta"""
        login_data = {
            "email": sample_user_data["email"],
            "password": "WrongPassword123!",
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "Email ou senha incorretos" in str(data)

    def test_login_nonexistent_user(self, client, sample_device_info, mock_redis):
        """Teste de login com usuário inexistente"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "TestPassword123!",
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "Email ou senha incorretos" in str(data)

    def test_login_account_lockout(self, client, db_session, sample_user_data, sample_device_info, mock_redis):
        """Teste de bloqueio de conta após múltiplas tentativas falhas"""
        # Cria usuário com tentativas falhas
        user = User(
            email="locked@example.com",
            full_name="Locked User",
            password_hash=hash_password("TestPassword123!"),
            failed_login_attempts=4,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

        # Tenta login com senha errada (5ª tentativa)
        login_data = {
            "email": "locked@example.com",
            "password": "WrongPassword",
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 403
        data = response.json()
        assert "bloqueada" in str(data).lower()

    def test_login_inactive_user(self, client, db_session, sample_device_info, mock_redis):
        """Teste de login com usuário inativo"""
        # Cria usuário inativo
        user = User(
            email="inactive@example.com",
            full_name="Inactive User",
            password_hash=hash_password("TestPassword123!"),
            is_active=False
        )
        db_session.add(user)
        db_session.commit()

        login_data = {
            "email": "inactive@example.com",
            "password": "TestPassword123!",
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "inativo" in str(data).lower()

    def test_login_creates_new_device(self, client, db_session, existing_user, sample_user_data, sample_device_info,
                                      mock_redis):
        """Teste se login cria novo dispositivo"""
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
            "device_info": sample_device_info
        }

        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200

        # Verifica se dispositivo foi criado
        device = db_session.query(Device).filter(
            Device.user_id == existing_user.id
        ).first()

        assert device is not None
        assert device.platform == sample_device_info["platform"]
        assert device.model == sample_device_info["model"]


# ==================== TESTES DE REFRESH TOKEN ====================

class TestRefreshToken:
    """Testes para o endpoint de refresh token"""

    def test_refresh_token_success(self, client, db_session, existing_user):
        """Teste de refresh token bem-sucedido"""
        # Cria refresh token válido
        tokens = create_tokens(existing_user.id, existing_user.email)
        refresh_token = RefreshToken(
            user_id=existing_user.id,
            token=tokens["refresh_token"],
            expires_at=tokens["refresh_expires_at"],
            revoked=False
        )
        db_session.add(refresh_token)
        db_session.commit()

        response = client.post("/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, client):
        """Teste com refresh token inválido"""
        response = client.post("/auth/refresh", json={
            "refresh_token": "invalid_token"
        })

        assert response.status_code == 401
        data = response.json()
        assert "inválido" in str(data).lower()

    def test_refresh_token_expired(self, client, db_session, existing_user):
        """Teste com refresh token expirado"""
        # Cria refresh token expirado
        expired_token = RefreshToken(
            user_id=existing_user.id,
            token="expired_token",
            expires_at=datetime.now(UTC) - timedelta(days=1),
            revoked=False
        )
        db_session.add(expired_token)
        db_session.commit()

        response = client.post("/auth/refresh", json={
            "refresh_token": "expired_token"
        })

        assert response.status_code == 401
        data = response.json()
        assert "expirado" in str(data).lower()

    def test_refresh_token_revoked(self, client, db_session, existing_user):
        """Teste com refresh token revogado"""
        # Cria refresh token revogado
        revoked_token = RefreshToken(
            user_id=existing_user.id,
            token="revoked_token",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked=True
        )
        db_session.add(revoked_token)
        db_session.commit()

        response = client.post("/auth/refresh", json={
            "refresh_token": "revoked_token"
        })

        assert response.status_code == 401


# ==================== TESTES DE LOGOUT ====================

class TestLogout:
    """Testes para o endpoint de logout"""

    def test_logout_single_device(self, client, existing_user):
        """Teste de logout de dispositivo único"""
        # Cria token de acesso
        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Logout realizado com sucesso" in data["message"]

    def test_logout_all_devices(self, client, db_session, existing_user):
        """Teste de logout de todos os dispositivos"""
        # Cria múltiplas sessões
        for i in range(3):
            session = Session(
                user_id=existing_user.id,
                device_id=None,
                access_token_jti=str(uuid.uuid4()),
                refresh_token=f"token_{i}",
                ip_address="127.0.0.1",
                user_agent="test",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                is_active=True
            )
            db_session.add(session)
        db_session.commit()

        # Cria token de acesso
        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.post(
            "/auth/logout?all_devices=true",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "3 dispositivos" in data["message"]

    def test_logout_without_token(self, client):
        """Teste de logout sem token"""
        response = client.post("/auth/logout")
        assert response.status_code == 403  # Sem autorização


# ==================== TESTES DO ENDPOINT /me ====================

class TestGetMe:
    """Testes para o endpoint /me"""

    def test_get_me_success(self, client, db_session, existing_user):
        """Teste de obtenção de dados do usuário atual"""
        # Cria token e sessão
        tokens = create_tokens(existing_user.id, existing_user.email)

        # Cria sessão ativa
        session = Session(
            user_id=existing_user.id,
            device_id=None,
            access_token_jti=str(uuid.uuid4()),
            refresh_token=tokens["refresh_token"],
            ip_address="127.0.0.1",
            user_agent="test",
            expires_at=datetime.now(UTC) + timedelta(days=1),
            is_active=True
        )
        db_session.add(session)
        db_session.commit()

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["user"]["email"] == existing_user.email
        assert data["data"]["security"]["active_sessions"] == 1

    def test_get_me_unauthorized(self, client):
        """Teste de acesso não autorizado ao /me"""
        response = client.get("/auth/me")
        assert response.status_code == 403


# ==================== TESTES DE DISPOSITIVOS ====================

class TestDevices:
    """Testes para endpoints de dispositivos"""

    def test_list_devices(self, client, db_session, existing_user):
        """Teste de listagem de dispositivos"""
        # Cria dispositivos
        for i in range(2):
            device = Device(
                user_id=existing_user.id,
                device_id=f"device_{i}",
                platform="android",
                model=f"Model {i}",
                fingerprint=f"fingerprint_{i}",
                trusted=i == 0
            )
            db_session.add(device)
        db_session.commit()

        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.get(
            "/auth/devices",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["platform"] == "android"

    def test_remove_device(self, client, db_session, existing_user):
        """Teste de remoção de dispositivo"""
        # Cria dispositivo
        device = Device(
            user_id=existing_user.id,
            device_id="device_to_remove",
            platform="ios",
            model="iPhone 12",
            fingerprint="unique_fingerprint"
        )
        db_session.add(device)
        db_session.commit()

        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.delete(
            f"/auth/devices/{device.id}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Device removido"

        # Verifica se foi removido
        removed = db_session.query(Device).filter(Device.id == device.id).first()
        assert removed is None

    def test_remove_nonexistent_device(self, client, existing_user):
        """Teste de remoção de dispositivo inexistente"""
        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.delete(
            f"/auth/devices/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 404


# ==================== TESTES DE SESSÕES ====================

class TestSessions:
    """Testes para endpoints de sessões"""

    def test_list_sessions(self, client, db_session, existing_user):
        """Teste de listagem de sessões"""
        # Cria dispositivo
        device = Device(
            user_id=existing_user.id,
            device_id="test_device",
            platform="web",
            model="Chrome",
            fingerprint="test_fingerprint"
        )
        db_session.add(device)
        db_session.commit()

        # Cria sessões
        for i in range(2):
            session = Session(
                user_id=existing_user.id,
                device_id=device.id if i == 0 else None,
                access_token_jti=str(uuid.uuid4()),
                refresh_token=f"token_{i}",
                ip_address=f"192.168.1.{i}",
                user_agent="Mozilla/5.0",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                is_active=True
            )
            db_session.add(session)
        db_session.commit()

        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.get(
            "/auth/sessions",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert "sessões ativas" in data["message"]

    def test_revoke_session(self, client, db_session, existing_user):
        """Teste de revogação de sessão"""
        # Cria sessão
        session = Session(
            user_id=existing_user.id,
            device_id=None,
            access_token_jti=str(uuid.uuid4()),
            refresh_token="session_to_revoke",
            ip_address="127.0.0.1",
            user_agent="test",
            expires_at=datetime.now(UTC) + timedelta(days=1),
            is_active=True
        )
        db_session.add(session)
        db_session.commit()

        tokens = create_tokens(existing_user.id, existing_user.email)

        response = client.delete(
            f"/auth/sessions/{session.id}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "revogada com sucesso" in data["message"]

        # Verifica se foi revogada
        db_session.refresh(session)
        assert session.is_active is False
        assert session.revoked_at is not None


# ==================== TESTES DE INTEGRAÇÃO ====================

class TestIntegration:
    """Testes de integração entre endpoints"""

    def test_full_auth_flow(self, client, sample_user_data, sample_device_info, mock_redis):
        """Teste do fluxo completo de autenticação"""
        # 1. Registro
        register_response = client.post("/auth/register", json=sample_user_data)
        assert register_response.status_code == 200

        # 2. Login
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
            "device_info": sample_device_info
        }
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200

        login_data = login_response.json()
        access_token = login_data["data"]["access_token"]
        refresh_token = login_data["data"]["refresh_token"]

        # 3. Acessar /me
        me_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_response.status_code == 200

        # 4. Refresh token
        refresh_response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_response.status_code == 200

        # 5. Logout
        logout_response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert logout_response.status_code == 200

    def test_security_headers(self, client):
        """Teste de headers de segurança"""
        response = client.get("/")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in response.headers

    def test_request_id_header(self, client):
        """Teste de header X-Request-ID"""
        response = client.get("/")

        assert "X-Request-ID" in response.headers
        # Verifica se é um UUID válido
        request_id = response.headers["X-Request-ID"]
        uuid.UUID(request_id)  # Lança exceção se não for válido


# ==================== TESTES DE PERFORMANCE ====================

class TestPerformance:
    """Testes de performance e carga"""

    def test_concurrent_registrations(self, client, mock_redis):
        """Teste de registros concorrentes"""
        import concurrent.futures

        def register_user(index):
            user_data = {
                "email": f"user{index}@example.com",
                "password": "TestPassword123!",
                "full_name": f"User {index}"
            }
            return client.post("/auth/register", json=user_data)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(register_user, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 3  # Pelo menos 3 devem ter sucesso


# ==================== TESTES DE SEGURANÇA ====================

class TestSecurity:
    """Testes de segurança"""

    def test_sql_injection_attempt(self, client, sample_device_info, mock_redis):
        """Teste de tentativa de SQL injection"""
        malicious_data = {
            "email": "test@example.com",
            "password": "TestPassword123!",
            "full_name": "teste'; DROP TABLE users; --"
        }

        response = client.post("/auth/register", json=malicious_data)
        if response.status_code == 200:
            data = response.json()
            # Verifica se o script não é executado (está escapado)
            assert "DROP TABLE" not in json.dumps(data)

    def test_xss_attempt_in_registration(self, client, mock_redis):
        """Teste de tentativa de XSS no registro"""
        xss_data = {
            "email": "test@example.com",
            "password": "TestPassword123!",
            "full_name": "<script>alert('XSS')</script>"
        }

        response = client.post("/auth/register", json=xss_data)
        if response.status_code == 200:
            data = response.json()
            # Verifica se o script não é executado (está escapado)
            assert "<script>" not in json.dumps(data)

    def test_token_tampering(self, client, existing_user):
        """Teste de manipulação de token"""
        # Token inválido/manipulado
        tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )

        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])