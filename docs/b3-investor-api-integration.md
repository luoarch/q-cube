# B3 Investor API — Guia de Integração e Licenciamento

Este documento detalha os passos necessários para obter acesso à API da Área do Investidor da B3, incluindo requisitos de licenciamento, configuração técnica (mTLS + ROPC) e endpoints disponíveis.

## 1. Pré-requisitos

| Requisito | Detalhes |
|-----------|----------|
| **CNPJ ativo** | Empresa ou fintech registrada no Brasil |
| **Contato comercial B3** | contratação@b3.com.br / (11) 2565-5080 |
| **Contrato de licenciamento** | Assinado com a B3 |
| **Infraestrutura mTLS** | Capacidade de configurar TLS mútuo com certificados client-side |

## 2. Fluxo de Onboarding

### 2.1 — Solicitar contrato de licenciamento

1. Entrar em contato com a B3 via contratação@b3.com.br
2. Informar: razão social, CNPJ, natureza do serviço (fintech, corretora, plataforma de investimento)
3. Definir modelo de tarifação (cobrança por investidor autorizado/mês)
4. Assinar contrato

### 2.2 — Obter acesso ao ambiente de certificação (gratuito)

Após contratação, gerar o pacote de acesso via API:

```http
POST https://apib3i-cert.b3.com.br/api/acesso/autosservico
Content-Type: application/json

{
  "razao_social": "Sua Empresa Ltda",
  "cnpj": "12.345.678/0001-90",
  "email": "dev@suaempresa.com.br"
}
```

Resultado: certificado `.p12` enviado por e-mail com senha.

### 2.3 — Configurar certificado mTLS

#### Opção A: Converter para JKS (Java)

```bash
keytool -importkeystore \
  -srckeystore [CNPJ].p12 \
  -srcstoretype pkcs12 \
  -srcstorepass [SENHA] \
  -destkeystore b3_api.jks \
  -deststoretype jks \
  -deststorepass [NOVA_SENHA]
```

#### Opção B: Usar diretamente com Python/httpx

```python
import httpx
import ssl

ssl_context = ssl.create_default_context()
ssl_context.load_cert_chain(
    certfile="client_cert.pem",
    keyfile="client_key.pem",
    password="senha_do_certificado",
)

client = httpx.Client(verify=ssl_context)
```

Para extrair PEM do .p12:
```bash
# Extrair certificado
openssl pkcs12 -in [CNPJ].p12 -clcerts -nokeys -out client_cert.pem

# Extrair chave privada
openssl pkcs12 -in [CNPJ].p12 -nocerts -out client_key.pem
```

### 2.4 — Obter Bearer token

Autenticação via ROPC (Resource Owner Password Credentials):

```http
POST https://apib3i-cert.b3.com.br/TOKEN
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=[CLIENT_ID]&client_secret=[SECRET]
```

Header adicional obrigatório: `category_ID`

Resposta:
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### 2.5 — Testar healthcheck

```http
GET https://apib3i-cert.b3.com.br:2443/api/healthcheck/{access_token}
```

## 3. Ambientes

| Ambiente | URL | Porta | Acesso |
|----------|-----|-------|--------|
| **Certificação** | `https://apib3i-cert.b3.com.br` | 2443 | Após gerar pacote de acesso |
| **Produção** | Fornecido pela B3 | TBD | Após contratação formal |

## 4. Endpoints Disponíveis (12 APIs)

| API | Versão | Dados | Frequência |
|-----|--------|-------|------------|
| **Posição** | 3.3.1-rc2 | Saldos D-1 de investimentos nas contas do investidor | D-1 |
| **Movimentação** | 2.0.2-rc8 | Transações D-1 ocorridas em período especificado | D-1 |
| **Negociação de Ativos** | 2.0.1-rc3 | Compras/vendas D-1 de ativos listados | D-1 |
| **Eventos Provisionados** | 2.0.0-rc1 | Eventos corporativos de renda variável por investidor | D-1 |
| **Oferta Pública** | 2.0.0-rc1 | Participação do investidor em ofertas públicas | D-1 |
| **API Guia** | 1.0.0-rc3 | Docs de investidores autorizados pela fintech por produto/data | On-demand |
| **Autorização Fintech** | 1.0.0-rc7 | Verificar se investidor autorizou compartilhamento | On-demand |
| **Cadastro Investidor** | 1.0.0-rc1 | Dados cadastrais do investidor | On-demand |
| **Pacote de Acesso** | 1.0 | Gerar credenciais para ambiente de certificação | On-demand |
| **FintechSistema** | 1.0.0-rc1 | Timestamps de quando os dados foram carregados | On-demand |
| **STVM Request Auth** | 1.0.0-rc1 | Solicitar token de autorização via custodiante | On-demand |
| **STVM Response Auth** | 1.0.0-rc1 | Obter token solicitado via custodiante | On-demand |

## 5. Modelo de Consentimento

O investidor deve autorizar explicitamente o compartilhamento de dados com a fintech licenciada:

1. Investidor acessa a [Área do Investidor](https://www.investidor.b3.com.br/)
2. Navega até seção de autorizações
3. Autoriza a fintech a acessar seus dados
4. Fintech verifica consentimento via API `Autorização Fintech`

### Revogação
- Investidor pode revogar a qualquer momento
- Sem cobrança a partir do mês seguinte à revogação
- Fintech não receberá mais dados após revogação

## 6. Tarifação

- **Modelo opt-out**: cobrança por investidor autorizado por mês
- Detalhes específicos de valores no contrato de licenciamento
- Ambiente de certificação: gratuito para testes

## 7. Suporte Técnico B3

| Canal | Contato |
|-------|---------|
| **Telefone** | (11) 2565-5120 |
| **E-mail** | suporte@b3.com.br |
| **Portal** | https://developers.b3.com.br |

## 8. Referências

- [Manual Técnico APIs — Área do Investidor (12/2024)](https://www.b3.com.br/lumis/portal/file/fileDownload.jsp?fileId=8AE490CA9358B1A70193BADF061C63AF)
- [Manual Técnico — Área Logada (versão anterior)](https://www.b3.com.br/data/files/60/72/19/05/45CDF7104532BBF7AC094EA8/Manual%20Tecnico%20-%20APIs%20vf.pdf)
- [Material Webinar — APIs Nova Área Logada](https://www.b3.com.br/data/files/99/00/1E/5D/6C39F71026F0F8F7AC094EA8/Material%20Webinar.pdf)
- [POC de Referência (GitHub)](https://github.com/felipewind/poc-b3-investor-api)
- [Portal de APIs B3](https://developers.b3.com.br/apis/api-area-do-investidor)
- [Integrações da Área do Investidor](https://www.b3.com.br/pt_br/produtos-e-servicos/central-depositaria/canal-com-investidores/integracoes-da-area-do-investidor-apis/)
