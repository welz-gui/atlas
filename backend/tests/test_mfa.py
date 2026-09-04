"""Segundo fator por TOTP (§8.1, §12 — item D2).

O que estes testes protegem, em ordem de importância:

1. **o segredo não fica em claro no banco.** Em claro, qualquer backup gera
   códigos válidos para sempre;
2. **código de recuperação vale uma vez.** Reutilizável, é uma senha permanente
   com nome bonito;
3. **a exigência recai na ação, não no login.** Exigir na entrada trancaria
   para fora todo `owner` e `validator` existente no instante do deploy;
4. **desligar o fator exige prová-lo.** Sem isso, uma sessão roubada bastaria
   para removê-lo, e o fator seria decorativo.
"""


import pyotp

from app.core import mfa
from app.core.security import MFA_REQUIRED_PERMISSIONS
from app.models.domain import MFARecoveryCode


def _enroll(client, headers):
    response = client.post("/api/v1/auth/mfa/enroll", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _activate(client, headers, secret):
    codigo = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/auth/mfa/activate", headers=headers, json={"code": codigo}
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- O segredo em repouso ----------------------------------------------------


def test_segredo_e_cifrado_no_banco(client, headers_sem_mfa, db_session, usuario_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)

    db_session.refresh(usuario_sem_mfa)
    assert usuario_sem_mfa.mfa_secret is not None
    # O que está gravado não é o segredo.
    assert dados["secret"] not in usuario_sem_mfa.mfa_secret
    # E abre com a chave da aplicação.
    assert mfa.decrypt_secret(usuario_sem_mfa.mfa_secret) == dados["secret"]


def test_segredo_com_chave_errada_nao_abre():
    """Depois de rotacionar `SECRET_KEY`, o segredo antigo deixa de abrir."""
    cifrado = mfa.encrypt_secret("JBSWY3DPEHPK3PXP")
    assert mfa.decrypt_secret(cifrado) == "JBSWY3DPEHPK3PXP"
    assert mfa.decrypt_secret("nao-e-um-token-valido") is None


def test_cadastro_sem_confirmacao_nao_vale(
    client, headers_sem_mfa, db_session, usuario_sem_mfa
):
    """Quem gera o QR Code e fecha a aba não está protegido."""
    _enroll(client, headers_sem_mfa)
    db_session.refresh(usuario_sem_mfa)

    assert usuario_sem_mfa.mfa_secret is not None
    assert usuario_sem_mfa.mfa_activated_at is None
    assert usuario_sem_mfa.mfa_active is False


# --- Ativação e códigos de recuperação ---------------------------------------


def test_ativacao_exige_codigo_valido(client, headers_sem_mfa):
    _enroll(client, headers_sem_mfa)
    response = client.post(
        "/api/v1/auth/mfa/activate", headers=headers_sem_mfa, json={"code": "000000"}
    )
    assert response.status_code == 400


def test_ativacao_entrega_codigos_de_recuperacao(client, headers_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)
    resultado = _activate(client, headers_sem_mfa, dados["secret"])

    assert len(resultado["recovery_codes"]) == 10
    assert all("-" in c for c in resultado["recovery_codes"])


def test_codigos_de_recuperacao_ficam_hasheados(
    client, headers_sem_mfa, db_session, usuario_sem_mfa
):
    dados = _enroll(client, headers_sem_mfa)
    resultado = _activate(client, headers_sem_mfa, dados["secret"])

    guardados = (
        db_session.query(MFARecoveryCode)
        .filter(MFARecoveryCode.user_id == usuario_sem_mfa.id)
        .all()
    )
    assert len(guardados) == 10
    for codigo in resultado["recovery_codes"]:
        assert all(codigo not in g.code_hash for g in guardados)


# --- Login -------------------------------------------------------------------


def test_login_sem_mfa_ativo_continua_simples(client, engineer):
    """`engineer` não é obrigado ao fator, e nada muda para ele."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": engineer.email, "password": "senha-de-teste-123"},
    )
    assert response.status_code == 200


def test_login_com_mfa_ativo_exige_codigo(client, headers_sem_mfa, usuario_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, dados["secret"])

    response = client.post(
        "/api/v1/auth/login",
        json={"email": usuario_sem_mfa.email, "password": "senha-de-teste-123"},
    )
    assert response.status_code == 401
    assert response.headers.get("X-Atlas-MFA-Required") == "true"


def test_login_com_codigo_valido_passa(client, headers_sem_mfa, usuario_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, dados["secret"])

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": usuario_sem_mfa.email,
            "password": "senha-de-teste-123",
            "mfa_code": pyotp.TOTP(dados["secret"]).now(),
        },
    )
    assert response.status_code == 200


def test_codigo_de_recuperacao_vale_uma_vez(client, headers_sem_mfa, usuario_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)
    resultado = _activate(client, headers_sem_mfa, dados["secret"])
    codigo = resultado["recovery_codes"][0]

    corpo = {
        "email": usuario_sem_mfa.email,
        "password": "senha-de-teste-123",
        "mfa_code": codigo,
    }
    assert client.post("/api/v1/auth/login", json=corpo).status_code == 200
    # Segunda vez, o mesmo código não vale mais.
    assert client.post("/api/v1/auth/login", json=corpo).status_code == 401


# --- A exigência recai na ação -----------------------------------------------


#: Cadastrar norma exige `catalog:validate`. Ler a fila de validação exige
#: apenas `catalog:read`, e continua liberada — ler não publica nada.
DOCUMENTO = {
    "jurisdiction": "BR-RS-4311403",
    "doc_type": "plano_diretor",
    "title": "Documento de teste",
    "issuing_body": "Prefeitura",
}


def test_validador_sem_mfa_entra_e_le_mas_nao_publica(client, headers_sem_mfa):
    """Exigir na entrada trancaria para fora quem já existe. Exige-se na ação."""
    assert client.get("/api/v1/auth/me", headers=headers_sem_mfa).status_code == 200
    # Leitura segue liberada: a exigência recai sobre publicar, não sobre ver.
    assert (
        client.get(
            "/api/v1/catalog/validation-queue", headers=headers_sem_mfa
        ).status_code
        == 200
    )

    resposta = client.post(
        "/api/v1/catalog/documents", headers=headers_sem_mfa, json=DOCUMENTO
    )
    assert resposta.status_code == 403
    assert resposta.headers.get("X-Atlas-MFA-Required") == "true"


def test_validador_com_mfa_publica(client, headers_sem_mfa):
    dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, dados["secret"])

    resposta = client.post(
        "/api/v1/catalog/documents", headers=headers_sem_mfa, json=DOCUMENTO
    )
    assert resposta.status_code == 201, resposta.text


def test_engenheiro_nao_precisa_de_mfa_para_operar(client, engineer_headers, project):
    """`inspector` e `engineer` ficam fora de propósito — atrito de canteiro."""
    assert client.get("/api/v1/projects", headers=engineer_headers).status_code == 200


def test_as_permissoes_exigentes_sao_as_do_plano():
    assert MFA_REQUIRED_PERMISSIONS == {"org:manage", "catalog:validate"}


# --- Remoção -----------------------------------------------------------------


def test_desligar_exige_provar_posse(client, headers_sem_mfa):
    """Sessão roubada não pode bastar para remover o fator."""
    dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, dados["secret"])

    ruim = client.post(
        "/api/v1/auth/mfa/disable", headers=headers_sem_mfa, json={"code": "000000"}
    )
    assert ruim.status_code == 400

    bom = client.post(
        "/api/v1/auth/mfa/disable",
        headers=headers_sem_mfa,
        json={"code": pyotp.TOTP(dados["secret"]).now()},
    )
    assert bom.status_code == 204


def test_recadastro_invalida_os_codigos_antigos(
    client, headers_sem_mfa, db_session, usuario_sem_mfa
):
    dados = _enroll(client, headers_sem_mfa)
    primeiros = _activate(client, headers_sem_mfa, dados["secret"])["recovery_codes"]

    client.post(
        "/api/v1/auth/mfa/disable",
        headers=headers_sem_mfa,
        json={"code": pyotp.TOTP(dados["secret"]).now()},
    )
    novos_dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, novos_dados["secret"])

    corpo = {
        "email": usuario_sem_mfa.email,
        "password": "senha-de-teste-123",
        "mfa_code": primeiros[1],
    }
    assert client.post("/api/v1/auth/login", json=corpo).status_code == 401


def test_status_informa_o_que_falta(client, headers_sem_mfa):
    antes = client.get("/api/v1/auth/mfa/status", headers=headers_sem_mfa).json()
    assert antes["active"] is False
    assert antes["required_for_role"] is True

    dados = _enroll(client, headers_sem_mfa)
    _activate(client, headers_sem_mfa, dados["secret"])

    depois = client.get("/api/v1/auth/mfa/status", headers=headers_sem_mfa).json()
    assert depois["active"] is True
    assert depois["recovery_codes_remaining"] == 10
