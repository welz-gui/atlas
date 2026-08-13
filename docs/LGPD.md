# Dado pessoal no Atlas

Inventário do que o sistema guarda, o que o código já faz a respeito, e o que
continua dependendo de decisão humana.

> ## O que este documento não é
>
> **Não é política de privacidade, não é parecer jurídico e não é contrato.**
>
> Escrever uma política de privacidade sem advogado seria o mesmo defeito que
> preencher `source.article` sem abrir a lei publicada: um texto plausível,
> indistinguível de um correto para quem lê, e que alguém trataria como válido.
> O projeto recusa isso no catálogo regulatório — recusa aqui pela mesma razão.
>
> O que está abaixo é **levantamento técnico**: o que existe no banco, o que o
> código faz, e a lista do que falta decidir. Serve de insumo para quem tem
> competência para redigir os documentos, não de substituto.

---

## Inventário — o que existe hoje

Levantado do modelo (`backend/app/models/domain.py`), não de memória.

| Onde | Dado | De quem |
|---|---|---|
| `users` | nome, e-mail, hash de senha, último login | quem opera o sistema |
| `projects` | `owner_name`, **`owner_document`**, `contractor_name` | proprietário e contratante |
| `projects` | `technical_responsible_name`, `technical_responsible_registry` | responsável técnico (CREA/CAU) |
| `documents` | `original_filename` e o **conteúdo** dos PDFs de projeto | qualquer um |
| `daily_logs` | efetivo próprio e terceirizado, ocorrências em texto livre | trabalhadores em obra |
| `rule_validation_events`, `protocol_events` | `actor_name` por transição | quem operou |
| `ai_interactions` | pergunta, resposta e contexto de cada chamada | quem perguntou |
| `job_records` | `payload` de cada trabalho | quem solicitou |

**A linha que mais pesa é `projects.owner_document`.** Documento de
identificação de um terceiro que nunca interagiu com o Atlas e não tem como
saber que está aqui. `contractor_name` e `technical_responsible_registry` têm o
mesmo problema em grau menor.

---

## O que o código já faz

| Mecanismo | Onde |
|---|---|
| Expurgo apaga o arquivo, **nunca o registro** | `services/retention.py` |
| Expurgo de pergunta e resposta de IA, preservando proveniência | `POST /privacy/purge-ai-interactions` |
| Expurgo de payload e resultado de trabalhos encerrados | `POST /privacy/purge-job-records` |
| Eliminação de dado pessoal de terceiro, preservando a trilha | `POST /projects/{id}/anonymize` |
| Isolamento entre organizações responde 404, nunca 403 | `api/deps.py` |
| Senha com argon2id; senha em claro nunca é persistida nem logada | `core/security.py` |
| Segredos redigidos em `repr` — não vazam em traceback | `core/config.py` |
| Proveniência de IA registrada por chamada | tabela `ai_interactions` |

### O caso difícil, e como foi resolvido

`AnalysisRun` e `ProjectVersion` são **append-only por desenho** (I5, I6). É o
que permite responder, daqui a três anos, qual versão foi protocolada e o que o
motor disse sobre ela.

Um pedido de eliminação não pode virar `DELETE` ali: destruiria a prova de um
ato técnico que aconteceu e **continua produzindo efeito**, porque o alvará foi
emitido com base nele.

A resposta implementada é **redigir o dado pessoal e preservar o registro**.
Depois de `POST /projects/{id}/anonymize`:

- o empreendimento continua existindo, com endereço, zona e parâmetros;
- as análises continuam íntegras, com o mesmo `content_hash`;
- nome e documento do proprietário deixam de estar em qualquer lugar;
- fica gravado **quando** e **por quê** — a anonimização também é ato que
  precisa de trilha.

O endpoint **não decide se o pedido procede**. Isso é avaliação jurídica, feita
por gente; a razão informada é o registro dessa decisão.

### Retenção

Três janelas, todas **desligadas por padrão** (`0`):

```
OBSOLETE_RETENTION_DAYS         documentos obsoletos
AI_INTERACTION_RETENTION_DAYS   pergunta e resposta do assistente
JOB_RECORD_RETENTION_DAYS       payload e resultado de trabalhos
```

Zero significa **guardar indefinidamente**. É o padrão seguro contra perda
acidental, e é o padrão errado do ponto de vista de proteção de dados: dado
pessoal guardado sem prazo é dado pessoal guardado para sempre. **Definir esses
prazos é uma das decisões pendentes.**

---

## O que falta, e é decisão humana

Nada disto se resolve com código.

| # | Decisão | Por que trava |
|---|---|---|
| 1 | **Operador ou controlador?** | Muda quem responde pelo quê. O Atlas trata por conta do construtor, ou por conta própria? |
| 2 | **Base legal por categoria** | Execução de contrato, obrigação legal, legítimo interesse — não é a mesma para o e-mail do usuário e para o CPF do proprietário |
| 3 | **Contrato de tratamento** | Precisa existir no primeiro projeto pago do Estágio 0, não depois |
| 4 | **Prazos de retenção** | Ver acima. Vale também para **backup**: backup guarda dado pessoal, então retenção de backup é retenção de dado ([`OPERACAO.md`](OPERACAO.md)) |
| 5 | **Quem é o encarregado** | Nome e canal de contato |
| 6 | **Política de privacidade** | Precisa de quem tenha competência para redigi-la |
| 7 | **Resposta a incidente** | O que fazer, quem avisa, em quanto tempo |

### Uma decisão de produto que já é decisão de privacidade

O roadmap prevê, para as fotos de obra do Estágio 2:

> remova GPS antes de servir ao cliente, se a política de privacidade da obra
> exigir; guarde no registro interno.

Isso vale **antes** do Estágio 2. A decisão precisa existir antes de a primeira
foto ser tirada, não quando o módulo for construído — foto com GPS já tirada não
volta atrás.

---

## Como responder a um pedido de titular, hoje

Enquanto o processo formal não existe, o caminho técnico é este:

```bash
# 1. Ver o que seria removido, sem remover
POST /api/v1/projects/{id}/anonymize
     {"reason": "...", "dry_run": true}

# 2. Depois de a avaliação jurídica concluir que o pedido procede
POST /api/v1/projects/{id}/anonymize
     {"reason": "Pedido recebido em ..., avaliado por ...", "dry_run": false}
```

Requer papel `owner` ou `admin`. A razão informada fica no registro do
empreendimento, indefinidamente.

**O que este caminho não cobre:** dado pessoal dentro do **conteúdo** de um PDF
de projeto, e nomes em texto livre no diário de obra. Remover ali exige
substituir o documento ou editar o diário — e o diário, uma vez fechado, não é
editável por desenho. É limitação conhecida, e entra na decisão nº 6.
