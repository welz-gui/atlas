# Operação — backup, segredos e deploy

Cobre o item **D9** da Fase D e os itens de operação do §12 do plano. Documento
curto de propósito: o que não estiver aqui deve estar no código.

> **O que este documento não faz:** escolher onde o Atlas roda. Provedor,
> domínio e custo são decisão de negócio. O que está aqui torna a escolha uma
> questão de hospedagem, não de arquitetura — a imagem e a composição rodam em
> VPS, e são o mapa para traduzir a plataformas gerenciadas.

---

## Backup

Duas metades, e as duas precisam existir:

| O quê | Por quê |
|---|---|
| **Banco** | O registro: quem analisou o quê, sob qual versão do catálogo, com qual hash |
| **Storage** (§6.6) | Os bytes dos documentos |

Um sem o outro deixa registro apontando para arquivo que não existe, ou arquivo
que ninguém sabe de qual projeto é.

```bash
python ops/backup.py --output /var/backups/atlas
```

Produz um diretório com carimbo de tempo contendo `database.dump`,
`storage.tar.gz` e um `manifest.json` com o SHA-256 de cada peça.

### Agendamento

O script não se agenda. No destino escolhido, ligue-o ao agendador de lá — cron,
`systemd` timer, ou o agendador do provedor:

```
0 3 * * *  cd /app && python ops/backup.py --output /var/backups/atlas
```

### Retenção

Decisão pendente, ligada à [issue de LGPD](https://github.com/welz-gui/atlas/issues/33):
backup guarda dado pessoal, e prazo de retenção de backup é prazo de retenção de
dado. Enquanto não for definido, mantenha o mínimo que o negócio tolera perder.

---

## Restauração

**Backup não restaurado é hipótese, não cópia.**

```bash
# Confere os hashes sem tocar em nada
python ops/restore.py /var/backups/atlas/atlas-20260812T030000Z --verify-only

# Restaura
python ops/restore.py /var/backups/atlas/atlas-20260812T030000Z
```

A conferência acontece **antes** de o destino ser tocado. Restaurar arquivo
corrompido por cima de banco vazio é pior que não restaurar: o sistema sobe,
parece íntegro, e a perda só aparece quando alguém procura o registro que sumiu.

### O ciclo é exercitado a cada push

O job `backup` da CI povoa um banco, tira o backup, **destrói o banco**,
restaura e compara a contagem de cada tabela. Se divergir, a CI fica vermelha.

É a diferença entre ter backup e achar que tem — e é automática, porque a forma
como backups deixam de funcionar é justamente ninguém lembrar de testá-los.

---

## Segredos

Por padrão, todos chegam por variável de ambiente, injetadas pela plataforma:

| Variável | Observação |
|---|---|
| `SECRET_KEY` | Sem ela, a aplicação **recusa subir** em produção |
| `SECRET_KEY_PREVIOUS` | Só durante uma rotação — ver abaixo |
| `DATABASE_URL` | Carrega usuário e senha do Postgres |
| `S3_*` | Quando `STORAGE_BACKEND=s3` |
| `ANTHROPIC_API_KEY` | Quando `AI_PROVIDER=anthropic` |

Gerar uma chave:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### De onde vêm os segredos (`SECRETS_BACKEND`)

`env` é o padrão. `SECRETS_BACKEND=file` lê de `SECRETS_DIR/<nome em
minúsculas>` — por exemplo, `SECRETS_DIR/secret_key` — a convenção de arquivo
montado que Docker Swarm, Kubernetes e todo cofre externo (Vault, AWS Secrets
Manager, Doppler, Infisical) usam para entregar segredo a um contêiner sem que
ele passe pela lista de processos. Variável de ambiente definida tem
precedência: dá para apontar `file` e ainda assim substituir um segredo
pontualmente em depuração, sem editar o arquivo montado.

Isto **não é um cofre** — `core/secrets.py` só lê o arquivo que outro sistema
colocou lá. Rotação automática, auditoria de acesso e a escolha de qual cofre
usar continuam dependendo do provedor (ver adiante).

### Rotação

Antes, trocar `SECRET_KEY` invalidava todas as sessões **e destruía todos os
segredos de MFA** — o TOTP é cifrado com uma chave derivada dela
(`core/mfa.py`) — obrigando cada pessoa com segundo fator a recadastrá-lo. A
rotação era tecnicamente possível e praticamente proibitiva, então na prática
não acontecia.

Agora a rotação tem uma janela, aberta por `SECRET_KEY_PREVIOUS`:

```
1. SECRET_KEY_PREVIOUS = valor atual de SECRET_KEY
2. SECRET_KEY          = a chave nova
3. reiniciar a aplicação
```

Durante a janela:

- **tokens continuam válidos** — `decode_access_token` aceita a chave atual e a
  anterior (`core/security.py`). Sessão em curso não cai;
- **segredo de MFA continua abrindo** — `MultiFernet` decifra com qualquer uma
  das duas (`core/mfa.py`);
- **cada login com MFA migra o segredo para a chave atual sozinho** — a
  verificação bem-sucedida recifra e grava, então a janela se fecha por uso,
  sem *job* de migração em lote (`consume_second_factor`, em
  `api/v1/endpoints/auth.py`).

Quando não houver mais sessão nem segredo dependendo da chave velha, **remova
`SECRET_KEY_PREVIOUS`**. A partir daí, token ou segredo ainda cifrado com ela
deixa de abrir — é o fim pretendido da janela, não uma falha.

O que a rotação continua causando: quem não usa o app durante a janela
inteira recadastra o MFA depois que `SECRET_KEY_PREVIOUS` sai. Avise antes de
uma rotação planejada, e mantenha a janela aberta por tempo suficiente para o
time em campo logar ao menos uma vez.

### O que o código garante

- **`repr(settings)` e `str(settings)` redigem os segredos**, incluindo
  `SECRET_KEY_PREVIOUS`. O padrão do Pydantic imprimiria tudo, e bastaria um
  traceback contendo as configurações para a chave ir ao log. Coberto por
  `tests/test_config_secrets.py`;
- **`.dockerignore` mantém `.env` fora do contexto de build** — segredo não
  entra em camada de imagem;
- **produção com SQLite recusa subir**, porque sem Postgres não há concorrência,
  nem RLS (D1), nem o caminho de backup deste documento.

### ⚠️ A conexão da aplicação não pode ser superusuária

A RLS (item **D1**) só defende se o papel do banco **não** for superusuário e
**não** tiver `BYPASSRLS`. Postgres ignora a política para esses papéis mesmo
com `FORCE ROW LEVEL SECURITY` — foi por isso que a política existiu desde a
Fase B sem nunca ter defendido nada.

Em produção, separe os dois papéis:

```sql
-- dono do esquema: roda migrations e o seed
CREATE ROLE atlas_owner LOGIN PASSWORD '...';

-- aplicação: sujeita à política
CREATE ROLE atlas_app LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA public TO atlas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO atlas_app;
```

`DATABASE_URL` da API e do worker aponta para `atlas_app`. Migrations e
`seed.py` rodam com `atlas_owner`.

Para conferir que o papel em uso não escapa da política:

```sql
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
```

Os dois precisam vir `false`.

### O que ainda depende do provedor

O cofre em si — Vault, AWS Secrets Manager, Doppler ou Infisical —, com
rotação automática e auditoria de acesso ao segredo. `SECRETS_BACKEND=file`
deixa a aplicação compatível com qualquer um deles; a escolha de qual usar
acompanha a escolha do host.

---

## Deploy

```bash
docker compose -f docker-compose.prod.yml up -d
```

Três decisões ficam explícitas na composição:

1. **`migrate` é serviço próprio.** Roda `alembic upgrade head` e termina; a API
   só sobe depois que ele completa. O esquema nunca é criado por `create_all`;
2. **`worker` roda de verdade.** Sem ele o backend cai para o modo `inline`, que
   é legítimo — mas passa a ser decisão consciente, e o registro do trabalho
   declara isso (`executed_inline`);
3. **nenhum segredo está no arquivo.** `${SECRET_KEY:?}` faz o compose recusar
   subir se a variável faltar, em vez de usar um padrão inseguro.

### Ordem de um deploy

```
1. backup            ops/backup.py
2. subir imagem      docker compose build
3. migrar            o serviço `migrate` roda sozinho
4. subir api+worker  docker compose up -d
5. conferir          GET /health  e  GET /api/v1/metrics
```

O passo 1 não é cerimônia: migração que falha no meio deixa o esquema em estado
intermediário, e o backup é o caminho de volta.

---

## Descoberta de normas

Usuários com permissão de validação podem iniciar a busca em **Catálogo →
Buscar normas oficiais** ou chamar:

```http
POST /api/v1/catalog/jobs/discovery?jurisdiction=BR-RS-4311403
```

A operação consulta os índices oficiais configurados em
`app/regulatory/discovery.py`, registra o trabalho e cria documentos no estado
`descoberto`. Ela não extrai artigos, não cria regras executáveis e não publica
conteúdo. Um validador técnico ainda precisa conferir a versão consolidada, a
vigência e os artigos antes de qualquer regra alimentar um laudo de cliente.

Para execução periódica, o agendador da infraestrutura deve chamar esse endpoint
com uma credencial de serviço que possua `catalog:validate`; frequência sugerida:
diária. Falhas e resultados ficam em `job_records`.

### Conformidade com `robots.txt`

Antes de buscar qualquer índice, o coletor lê o `robots.txt` da origem
(`app/regulatory/robots.py`) e respeita o grupo do agente
`Atlas-Regulatory-Discovery/1.0`. Três comportamentos que valem conhecer:

- **arquivo ausente libera; falha de servidor suspende.** 4xx significa "não há
  arquivo de regras"; 5xx e 429 significam "não deu para perguntar", e aí a
  fonte não é buscada. Ausência de verificação não é aprovação (I10);
- **200 com HTML não é `robots.txt`.** O portal de Lajeado devolve o shell da
  própria página nesse caminho. Sem exigir `text/plain`, um parser leria HTML
  como diretiva e liberaria tudo por acidente;
- **intervalo mínimo de 2 s entre buscas ao mesmo host**, com `Crawl-delay`
  prevalecendo quando for maior.

Fonte recusada **não** interrompe a execução: aparece em `sources_skipped` no
resultado do trabalho, com o motivo, para que a recusa fique no registro em vez
de sumir em log.

### Allowlist de um município novo

Cada fonte em `SOURCES` carrega a própria `allowed_hosts`, e ela faz duas
coisas: decide de onde um candidato pode vir e valida o host final depois de
redirecionamento. Lista curta demais perde normas; longa demais aceita link de
qualquer lugar.

**Não existe regra sobre `www`.** Em Lajeado o portal usa `www.` e o host sem
`www` tem certificado autoassinado; no `leismunicipais.com.br`, que serve
dezenas de municípios, os índices referenciam a versão **sem** `www`. Os dois
casos coexistem no mesmo município. Padronizar por aparência erraria um deles.

O procedimento, para cada município novo:

1. **conte os hosts do índice real**, em vez de supor —

   ```python
   from app.regulatory.discovery import fetch_source, _LinkParser
   html = fetch_source("<url do índice>")
   p = _LinkParser(); p.feed(html)
   # agrupe urlparse(urljoin(indice, href)).hostname e veja quem aparece
   ```

2. **inclua o que os links de tema regulatório usam**, exatamente na forma em
   que aparecem — com ou sem `www`, conforme o site;
3. **confira o TLS de cada host** antes de incluir. Certificado inválido é
   motivo de exclusão: se a busca cair ali, a correção tentadora é desligar a
   verificação, que é pior que a lacuna;
4. **exclua o que é navegação e não norma** — redes sociais, portal da
   transparência, sistemas administrativos;
5. **meça o antes e o depois**: a contagem de candidatos não pode cair sem que
   você saiba qual link deixou de entrar.

---

## Observabilidade

### Sondas

| Rota | Pergunta | Quem consulta |
|---|---|---|
| `GET /api/v1/health` | *o processo está vivo?* | orquestrador, para decidir reinício |
| `GET /api/v1/health/ready` | *dá para atender?* | balanceador, para decidir rotação |

A sonda de vida **não toca em dependência nenhuma**, de propósito: uma que
consultasse o banco derrubaria a aplicação inteira quando o banco oscilasse.

A de prontidão verifica banco, storage, fila e antivírus, e devolve **503** se
alguma essencial estiver fora. **Componente que não pôde ser verificado responde
`nao_verificado`, nunca `ok`** — antivírus desligado por configuração não é
antivírus funcionando (I10).

```bash
curl -s localhost:8000/api/v1/health/ready | jq .status
# "pronto" ou "indisponivel"
```

### Log

Uma linha, um objeto JSON, em `stdout` — que é onde qualquer coletor de
contêiner procura. Nível em `LOG_LEVEL` (padrão `INFO`).

```json
{"ts":"...","level":"info","logger":"atlas.api","request_id":"demo-123",
 "message":"Requisição atendida","method":"GET","path":"/api/v1/health",
 "status":200,"duration_ms":4.8,"organization_id":null}
```

**`X-Request-Id` volta em toda resposta.** Se o cliente mandar o cabeçalho, ele
é preservado — uma chamada que atravessa serviços mantém o mesmo fio. Peça o
identificador a quem relatar um erro: é a chave que acha a linha.

### O que o log não carrega

Nem segredo nem dado pessoal. Campos cujo nome contenha `password`, `senha`,
`secret`, `token`, `authorization`, `mfa`, `recovery`, `prompt`, `cpf` ou
`document` saem como `***`, inclusive aninhados — e **corpo de requisição e
query string nunca são registrados**.

Não é zelo: `docs/LGPD.md` registra que a pergunta feita ao assistente pode
conter dado pessoal, e log é o lugar onde dado vaza sem ninguém notar.

### O que ainda não existe

Métricas em série temporal, rastreamento distribuído e alerta. Todos dependem
do provedor escolhido — o log estruturado é o que alimenta os três quando
houver um.

---

## O que falta, e é decisão humana

| Item | Bloqueado por |
|---|---|
| **Escolher o provedor** | Decisão de negócio — custo, jurisdição do dado, quem administra |
| **Observabilidade** | Vale na liberação externa do Estágio 1, não agora |
| **Retenção de backup** | Depende da [#33 (LGPD)](https://github.com/welz-gui/atlas/issues/33) |
| **Cofre de segredos** | Acompanha a escolha do provedor |
