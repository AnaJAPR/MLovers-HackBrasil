# MLovers HackBrasil

Neste repositório encontra-se o trabalho do grupo MLovers ao participar do HackBrasil 2026. O grupo é composto por 4 estudantes do último ano da graduação em Ciência de Dados e Inteligência Artificial na FGV-EMAp.

## Integrantes do grupo:

- Ana Júlia Amaro Pereira Rocha
- Gustavo Tironi
- Kauan Mariani Ferreira
- Sillas Rocha da Costa

## O projeto

A Energia Inteligente é uma plataforma de inteligência energética que conecta dois desafios do setor elétrico brasileiro:

- **Curtailment:** energia solar e eólica que deixa de ser gerada por restrições operacionais do sistema elétrico.
- **Abertura do mercado livre:** oportunidade para que pequenos negócios escolham seus fornecedores de energia e negociem melhores condições comerciais.

Nossa proposta é utilizar ciência de dados, inteligência artificial e dados públicos para ajudar pequenos negócios a tomar decisões mais econômicas sobre energia, enquanto oferecemos inteligência preditiva para empresas do setor elétrico.

---

## Problema

O Brasil enfrenta um paradoxo energético: enquanto cresce a capacidade de geração solar e eólica, parte dessa energia potencial é desperdiçada devido a restrições na rede elétrica e a condições operacionais do sistema.

Ao mesmo tempo, pequenos negócios ainda possuem pouco acesso a ferramentas de inteligência energética para avaliar contratos, comparar fornecedores e identificar oportunidades de economia.

Com a abertura do mercado livre para consumidores comerciais e industriais de baixa tensão em novembro de 2027, surge uma oportunidade de democratizar o acesso a informações e ferramentas de decisão.

## Nossa solução

Uma plataforma composta por três módulos integrados:

### 1. Radar de Energia Renovável
- Monitoramento de curtailment solar e eólico.
- Análise histórica por usina, região e horário.
- Previsão de risco de restrição de geração.
- Análise conjunta com preços horários do mercado.
- Identificação de possíveis janelas de flexibilidade energética.

### 2. Copiloto Energético
- Upload e análise de contas de luz.
- Identificação de distribuidora e modalidade tarifária.
- Estimativa de custos atuais.
- Simulação de migração para o mercado livre.
- Comparação de propostas comerciais.
- Análise de riscos e condições contratuais.
- Recomendações personalizadas para pequenos negócios.

### 3. Matching Inteligente
- Cruzamento entre disponibilidade potencial de energia renovável e perfil de consumo.
- Identificação de consumidores com cargas flexíveis.
- Comparação de ofertas comerciais.
- Recomendação de oportunidades por região e período.
- Conexão com comercializadoras e parceiros habilitados.

**Importante:** a plataforma não presume que a energia cortada em uma usina possa ser fisicamente entregue a um consumidor específico. O matching considera oportunidades comerciais e flexibilidade de consumo, respeitando as restrições da rede e as regras do setor elétrico.

---

## Fontes de dados

O projeto utiliza prioritariamente dados públicos de instituições brasileiras.

| Fonte | Dados | Aplicação |
|---|---|---|
| ONS | Curtailment eólico e solar | Monitoramento e previsão |
| ONS | Carga, geração e intercâmbios | Análise de oferta e demanda |
| CCEE | PLD horário e mensal | Análise de preços |
| CCEE | Consumo por ambiente de contratação | Inteligência de mercado |
| ANEEL | Tarifas TE e TUSD | Simulador de custos |
| EPE | Consumo por classe e região | Dimensionamento de mercado |
| INMET | Dados meteorológicos | Previsão de geração |
| Copernicus ERA5 | Vento e radiação solar | Engenharia de atributos |

### Links das bases

- [ONS - Dados Abertos](https://dados.ons.org.br/)
- [ONS - Curtailment eólico](https://dados.ons.org.br/dataset/restricao_coff_eolica_detail)
- [ONS - Curtailment fotovoltaico](https://dados.ons.org.br/dataset/restricao_coff_fotovoltaica)
- [CCEE - Dados Abertos](https://dadosabertos.ccee.org.br/)
- [ANEEL - Dados Abertos](https://dadosabertos.aneel.gov.br/)
- [EPE - Consumo de Energia Elétrica](https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/consumo-de-energia-eletrica)
- [INMET - Dados Históricos](https://portal.inmet.gov.br/dadoshistoricos)
- [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/)

---

## Inteligência Artificial e Machine Learning

O projeto utiliza modelos de aprendizado de máquina para transformar dados energéticos em previsões e recomendações.

### Modelo 1: Previsão de Curtailment

Objetivo: estimar a probabilidade e a intensidade de restrições de geração solar e eólica.

Possíveis variáveis:
- Geração histórica.
- Carga do sistema.
- Capacidade instalada.
- Condições meteorológicas.
- Restrições operacionais.
- Histórico de curtailment.

Modelos candidatos:
- Regressão logística.
- Random Forest.
- XGBoost.
- Modelos de séries temporais.

### Modelo 2: Perfil de Consumo

Objetivo: identificar padrões de consumo e oportunidades de economia.

Técnicas:
- Clustering.
- Regressão.
- Previsão de séries temporais.
- Detecção de anomalias.

### Modelo 3: Matching e Recomendação

Objetivo: identificar as ofertas comerciais mais adequadas ao perfil de cada consumidor.

Critérios:
- Economia estimada.
- Compatibilidade com o consumo.
- Condições contratuais.
- Risco financeiro.
- Adequação da oferta de energia.

As recomendações deverão apresentar suas premissas e limitações de forma transparente.

---

## Tecnologias

| Tecnologia | Aplicação |
|---|---|
| Python | Ciência de dados e backend |
| Pandas / Polars | Processamento de dados |
| Scikit-learn | Machine Learning |
| XGBoost | Modelos preditivos |
| FastAPI | APIs |
| PostgreSQL | Banco de dados |
| Parquet | Armazenamento de séries temporais |
| Next.js | Interface web |
| Tailwind CSS | Estilização |
| Firecrawl | Extração de informações públicas |
| Resend | Alertas e relatórios por e-mail |
| Devin | Apoio ao desenvolvimento e testes |
| Docker | Containerização |

---

## Arquitetura

```text
                 FONTES DE DADOS
                       |
        +--------------+--------------+
        |              |              |
       ONS            CCEE          ANEEL
        |              |              |
        +--------------+--------------+
                       |
                PIPELINE DE DADOS
                       |
              ENGENHARIA DE DADOS
                       |
          +------------+------------+
          |            |            |
       CURTAILMENT   CONSUMO      PREÇOS
          |            |            |
          +------------+------------+
                       |
                MODELOS DE IA
                       |
          +------------+------------+
          |            |            |
       PREVISÃO    SIMULADOR    MATCHING
          |            |            |
          +------------+------------+
                       |
                 BACKEND API
                       |
                DASHBOARD WEB
                       |
          +------------+------------+
          |            |            |
        CLIENTES    PARCEIROS     ALERTAS
```

---

## MVP - HackBrasil

A primeira versão terá quatro funcionalidades:

1. Dashboard de curtailment com dados reais do ONS.
2. Análise de preços horários da CCEE.
3. Simulador de economia para pequenos negócios.
4. Recomendações demonstrativas de oportunidades comerciais.

O MVP utilizará dados públicos reais e ofertas comerciais simuladas, claramente identificadas como demonstração, até que existam parcerias para disponibilizar propostas comerciais efetivas.

### Fluxo de utilização

1. O usuário informa sua localização e envia a conta de luz.
2. A plataforma identifica seu perfil energético.
3. O sistema estima os custos atuais.
4. O usuário visualiza cenários de contratação.
5. A plataforma apresenta oportunidades e recomendações.
6. O usuário pode solicitar contato com um parceiro habilitado.

---

## Modelo de negócio

A monetização será baseada em três frentes:

- **SaaS para pequenos negócios:** assinatura para acesso ao copiloto energético.
- **SaaS B2B:** licenciamento do radar de curtailment e ferramentas de inteligência para empresas do setor.
- **Marketplace:** remuneração por encaminhamento ou conversão de clientes, mediante parcerias e enquadramento regulatório adequado.

---

## Impacto esperado

**Econômico**
- Redução de custos energéticos.
- Maior transparência na contratação.
- Democratização do acesso ao mercado livre.

**Ambiental**
- Incentivo à utilização eficiente da energia renovável.
- Identificação de oportunidades de flexibilidade.
- Maior integração entre geração e consumo.

**Tecnológico**
- Aplicação de Machine Learning ao setor elétrico.
- Democratização da inteligência energética.
- Desenvolvimento de ferramentas preditivas e explicáveis.

---

## Contexto regulatório

O Decreto nº 13.097/2026 estabelece:

- 25/11/2027: abertura para consumidores industriais e comerciais de baixa tensão.
- 25/11/2028: abertura para os demais consumidores de baixa tensão.

Fonte: [Decreto nº 13.097/2026 - Senado Federal](https://legis.senado.gov.br/norma/43675473/publicacao/43678847).

---

## Referências e benchmarking

Projetos e empresas estudados:

- [Nameplate](https://nameplate.com.br/projeto) - Previsão de curtailment e flexibilidade energética.
- [EnergiaWATT](https://energiawatt.com/) - Inteligência de mercado elétrico.
- [Energuia Online](https://energuia.online/) - Diretório de comercializadoras.
- [Clarke Energia](https://clarke.com.br/) - Gestão e contratação de energia.
- [Comerc Energia](https://www.comerc.com.br/) - Comercialização e gestão energética.
- [Piclo](https://www.piclo.com/) - Marketplace internacional de flexibilidade energética.
