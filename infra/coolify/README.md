# Deploy: Oracle Cloud Free Tier (Ampere ARM) + Coolify

Guia passo a passo para colocar o Echo em produção em **uma** VM Always Free da Oracle, gerenciada
pelo Coolify (Traefik + Let's Encrypt + deploy por Git). Ao final você terá, no projeto `echo` do
Coolify, quatro recursos:

| Recurso | Tipo no Coolify | Papel |
|---|---|---|
| `echo-postgres` | Database → PostgreSQL 16 | banco (backup diário para o Object Storage) |
| `echo-redis` | Database → Redis 7 | broker/result backend do Celery |
| `echo-web` | Application → Dockerfile (`infra/Dockerfile.backend`, stage `prod`) | gunicorn + WhiteNoise servindo API, admin e a SPA no **mesmo domínio** |
| `echo-worker` | Application → mesmo Dockerfile | Celery worker (`ffmpeg` incluso) que transcreve e avalia |

`web` e `worker` usam **a mesma imagem**. O build pack Dockerfile do Coolify não tem campo de
"start command", então o papel do container vem da variável `ECHO_PROCESS` (`web` | `worker` |
`beat`, default `web`), lida por `infra/entrypoint.sh`. O `HEALTHCHECK` da imagem
(`infra/healthcheck.sh`) também é ciente do papel: `web` chama `/healthz/`, `worker` faz
`celery inspect ping`.

Ordem recomendada: **1 → 2 → 3 (postgres e redis antes de web/worker) → 4 → 5 → 6 → 7 → 8**.

---

## 0. Pré-requisitos
- Conta Oracle Cloud. Recomendado converter para **Pay As You Go** (fica em US$ 0 dentro dos
  limites Always Free) — remove a regra de recuperação de instâncias ociosas (ver §1.6) e ajuda com
  "Out of capacity" ao criar a VM A1.
- Um domínio com DNS que você controle (ex.: `echo.example.com`; substitua em todo o guia).
- Repositório `github.com/hugommbrito/echo` (público) com a branch `main` verde no CI.
- Chaves `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`.
- Um par de chaves SSH local (`~/.ssh/id_ed25519.pub`).

---

## 1. VM na Oracle Cloud

### 1.1 Criar a instância
Console → **Compute → Instances → Create instance**:
- **Name**: `echo`.
- **Image**: Canonical Ubuntu 24.04 (a variante `aarch64` aparece ao escolher o shape ARM).
- **Shape**: Ampere → `VM.Standard.A1.Flex` → **4 OCPU / 24 GB** (máximo Always Free; menos também
  serve, mas o primeiro build da imagem é pesado).
- **Networking**: "Create new virtual cloud network" + "Create new public subnet";
  **Assign a public IPv4 address = Yes**.
- **Add SSH keys**: cole sua chave pública.
- **Boot volume**: marque "Specify a custom boot volume size" → **50 GB** (Always Free permite até
  200 GB somando volumes). Imagens Docker + builds ocupam espaço rápido.

Se aparecer **"Out of capacity"** para A1: tente outro Availability Domain, repita em horários
diferentes, ou converta para PAYG (contas PAYG têm prioridade). É o obstáculo mais comum do Free Tier.

Anote o **Public IP**. Opcional, mas evita surpresas: torne-o reservado (Instance → Attached VNICs →
VNIC → IPv4 Addresses → Edit → "Reserved public IP").

### 1.2 Abrir portas na VCN (firewall da Oracle)
**Networking → Virtual cloud networks → sua VCN → Subnets → subnet pública → Security List
(Default) → Add Ingress Rules**. A porta 22 já existe. Adicione:

| Source CIDR | Protocol | Dest. port | Uso |
|---|---|---|---|
| `0.0.0.0/0` | TCP | `80` | HTTP (redirect + desafio Let's Encrypt) |
| `0.0.0.0/0` | TCP | `443` | HTTPS |
| `<seu IP>/32` | TCP | `8000` | painel do Coolify (só até configurar um domínio para ele) |
| `<seu IP>/32` | TCP | `6001-6002` | realtime/terminal do painel quando acessado por IP |

### 1.3 Abrir portas no Ubuntu (iptables — a armadilha clássica)
As imagens Ubuntu da Oracle já vêm com `iptables` bloqueando tudo exceto 22, e regras da VCN **não
bastam**. Conecte por SSH (`ssh ubuntu@<IP>`) e rode:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 6001:6002 -j ACCEPT
sudo netfilter-persistent save
```

(Alternativa aceita pela comunidade: `sudo apt remove -y iptables-persistent netfilter-persistent`
e confiar só na Security List. Mantenha 22 aberto em ambos os lugares em qualquer caso.)

### 1.4 Atualizar o sistema e instalar o Coolify
```bash
sudo apt update && sudo apt -y upgrade && sudo reboot
# reconecte após o reboot
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
```
O script instala Docker e sobe o Coolify (Postgres, Redis, Soketi e Traefik como proxy). Ao final
ele imprime a URL `http://<IP>:8000`.

### 1.5 Primeiro acesso ao painel
1. Abra `http://<IP>:8000` **imediatamente** e crie a conta admin — quem chegar primeiro à tela de
   registro vira admin da instância.
2. Onboarding: escolha **"localhost"** (o Coolify gerencia a própria VM) e deixe criar o projeto
   padrão ou pule.
3. Guarde uma cópia de `/data/coolify/source/.env` da VM (contém `APP_KEY`; sem ele um restore do
   Coolify não decifra os segredos).
4. Opcional, recomendado: **Settings → Instance domain** = `https://coolify.echo.example.com`
   (crie antes o registro A apontando para o IP). Depois disso feche 8000/6001/6002 na Security
   List e no iptables — o painel passa a ser servido pelo Traefik com TLS.

### 1.6 Caveat: recuperação de instâncias ociosas
A Oracle pode **recuperar** instâncias Always Free com CPU/rede baixos por 7 dias. Contas PAYG
não estão sujeitas à regra (custo continua zero dentro dos limites). Se ficar no Free Tier puro,
saiba que a VM pode sumir; os backups do §8 são a rede de segurança.

---

## 2. Coolify: projeto, fonte Git e rede

### 2.1 Projeto
**Projects → + Add** → nome `echo`. Um projeto nasce com o ambiente `production`; é nele que os
quatro recursos vão viver.

### 2.2 Fonte GitHub (GitHub App)
O repositório é público, então "Public Repository" funcionaria, mas o **GitHub App** habilita o
**Auto Deploy** por webhook sem configuração manual e vale para repositórios privados depois.

**Sources → + Add → GitHub App**: dê um nome (`coolify-echo`), clique em "Register Now", confirme
no GitHub, e na tela de instalação escolha **Only select repositories → `hugommbrito/echo`**.
De volta ao Coolify, o source deve aparecer como conectado.

### 2.3 Rede (Destination)
Todos os recursos devem ficar no mesmo servidor (`localhost`) e na mesma **Destination** (a rede
Docker `coolify`, criada na instalação). É isso que permite `web`/`worker` alcançarem o banco e o
Redis **pelo nome do container**. Não há nada a fazer além de não mudar a Destination ao criar cada
recurso.

---

## 3. Serviços (recursos) no projeto `echo`

Tudo abaixo acontece em **Projects → echo → production → + New**.

### 3.1 `echo-postgres`
1. **Databases → PostgreSQL**. Servidor `localhost`, destination padrão.
2. Na tela de configuração, **antes do primeiro deploy**:
   - **Name**: `echo-postgres`
   - **Image**: `postgres:16-alpine` (mesma major do dev/CI; o Coolify pode sugerir 17/18)
   - **Username**: `echo` · **Password**: gerada (copie) · **Initial Database**: `echo`
   - **Make it publicly available**: **desligado**.
3. **Deploy**. O Coolify cria o volume persistente em `/var/lib/postgresql/data` sozinho.
4. Copie a **"Postgres URL (internal)"**. Ela tem a forma
   `postgres://echo:<senha>@<nome-do-container>:5432/echo` — **o host é o nome do container**
   (algo como `echo-postgres-abc123`), não `postgres`. Esse valor inteiro vira `DATABASE_URL`.
   Se a senha tiver caracteres especiais, ela precisa estar URL-encoded na URL (as geradas pelo
   Coolify normalmente são alfanuméricas).

### 3.2 `echo-redis`
1. **Databases → Redis**. **Name**: `echo-redis`; **Image**: `redis:7-alpine` (o default `redis:7.2`
   também serve). O Coolify **gera uma senha** automaticamente; não é opcional.
2. **Deploy**. Persistência não importa para o Echo (filas são transitórias); deixe o default.
3. Copie a **"Redis URL (internal)"**: `redis://:<senha>@<nome-do-container>:6379/0`
   (note os dois-pontos antes da senha). Esse valor vira `REDIS_URL`.

### 3.3 `echo-web`
1. **Applications → Private Repository (with GitHub App)** → escolha o source do §2.2 →
   repositório `hugommbrito/echo` → branch `main` → **Build Pack: Dockerfile**.
2. **Configuration → General**:

   | Campo | Valor |
   |---|---|
   | Name | `echo-web` |
   | Build Pack | `Dockerfile` |
   | Base directory | `/` |
   | Dockerfile location | `/infra/Dockerfile.backend` |
   | Docker build stage target | `prod` |
   | Ports exposes | `8000` |
   | Domains | `https://echo.example.com` (apague o domínio `sslip.io` gerado) |
   | Custom Docker options | vazio |

   O `https://` no domínio faz o Traefik emitir o certificado Let's Encrypt sozinho — o registro
   **A** `echo.example.com → <IP da VM>` precisa existir **antes** do deploy (§6).
3. **Configuration → Environment Variables**: use **Developer view** e cole o bloco do §4 (sem
   `ECHO_PROCESS`, ou com `ECHO_PROCESS=web`). Nenhuma delas precisa ser "Build Variable".
4. **Configuration → Healthcheck**: nada a fazer. O Coolify detecta o `HEALTHCHECK` da imagem e o
   usa no lugar do configurado no painel. Ele chama `/healthz/` (que também testa a conexão com o
   banco) enviando como `Host` o primeiro valor de `ALLOWED_HOSTS`, então não é preciso listar
   `localhost`.
5. **Configuration → Advanced**: **Auto deploy** ligado (push em `main` → redeploy). Opcional, em
   **General → Watch paths**: `backend/**`, `frontend/**`, `infra/**` (um por linha) para não
   rebuildar por mudança em `docs/`.
6. **Deploy** e acompanhe em **Deployments**. Primeiro build na A1: ~5–10 min (`npm ci` + Vite +
   `uv sync` + `collectstatic`). Ao subir, o entrypoint roda `migrate` e inicia o gunicorn;
   o recurso fica verde quando `/healthz/` responde 200.

### 3.4 `echo-worker`
Repita o §3.3 com três diferenças:
- **Name**: `echo-worker`.
- **Domains**: **vazio** (remova o domínio gerado; o worker não recebe HTTP). `Ports exposes` pode
  ficar `8000` — sem domínio o Traefik não roteia nada.
- **Environment Variables**: o mesmo bloco do §4 **mais `ECHO_PROCESS=worker`**.

O `HEALTHCHECK` no worker executa `celery inspect ping` contra o próprio nó a cada 30 s (período de
graça de 60 s). Se ficar "unhealthy", quase sempre é `REDIS_URL` (senha/host errados) — veja os logs.

Para não duplicar segredos entre `web` e `worker`, opcionalmente defina-os em
**Shared Variables → Project `echo`** e referencie nas aplicações como `{{project.SECRET_KEY}}`,
`{{project.DATABASE_URL}}` etc.

Ordem no primeiro deploy: **web antes do worker**, porque é o `web` que aplica as migrações.

### 3.5 `beat` (não usado)
O entrypoint aceita `ECHO_PROCESS=beat`, mas o MVP não tem tarefas periódicas. Só crie um terceiro
recurso quando existir um `beat_schedule`.

---

## 4. Variáveis de ambiente (`echo-web` e `echo-worker`)

Gere a `SECRET_KEY` localmente: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

```
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<64 chars aleatórios>
ALLOWED_HOSTS=echo.example.com                      # vários hosts: separados por vírgula
CSRF_TRUSTED_ORIGINS=https://echo.example.com
DATABASE_URL=postgres://echo:<senha>@<container-postgres>:5432/echo   # "Postgres URL (internal)"
REDIS_URL=redis://:<senha>@<container-redis>:6379/0                  # "Redis URL (internal)"
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ECHO_AUDIO_STORAGE=s3
S3_BUCKET_NAME=echo-audio
S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
S3_REGION=<region>                                   # ex.: sa-saopaulo-1
S3_ACCESS_KEY_ID=<Customer Secret Key: access key>
S3_SECRET_ACCESS_KEY=<Customer Secret Key: secret>
S3_SIGNED_URL_SECONDS=900
WEB_CONCURRENCY=2
CELERY_CONCURRENCY=2
LOG_LEVEL=INFO
# só no worker:
ECHO_PROCESS=worker
```

Opcionais: `ECHO_TRANSCRIPTION_MODEL=gpt-4o-transcribe` (teste A/B), `ECHO_EVALUATION_MODEL`,
`ECHO_GENERATION_MODEL`, `WEB_THREADS` (default 4), `SECURE_SSL_REDIRECT=1` (desnecessário: o
Traefik já redireciona). Todos os parâmetros `ECHO_*` estão em `backend/config/settings/base.py`.

---

## 5. Oracle Object Storage (API compatível com S3)

### 5.1 Bucket
**Storage → Buckets → Create Bucket**: compartimento da sua escolha (anote qual), **Name**
`echo-audio`, Default Storage Tier **Standard**, visibilidade **Private** (default). Não habilite
versionamento nem eventos.

### 5.2 Namespace e região
- **Namespace**: Profile → **Tenancy** → "Object storage namespace" (também aparece nos detalhes
  do bucket).
- **Region**: identificador da região da VM, ex. `sa-saopaulo-1` (lista no seletor de região do
  console).
- Endpoint resultante: `https://<namespace>.compat.objectstorage.<region>.oraclecloud.com`.
  A forma nova `https://<namespace>.compat.objectstorage.<region>.oci.customer-oci.com` também
  funciona. O `settings.py` já usa **path-style** e **SigV4** (a Oracle não aceita SigV2).

### 5.3 Credenciais (Customer Secret Key)
Profile (ícone no topo direito) → **User settings → Customer secret keys → Create Customer Secret
Key**. Dê um nome (`echo-s3`) e **copie o secret na hora** — ele não é exibido de novo. O
"Access Key" fica listado e pode ser copiado depois. Isso vira `S3_ACCESS_KEY_ID` /
`S3_SECRET_ACCESS_KEY`.

### 5.4 Compartimento designado (gotcha)
A API S3 enxerga buckets de **um** compartimento: **Tenancy → Edit Object Storage Settings →
"Amazon S3 Compatibility API designated compartment"**. Se o bucket não estiver no root, aponte
esse campo para o compartimento do bucket; caso contrário você verá `NoSuchBucket` mesmo com o
bucket existindo.

### 5.5 Teste rápido (depois do deploy do `echo-web`)
No Coolify → `echo-web` → **Terminal**:
```bash
python manage.py shell -c "
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
n = default_storage.save('smoke/test.txt', ContentFile(b'ok'))
print(default_storage.url(n)); default_storage.delete(n)"
```
Deve imprimir uma URL assinada (`?X-Amz-Signature=...`) sem erro. Áudios ficam em
`users/<user_id>/attempts/<attempt_id>.<ext>` e só são servidos por URL assinada de 15 min.

---

## 6. Domínio e TLS
1. No seu DNS: registro **A** `echo` → `<IP público da VM>` (TTL baixo enquanto configura).
   Verifique com `dig +short echo.example.com`.
2. Em `echo-web` o domínio está como `https://echo.example.com` (§3.3). No deploy o Traefik pede
   o certificado via desafio HTTP — a porta **80** precisa estar aberta na VCN **e** no iptables.
3. Com o domínio em `https://`, o Coolify gera a rota TLS e o redirecionamento http→https no
   Traefik; por isso `SECURE_SSL_REDIRECT` fica desligado no Django. Se na sua versão do Coolify o
   `http://` não redirecionar, defina `SECURE_SSL_REDIRECT=1` — `SECURE_PROXY_SSL_HEADER` já confia
   no `X-Forwarded-Proto` do proxy, então não há loop.
4. Se o certificado não vier em ~2 min: veja **Servers → localhost → Proxy → Logs**; causas usuais
   são DNS ainda não propagado ou 80 fechada.

---

## 7. Primeira execução
No Coolify → `echo-web` → **Terminal**:
```bash
python manage.py createsuperuser
```
Depois, em `https://echo.example.com/admin/`:
1. Crie a aprendiz (usuário comum). Ajuste `level_rating` se for diferente do inicial (1150).
   Categorias globais já foram criadas pela migração.
2. Smoke test pelo app: login → gravar uma resposta → transcrição e avaliação aparecem
   (isso prova web → Redis → worker → OpenAI/Anthropic → S3).
3. `/admin/ai/airequestlog/` lista cada chamada a provedores com custo estimado em USD; o total do
   filtro atual aparece no topo.

---

## 8. Backups

### 8.1 Postgres → Object Storage (diário)
1. Crie um segundo bucket privado `echo-backups` (§5.1) — mesma credencial do §5.3.
2. Coolify → **S3 Storage** (menu lateral) → **+ Add**: Name `oracle-backups`, Endpoint (o mesmo
   do §5.2), Bucket `echo-backups`, Region `<region>`, Access Key / Secret Key → **Validate**.
3. `echo-postgres` → **Backups → + Add**: Frequency `0 3 * * *` (03:00 UTC), Backup All Databases
   ligado, Retention por exemplo 14 backups / 30 dias, seção **S3** ligada apontando para
   `oracle-backups`, opcionalmente "Disable local backup" para não ocupar disco na VM.
4. Clique **Backup Now** e confirme status *Success*, tamanho > 0 e o arquivo no bucket.
   Restore: mesma tela, a partir do arquivo local ou do S3.

### 8.2 Boot volume (semanal)
OCI → **Block Storage → Boot Volumes → volume da VM → Assign Backup Policy → Silver** (semanal +
mensal). O Always Free inclui 5 backups de volume no total; a política Silver respeita isso.

---

## 9. Operação
- **Atualizar**: `git push` em `main` → CI → webhook → o Coolify rebuilda `echo-web` e
  `echo-worker` (dois builds da mesma imagem; ~3–5 min com cache). O job `image` do CI só valida o
  build multi-arch, não publica imagem.
- **Rollback**: `echo-web` → Deployments → deploy anterior → **Redeploy**.
- **Logs**: aba **Logs** de cada aplicação; `LOG_LEVEL=DEBUG` + Redeploy para investigar.
- **Recursos**: com 24 GB há folga; se precisar, suba `WEB_CONCURRENCY`/`CELERY_CONCURRENCY`
  (cada worker Celery segura um `ffmpeg` + upload em memória).
- **Coolify**: mantenha atualizado em Settings → Update; segredos ficam em `/data/coolify`.

---

## 10. Problemas comuns

| Sintoma | Causa provável | Correção |
|---|---|---|
| `echo-web` unhealthy, log mostra `Invalid HTTP_HOST header` | `ALLOWED_HOSTS` não contém o domínio, ou contém com `https://` | só o host, sem esquema (§4); Redeploy |
| 502/"no available server" no domínio | container não saudável ou `Ports exposes` ≠ 8000 | veja Logs; confira §3.3 |
| 403 CSRF ao logar | `CSRF_TRUSTED_ORIGINS` sem `https://` ou domínio diferente | corrija a variável e Redeploy |
| Worker: `Cannot connect to redis://...` | `REDIS_URL` sem a senha (`redis://:<senha>@...`) ou host errado | copie a URL interna de novo |
| `NoSuchBucket` / `SignatureDoesNotMatch` no S3 | compartimento designado (§5.4), região errada no endpoint, secret colado errado | revise §5 |
| 80/443 dão timeout mas 22 funciona | iptables do Ubuntu | §1.3 |
| Let's Encrypt falha | DNS não propagado / 80 fechada | §6 |
| "Out of capacity" ao criar a VM | falta de A1 no AD | outro AD, repetir, PAYG |
| Instância sumiu | recuperação de ociosa (§1.6) | recriar VM + restaurar backup (§8) |
