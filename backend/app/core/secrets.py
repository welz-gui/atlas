"""De onde vêm os segredos, e como rotacioná-los (§12).

Segue o padrão que o projeto já usa para storage, fila e antivírus: um backend
declarado por configuração, com o modo seguro como padrão.

    SECRETS_BACKEND=env    # padrão — variáveis de ambiente
    SECRETS_BACKEND=file   # arquivos em SECRETS_DIR

**Por que `file` importa mais do que parece.** Cofre nenhum entrega segredo ao
processo por API: AWS Secrets Manager, Vault, Doppler e Infisical entregam
todos por **arquivo montado** ou variável injetada. Suportar arquivo é o que
torna a aplicação compatível com qualquer um deles sem escolher nenhum — e sem
que o segredo passe pela lista de processos, onde `ps` o mostraria.

O nome do arquivo é o da variável em minúsculas: `SECRETS_DIR/secret_key`. É a
convenção do Docker Swarm e do Kubernetes, e é o que os cofres produzem.

**O que este módulo não faz:** buscar segredo em API de cofre, rotacionar
sozinho, ou auditar acesso. As três são funções do cofre escolhido, e escolher
é decisão de negócio — ver `docs/OPERACAO.md`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class SecretNotFound(RuntimeError):
    """O segredo não estava onde o backend configurado manda procurar."""


def read_secret(name: str, backend: str, directory: str) -> Optional[str]:
    """Lê um segredo, ou devolve `None` quando não há.

    `None` em vez de exceção porque a ausência é legítima: em desenvolvimento a
    maioria dos segredos não existe, e quem decide se isso é erro é
    `Settings.model_post_init`, que conhece o ambiente.
    """
    if backend != "file":
        return os.environ.get(name) or None

    caminho = Path(directory) / name.lower()
    if not caminho.is_file():
        return None

    # `strip` do fim: editores e o próprio Docker acrescentam nova linha, e um
    # segredo com `\n` no fim falha de formas difíceis de diagnosticar — a
    # assinatura simplesmente não confere.
    conteudo = caminho.read_text(encoding="utf-8").rstrip("\r\n")
    return conteudo or None
