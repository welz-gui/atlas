"""De onde vêm os segredos, e rotação sem destruir dado (§12).

O que estes testes protegem:

1. **rotacionar não derruba quem já estava dentro** — token assinado com a
   chave anterior continua valendo durante a janela;
2. **rotacionar não destrói os segundos fatores.** Antes disto, trocar
   `SECRET_KEY` obrigava toda pessoa com MFA a recadastrar, o que tornava a
   rotação praticamente proibitiva;
3. **a janela se fecha sozinha**: cada uso migra o segredo para a chave atual;
4. **o backend `file` lê de onde os cofres entregam** — arquivo montado, e não
   variável na lista de processos.
"""


from app.core import mfa
from app.core.config import Settings
from app.core.secrets import read_secret


# --- De onde vêm ------------------------------------------------------------


def test_backend_env_le_do_ambiente(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "do-ambiente")

    assert read_secret("SECRET_KEY", "env", "/nao/usado") == "do-ambiente"


def test_backend_file_le_do_diretorio(tmp_path):
    """Nome do arquivo em minúsculas — convenção do Docker e do Kubernetes."""
    (tmp_path / "secret_key").write_text("do-arquivo", encoding="utf-8")

    assert read_secret("SECRET_KEY", "file", str(tmp_path)) == "do-arquivo"


def test_backend_file_remove_a_nova_linha_do_fim(tmp_path):
    """Editor e Docker acrescentam `\n`, e a assinatura simplesmente não confere."""
    (tmp_path / "secret_key").write_text("valor\n", encoding="utf-8")

    assert read_secret("SECRET_KEY", "file", str(tmp_path)) == "valor"


def test_segredo_ausente_devolve_none(tmp_path):
    assert read_secret("SECRET_KEY", "file", str(tmp_path)) is None


def test_ambiente_tem_precedencia_sobre_arquivo(monkeypatch, tmp_path):
    """Permite substituir um segredo pontualmente sem mexer no cofre."""
    (tmp_path / "secret_key").write_text("do-arquivo", encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY", "do-ambiente")
    monkeypatch.setenv("SECRETS_BACKEND", "file")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))

    assert Settings(_env_file=None).SECRET_KEY == "do-ambiente"


def test_configuracao_carrega_do_arquivo_quando_o_ambiente_nao_traz(
    monkeypatch, tmp_path
):
    (tmp_path / "secret_key").write_text("chave-do-cofre", encoding="utf-8")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRETS_BACKEND", "file")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))

    assert Settings(_env_file=None).SECRET_KEY == "chave-do-cofre"


# --- Rotação: o token -------------------------------------------------------


def _com_chaves(monkeypatch, atual, anterior=""):
    from app.core import security

    monkeypatch.setattr(security.settings, "SECRET_KEY", atual)
    monkeypatch.setattr(security.settings, "SECRET_KEY_PREVIOUS", anterior)
    return security


def test_token_da_chave_anterior_continua_valendo(monkeypatch):
    """Quem estava autenticado no instante da rotação não é derrubado."""
    security = _com_chaves(monkeypatch, "chave-velha")
    token = security.create_access_token("u1", "org1", "engineer")

    _com_chaves(monkeypatch, "chave-nova", anterior="chave-velha")
    assert security.decode_access_token(token)["sub"] == "u1"


def test_token_novo_usa_sempre_a_chave_atual(monkeypatch):
    security = _com_chaves(monkeypatch, "chave-nova", anterior="chave-velha")
    token = security.create_access_token("u1", "org1", "engineer")

    # Fim da janela: a anterior sai de cena e o token novo segue valendo.
    _com_chaves(monkeypatch, "chave-nova")
    assert security.decode_access_token(token) is not None


def test_fim_da_janela_invalida_o_token_antigo(monkeypatch):
    security = _com_chaves(monkeypatch, "chave-velha")
    token = security.create_access_token("u1", "org1", "engineer")

    _com_chaves(monkeypatch, "chave-nova")
    assert security.decode_access_token(token) is None


def test_token_de_chave_desconhecida_e_recusado(monkeypatch):
    security = _com_chaves(monkeypatch, "intrusa")
    forjado = security.create_access_token("u1", "org1", "owner")

    _com_chaves(monkeypatch, "chave-nova", anterior="chave-velha")
    assert security.decode_access_token(forjado) is None


# --- Rotação: o segundo fator -----------------------------------------------


def test_segredo_de_mfa_sobrevive_a_rotacao(monkeypatch):
    """O ponto do item: antes disto, rotacionar zerava todos os MFAs."""
    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-velha")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    cifrado = mfa.encrypt_secret("JBSWY3DPEHPK3PXP")

    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-nova")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "chave-velha")

    assert mfa.decrypt_secret(cifrado) == "JBSWY3DPEHPK3PXP"


def test_rotacao_recifra_para_a_chave_atual(monkeypatch):
    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-velha")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    cifrado = mfa.encrypt_secret("JBSWY3DPEHPK3PXP")

    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-nova")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "chave-velha")
    recifrado = mfa.rotate_secret(cifrado)

    assert recifrado != cifrado
    # E o recifrado abre sem a chave anterior — a janela pode fechar.
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    assert mfa.decrypt_secret(recifrado) == "JBSWY3DPEHPK3PXP"
    assert mfa.decrypt_secret(cifrado) is None


def test_segredo_de_chave_desconhecida_nao_abre(monkeypatch):
    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "outra-completamente")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    cifrado = mfa.encrypt_secret("JBSWY3DPEHPK3PXP")

    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-nova")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "chave-velha")

    assert mfa.decrypt_secret(cifrado) is None
    assert mfa.rotate_secret(cifrado) is None


# --- A rotação de ponta a ponta ---------------------------------------------


def test_pessoa_com_mfa_atravessa_a_rotacao(client, db_session, usuario_sem_mfa, monkeypatch):
    """O cenário inteiro, que era impossível antes deste item.

    Cadastra o segundo fator com uma chave, rotaciona, e verifica que a pessoa
    ainda entra — e que o segredo dela migrou sozinho para a chave nova, de modo
    que a anterior possa ser removida.
    """
    import pyotp
    from tests.conftest import auth_headers

    headers = auth_headers(client, usuario_sem_mfa.email)

    # 1. Cadastra o fator sob a chave velha.
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    dados = client.post("/api/v1/auth/mfa/enroll", headers=headers).json()
    client.post(
        "/api/v1/auth/mfa/activate",
        headers=headers,
        json={"code": pyotp.TOTP(dados["secret"]).now()},
    )
    db_session.refresh(usuario_sem_mfa)
    cifrado_antes = usuario_sem_mfa.mfa_secret

    # 2. Rotaciona: a chave de hoje vira a anterior.
    chave_velha = mfa.settings.SECRET_KEY
    monkeypatch.setattr(mfa.settings, "SECRET_KEY", "chave-rotacionada")
    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", chave_velha)

    # 3. A pessoa entra normalmente, com o mesmo aplicativo autenticador.
    resposta = client.post(
        "/api/v1/auth/login",
        json={
            "email": usuario_sem_mfa.email,
            "password": "senha-de-teste-123",
            "mfa_code": pyotp.TOTP(dados["secret"]).now(),
        },
    )
    assert resposta.status_code == 200, resposta.text

    # 4. E o segredo dela migrou para a chave nova.
    db_session.refresh(usuario_sem_mfa)
    assert usuario_sem_mfa.mfa_secret != cifrado_antes

    monkeypatch.setattr(mfa.settings, "SECRET_KEY_PREVIOUS", "")
    assert mfa.decrypt_secret(usuario_sem_mfa.mfa_secret) == dados["secret"]
