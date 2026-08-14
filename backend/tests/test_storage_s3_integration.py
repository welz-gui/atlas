"""S3 de verdade, contra MinIO (§6.6 — item D6).

**Pula quando `S3_ENDPOINT_URL` não está configurado**, e é de propósito: sem
serviço, o teste mediria o dublê e não a integração.

O que a suíte já cobria era **contrato**: que `S3Storage` recusa construir sem
bucket, e que a interface se comporta. O que faltava é o que só um servidor
responde — se a chave gravada é a chave lida, se objeto inexistente vira
`ObjectNotFound` em vez de exceção do boto3, se o `defer_commit` de fato não
publica nada antes da hora.

Roda no job `integracao` da CI, com MinIO como serviço.
"""

import os
import uuid

import pytest

from app.services.storage import ObjectNotFound, S3Storage, build_key

S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")

pytestmark = pytest.mark.skipif(
    not S3_ENDPOINT,
    reason="Sem S3_ENDPOINT_URL: não há servidor S3 para exercitar.",
)


@pytest.fixture(scope="module")
def bucket():
    """Garante o bucket, criando-o se o servidor ainda não o tiver."""
    import boto3
    from botocore.exceptions import ClientError

    nome = os.environ.get("S3_BUCKET", "atlas-integracao")
    cliente = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("S3_REGION") or "us-east-1",
    )
    try:
        cliente.head_bucket(Bucket=nome)
    except ClientError:
        cliente.create_bucket(Bucket=nome)
    return nome


@pytest.fixture
def storage(bucket):
    return S3Storage(bucket=bucket, prefix=f"teste-{uuid.uuid4().hex[:8]}/")


def _gravar(storage, key: str, conteudo: bytes) -> int:
    writer = storage.writer(key)
    with writer:
        writer.write(conteudo)
    return writer.result.size_bytes


# --- Ida e volta -------------------------------------------------------------


def test_o_que_foi_gravado_e_o_que_se_le(storage):
    key = build_key("org-1", "proj-1", "memorial.pdf")
    conteudo = b"%PDF-1.4 conteudo de integracao"

    tamanho = _gravar(storage, key, conteudo)
    assert tamanho == len(conteudo)

    lido = b"".join(storage.reader(key))
    assert lido == conteudo


def test_conteudo_grande_atravessa_em_blocos(storage):
    """Um memorial real não cabe num pedaço só."""
    key = build_key("org-1", "proj-1", "grande.pdf")
    conteudo = b"x" * (5 * 1024 * 1024 + 17)

    _gravar(storage, key, conteudo)

    lido = b"".join(storage.reader(key))
    assert len(lido) == len(conteudo)
    assert lido == conteudo


def test_hash_confere_com_o_conteudo_gravado(storage):
    import hashlib

    key = build_key("org-1", "proj-1", "com-hash.pdf")
    conteudo = b"conteudo para conferir o hash"

    writer = storage.writer(key)
    with writer:
        writer.write(conteudo)

    assert writer.result.sha256 == hashlib.sha256(conteudo).hexdigest()


# --- Ausência ----------------------------------------------------------------


def test_chave_inexistente_vira_ObjectNotFound(storage):
    """Não pode vazar `ClientError` do boto3 para o chamador."""
    with pytest.raises(ObjectNotFound):
        list(storage.reader("nao/existe.pdf"))


def test_apagar_o_que_nao_existe_nao_explode(storage):
    """Expurgo de arquivo já ausente é caso normal, não erro (§6.6)."""
    assert storage.delete("nao/existe.pdf") is False


# --- Expurgo -----------------------------------------------------------------


def test_apagar_remove_do_servidor(storage):
    key = build_key("org-1", "proj-1", "para-expurgar.pdf")
    _gravar(storage, key, b"conteudo efemero")

    assert storage.delete(key) is True
    with pytest.raises(ObjectNotFound):
        list(storage.reader(key))


# --- Escrita interrompida ----------------------------------------------------


def test_gravacao_interrompida_nao_publica_objeto(storage):
    """A falha no meio não pode deixar meio arquivo legível no bucket."""
    key = build_key("org-1", "proj-1", "interrompido.pdf")

    with pytest.raises(RuntimeError):
        writer = storage.writer(key)
        with writer:
            writer.write(b"primeiro pedaco")
            raise RuntimeError("falha no meio do upload")

    with pytest.raises(ObjectNotFound):
        list(storage.reader(key))
