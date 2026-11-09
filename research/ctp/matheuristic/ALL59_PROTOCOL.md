# Coleta exploratoria ALNS M + Micro-MIP: todos os 59 casos

Protocolo definido em 05/11/2026 antes da nova coleta, a pedido do usuario.

- Universo: os 59 casos identificados no manifesto `mdm/article_all_cases_10seed/protocol.json`. O artigo anuncia 60, mas falta especificacao do quarto tamanho rd400; nao inventar caso. Todas essas geometrias ja foram vistas, portanto nao e teste confirmatorio independente.
- Dez sementes novas e fixas por caso: 20261140 a 20261149. Total: 590 execucoes; cada execucao fornece um par antes/depois da mesma rota ALNS.
- Etapa 1: binario congelado SHA256 759f18afe83d7b41262163ec1c6917d0021d1ca2200250efd406e5a796648422, modo M (ALNS original reconstruido; sem MDM), parametros publicados, 30.000 iteracoes. Sem timeout externo. Argumentos de seguranca 10^15 s e 2^63-1 rotulos nao vinculantes.
- Etapa 2: fonte isolada `micro_mip_batch.py`, janelas 4 e 6, ate 16 candidatos, no maximo 3 passagens, SCIP com um thread e limite algoritmico de 1 s por janela. Preserva a melhor rota encontrada, com auditoria de cobertura e custo. Janela nao resolvida ate otimalidade nao implica prova; rotas curtas sao devolvidas sem polimento quando a regra de elegibilidade as exclui.
- Diferencas do piloto anterior: warm start inclui variaveis de ordem MTZ; ciclo repetido e melhoria de custo sao conferidos; validacao aceita a convencao congelada de duas visitas. Fontes/artefatos do piloto preservados. Gate sintetico `batch_gate.json`: 24 janelas conferidas contra enumeracao e teste de rota de duas visitas.
- Comparacao primaria: custo antes/depois e tamanho do ganho para cada semente, com tempo integral da preparacao, ALNS, validacao e polimento. O hibrido recebe tempo adicional de polimento. Nao interpretar esta coleta como superioridade com orcamento de tempo igual; essa hipotese exige protocolo separado.
- Duas execucoes simultaneas, CPUs 0 e 2, lock global nao bloqueante. Execucao em servico de usuario separado da sessao do assistente. Protecao de memoria do servico pode produzir falha ambiental, nunca resultado completo ou TO cientifico. Ao falhar qualquer job: preservar logs e interromper admissao de novos jobs para revisao.
- Ordem fixa: numero de visitas crescente, nome do caso, semente. Jobs e fingerprints de dados/fontes/binario congelados em `all59_10seed/protocol.json`.
- Bundles atomicos, logs ALNS preservados; estado e PIDs rastreaveis. Auditor separado confere hashes, semente, modo, 30.000 iteracoes, ambas as rotas, cobertura, custo, ganho e tempos. Falhas e pendencias ficam explicitas.
- PDF separado: `output/pdf/ctp_alns_micro_mip_all59.pdf`. Atualizacao automatica aproximadamente a cada minuto com bundles encerrados; medias por caso somente com 10/10 completas, melhores parciais com denominador explicito. Aviso nesta conversa a cada 30 minutos. Ao completar 590/590 e passar auditoria final, revisar PDF e desativar tarefa.
- Sem tuning ou mudanca de fonte durante a coleta. Preservar PCCTP parado, Utils.h, fontes e lotes anteriores. O lote local MDM interrompido em 216/600 nao e retomado por esta coleta.

Comandos: `all59.py prepare` cria manifesto; `all59.py collect` inicia uma unica coleta preparada; `all59_report.py` verifica bundles e gera PDF parcial/final. Nao reiniciar `collect` sobre estado RUNNING/FAILED sem investigar processos e preservar tentativas.

## Emenda 1 (08/11/2026) - Adoção dos parâmetros de TO do autor (Vargas et al. 2017)
- A pedido do usuário, adotados os limites originais de corte do autor para viabilizar as instâncias maiores que excedem a capacidade monodirecional sem heurística de busca bidirecional:
  - `safety_seconds = 1800` (30 minutos por execução)
  - `label_cap = 2000000` (2 milhões de rótulos no seletor DP)
- Runs que excedem o tempo limite ou teto de rótulos encerram com `complete=False` e são registradas com `status='CENSORED'` (análogo à marcação `TO` / `NR` do artigo para `rd400`). O polimento Micro-MIP é aplicado sobre a melhor rota intermediária factível obtida pelo ALNS.
- Os 450 bundles previamente concluídos (casos 1 a 45, 10 sementes cada) são 100% preservados e auditados, sendo aceito o hash de protocolo original `d12fc0c15f81dbbaecf6c082405bfc4653359d284ae45727e73ab6ab2d9798af`.
