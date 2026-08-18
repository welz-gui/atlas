"""Segundo fator por TOTP (§8.1, §12 — item D2).

Três decisões governam o módulo, e todas vêm do mesmo princípio: **o banco
sozinho não pode bastar para se passar por alguém.**

**1. O segredo é cifrado em repouso.** Um TOTP guardado em claro transforma
qualquer cópia do banco — um backup, um dump de depuração, um `SELECT` de
suporte — em capacidade de gerar códigos válidos para sempre. A chave de
cifragem deriva de `SECRET_KEY` e vive só no ambiente, de modo que banco e
chave precisem vazar juntos.

**2. Os códigos de recuperação são hasheados como senha.** Argon2id, o mesmo
tratamento da senha, pelo mesmo motivo: eles substituem o segundo fator, então
valem tanto quanto ele.

**3. Uso único, marcado no consumo.** Código de recuperação reutilizável é uma
senha permanente com nome bonito.

Sobre a rotação de `SECRET_KEY`: trocá-la invalida os segredos cifrados, e quem
tinha MFA precisa recadastrar. É consequência conhecida e está em
`docs/OPERACAO.md`, junto do aviso de que a rotação já derruba todas as sessões.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import List, Optional

import pyotp
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings
from app.core.security import hash_password, verify_password

#: Emissor exibido no aplicativo autenticador.
ISSUER = "Atlas"

#: Quantos códigos de recuperação são entregues no cadastro.
RECOVERY_CODE_COUNT = 10

#: Tolerância de relógio, em janelas de 30 s para cada lado. Uma janela cobre
#: dessincronia comum de celular sem alargar demais a superfície.
VALID_WINDOW = 1


def _key_from(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> MultiFernet:
    """Cifragem derivada de `SECRET_KEY`, aceitando também a chave anterior.

    `MultiFernet` cifra **sempre com a primeira** e decifra com qualquer uma.
    É o que torna a rotação uma operação e não um evento destrutivo: enquanto
    `SECRET_KEY_PREVIOUS` estiver definida, o segredo cifrado com a chave velha
    continua abrindo, e cada uso o migra para a nova — ver `rotate_secret`.

    Antes disto, rotacionar `SECRET_KEY` destruía todos os segundos fatores, e
    a rotação era tecnicamente possível e praticamente proibitiva.
    """
    chaves = [_key_from(settings.SECRET_KEY)]
    if settings.SECRET_KEY_PREVIOUS:
        chaves.append(_key_from(settings.SECRET_KEY_PREVIOUS))
    return MultiFernet(chaves)


def rotate_secret(encrypted: str) -> Optional[str]:
    """Recifra com a chave atual, se ainda estiver na anterior.

    Devolve `None` quando o valor não abre com nenhuma das chaves — mesmo
    contrato de `decrypt_secret`.
    """
    try:
        return _fernet().rotate(encrypted.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        return None


def generate_secret() -> str:
    """Segredo TOTP novo, em base32."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted: str) -> Optional[str]:
    """Devolve `None` quando o segredo não abre com a chave atual.

    Acontece depois de uma rotação de `SECRET_KEY`. Devolver `None` em vez de
    levantar deixa a decisão com quem chama: para o Atlas, é tratar como "sem
    MFA cadastrado" e pedir novo cadastro.
    """
    try:
        return _fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def provisioning_uri(secret: str, email: str) -> str:
    """URI `otpauth://` para o aplicativo autenticador ler."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify_code(secret: str, code: str) -> bool:
    """Confere um código TOTP, com tolerância de uma janela para cada lado."""
    if not code or not code.strip().isdigit():
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=VALID_WINDOW)


def generate_recovery_codes(quantity: int = RECOVERY_CODE_COUNT) -> List[str]:
    """Códigos legíveis, entregues **uma única vez** a quem cadastra.

    O formato com hífen existe para serem transcritos à mão sem erro — quem os
    usa está, por definição, sem o celular.
    """
    codes = []
    for _ in range(quantity):
        bruto = secrets.token_hex(5).upper()  # 10 caracteres
        codes.append(f"{bruto[:5]}-{bruto[5:]}")
    return codes


def hash_recovery_code(code: str) -> str:
    """Argon2id, o mesmo da senha: o código vale tanto quanto ela."""
    return hash_password(_normalize_recovery(code))


def verify_recovery_code(code: str, code_hash: str) -> bool:
    return verify_password(_normalize_recovery(code), code_hash)


def _normalize_recovery(code: str) -> str:
    """Aceita com ou sem hífen, em qualquer caixa — quem digita está sob estresse."""
    return code.strip().upper().replace("-", "").replace(" ", "")
