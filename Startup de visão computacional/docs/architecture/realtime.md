# Operação contínua: câmera, armazenamento e estatística em tempo real

Este documento explica como o FruitCam_ai funciona quando a câmera fica ligada o dia inteiro, sem pausas, numa esteira de fábrica. Ele descreve o que foi construído em 2026-10-11, o que cada parte garante, como cada garantia foi testada e o que ainda não foi verificado.

O código não tem comentários; a explicação fica aqui.

---

## 1. O problema

Antes desta mudança o sistema funcionava bem numa demonstração de alguns minutos, mas tinha cinco fraquezas para rodar sem parar:

| Fraqueza | O que acontecia |
|---|---|
| Leitura e análise no mesmo passo | Se a análise de um quadro demorasse, os quadros seguintes da câmera se acumulavam e o sistema passava a analisar imagens cada vez mais antigas. |
| Gravação no mesmo passo | Se o banco de dados estivesse ocupado, a análise esperava. Se o programa caísse, as frutas contadas e ainda não gravadas se perdiam. |
| Nada religava a câmera | Se o programa da câmera terminasse por erro, ficava parado até alguém notar. |
| Estatística recalculada do zero | Cada consulta relia todos os eventos. Com a câmera gravando o tempo todo, o cache nunca valia e a leitura ficava mais lenta a cada dia. |
| Tela por consulta periódica | A página Linha perguntava ao servidor a cada 15 segundos. |

---

## 2. A arquitetura, em uma figura

```
 câmera (RTSP, USB)                        um processo por câmera (run_camera)
        │
        ▼
 ┌──────────────┐  só o quadro   ┌───────────────────────────┐  passagens  ┌──────────────┐
 │ leitor       │  mais novo     │ análise                   │ ──────────► │ fila em      │
 │ (thread)     │ ─────────────► │ detecta, rastreia, conta, │             │ disco        │
 │ reconecta    │                │ classifica, mede          │             │ (spool)      │
 └──────────────┘                └───────────────────────────┘             └──────┬───────┘
                                        │ quadro anotado e estado                 │
                                        ▼                                         ▼
                                 var/run/<câmera>/                         ┌──────────────┐
                                 frame.jpg, status.json                    │ gravador     │
                                                                           │ (thread)     │
 supervisor (run_line): liga um processo por câmera                        └──────┬───────┘
 e religa o que terminar                                                          │ uma transação
                                                                                  ▼
                                               ┌───────────────────────────────────────────────┐
                                               │ banco de dados                                │
                                               │ evento + agregado por minuto + agregado por   │
                                               │ dia, gravados juntos                          │
                                               └───────────────────┬───────────────────────────┘
                                                                   │
                         página Linha ◄── fluxo ao vivo (SSE) ◄────┤
                         Painel       ◄── agregados por dia   ◄────┘
```

Três ideias sustentam o desenho:

1. **Separar** ler, analisar e gravar. Cada um tem seu ritmo, e a lentidão de um não trava os outros.
2. **Anotar em disco antes de gravar no banco.** O que foi contado nunca depende de o banco estar livre nem de o programa continuar vivo.
3. **Manter a estatística pronta.** Em vez de reler todos os eventos a cada consulta, o sistema guarda somas por minuto e por dia e as atualiza a cada fruta.

---

## 3. As partes

### 3.1 Leitor de quadros: sempre o mais novo

Arquivo: [belt/capture.py](../../belt/capture.py), classe `LatestFrame`.

Uma thread só lê a câmera e guarda **apenas o quadro mais recente**. Quando a análise pede um quadro, recebe o mais novo; os que ficaram para trás são descartados e contados em `dropped_frames`. Assim o atraso entre o que a câmera vê e o que o sistema analisa nunca cresce.

Se a câmera cai, a thread fecha a conexão e tenta de novo, esperando 0,5 s, depois 1 s, 2 s, até o máximo de 30 s entre tentativas. O estado publicado passa a `reconnecting` e a contagem `reconnects` sobe. Para câmeras de rede, a abertura e a leitura têm limite de 5 s, para a thread não ficar presa numa conexão morta.

A hora de cada fruta é a hora em que o quadro foi **capturado**, não a hora em que terminou de ser analisado.

A simulação e os arquivos de vídeo não usam essa thread: neles todo quadro é analisado, na ordem.

### 3.2 Fila em disco: o que foi contado não se perde

Arquivo: [belt/spool.py](../../belt/spool.py), classe `Spool`. Fica em `var/run/<câmera>/spool/`.

Cada fruta que cruza a linha vira uma linha de texto num arquivo, gravada e confirmada no disco **antes** de qualquer tentativa de gravar no banco. Um segundo arquivo pequeno guarda até onde o banco já confirmou.

- Banco ocupado: a análise segue; a fila cresce e é esvaziada depois.
- Programa caiu: na próxima partida, o que estava na fila e não tinha sido confirmado é gravado.
- Queda no meio de uma escrita: a linha cortada é ignorada e as seguintes continuam válidas.
- Quando tudo foi confirmado e o arquivo passa de 1 MB, ele é esvaziado.

### 3.3 Gravação exata: cada fruta uma única vez

Arquivo: [core/ingest.py](../../core/ingest.py), função `store`.

Reenviar a fila depois de uma queda pode repetir frutas que já estavam no banco. Para isso cada passagem recebe um identificador único (`uid`), formado por câmera, instante da partida do serviço e número de sequência. O banco tem uma regra de unicidade nesse campo, e `store` descarta o que já existe.

Entregar pelo menos uma vez, mais descartar repetidos, resulta em gravar exatamente uma vez.

Toda gravação de evento passa por esse funil: a câmera e a análise de foto. Na mesma transação entram o evento e as somas da seção 3.4. Ou tudo é gravado, ou nada.

### 3.4 Agregados: a estatística já somada

Arquivo: [core/rollups.py](../../core/rollups.py). Tabelas novas em [core/models.py](../../core/models.py).

| Tabela | Uma linha por | Guarda | Quem usa |
|---|---|---|---|
| `MinuteStat` | câmera, minuto, lote, real ou demonstração | contagem de boa, baixa qualidade, podre e revisar; histograma de tamanhos; primeira e última passagem | página Linha |
| `DayCount` | dia, setor, tipo de fruta, boa ou não, tipo de defeito, real ou demonstração | número de frutas já decididas | Painel |
| `RollupState` | uma única linha | contadores que dizem se os agregados estão em dia | todas as leituras |

A matemática não mudou. As funções `p_chart`, `wilson` e `lot_verdict` de [belt/stats.py](../../belt/stats.py) são as mesmas; só a entrada delas passou a vir das somas por minuto. No Painel, os quatro redutores de [analytics/fruit_analytics.py](../../analytics/fruit_analytics.py) (`counts`, `deformity_counts`, `fruit_counts`, `sector_proportions`) aceitam uma coluna opcional `n` com o peso de cada linha. Sem essa coluna, o caminho de código é o de antes, linha por linha.

**Tamanho da fruta.** Mediana e percentis não podem ser somados, então cada minuto guarda um histograma com faixas de 0,5 mm. O valor informado é o centro da faixa, e por isso difere do valor exato em até 0,25 mm. A câmera configurada enxerga 1,6 pixel por milímetro, ou seja, um pixel vale 0,625 mm: o erro do histograma é menor que o da própria medição. O caminho por eventos usa o mesmo histograma, de modo que os dois caminhos dão sempre a mesma resposta.

**O certificado em PDF** continua lendo os eventos um a um, porque precisa da hora exata do primeiro e do último evento.

### 3.5 Como saber se os agregados estão certos

Somas mantidas à parte podem divergir do dado original se alguém gravar por fora do funil: um comando de carga, um teste, uma correção manual no banco. A proteção tem três camadas:

1. **Gatilhos no banco.** Três gatilhos na tabela de eventos somam 1 em `mutations` a cada inserção, alteração ou exclusão, venha de onde vier.
2. **Crédito do funil.** Quando o funil grava N eventos e atualiza as somas, soma N em `synced`. Se `mutations` e `synced` são iguais, as somas refletem todos os eventos.
3. **Recuo automático.** Se os números diferem, as leituras voltam a ler os eventos, como antes: mais lento, mas correto. A reconstrução (`rebuild`) refaz as somas e iguala os contadores.

A reconstrução acontece sozinha depois de cada migração do banco, no fim dos comandos de carga, na partida de cada câmera e do supervisor, e a cada 5 minutos dentro do gravador, se for preciso. Também pode ser pedida com `python manage.py rebuild_rollups`.

Os gatilhos são recriados depois de toda migração, porque o SQLite os apaga quando o Django reconstrói uma tabela.

### 3.6 Serviço de câmera

Arquivo: [core/service.py](../../core/service.py), classe `LineService`. O comando `run_camera` só monta e roda esse serviço.

O serviço junta as partes acima e publica o estado em `var/run/<câmera>/status.json`:

| Campo | Significado |
|---|---|
| `state` | `starting`, `connecting`, `running`, `reconnecting`, `stalled` ou `stopped` |
| `counted` | frutas contadas nesta execução |
| `passages` | frutas já gravadas no banco nesta execução |
| `backlog_bytes` | o que ainda está na fila em disco |
| `db_busy` | quantas vezes o banco estava ocupado |
| `dropped_frames`, `reconnects` | quadros antigos descartados e reconexões da câmera |
| `process_ms` | tempo médio de análise de um quadro |
| `frame_age_s` | idade do último quadro recebido |

**Parada limpa.** Ctrl+C, um sinal do sistema ou o arquivo `var/run/<câmera>/stop` fazem o serviço parar de ler, esvaziar a fila no banco (até 30 s) e publicar `stopped`. Se a fila não esvaziar, o que sobrou fica em disco para a próxima partida.

**Leitura do estado.** O arquivo de estado é trocado 15 vezes por segundo. No Windows, quem lê bem no instante da troca pode receber "acesso negado". A leitura tenta até cinco vezes, com pausas de centésimos de segundo, antes de dizer que a câmera está fora do ar. Esse defeito apareceu no teste com navegador: a página via a câmera "cair" por um instante e fechava o fluxo.

**Onde o gravador roda.** Em operação normal, numa thread própria com conexão própria ao banco. Quando o comando é chamado de dentro de uma transação já aberta, ou com `--fast`, grava no mesmo passo da análise, porque uma segunda conexão ficaria esperando a transação de fora.

### 3.7 Supervisor

Arquivos: [core/supervisor.py](../../core/supervisor.py) e o comando `run_line`.

O supervisor liga **um processo por câmera**. Um processo que cai não derruba os outros. A cada segundo ele verifica os processos:

- Processo terminou: espera 1 s e religa. Se cair de novo, espera 2 s, 4 s, 8 s, até 60 s.
- Processo ficou 60 s no ar: a espera volta a 1 s.
- Parada pedida: escreve o arquivo `stop` de cada câmera, espera até 40 s e só então encerra à força quem não saiu.

O estado fica em `var/run/supervisor.json`.

### 3.8 Fluxo ao vivo para a página Linha

Rota `GET /api/line/live` em [core/line_views.py](../../core/line_views.py). Exige login.

É um fluxo de eventos do servidor (SSE, `text/event-stream`). A cada segundo o servidor manda o estado da câmera. O resumo completo é enviado ao abrir, sempre que um minuto fecha e, se chegarem dados atrasados, no máximo a cada 5 s.

A página só abre o fluxo quando a câmera está ligada. Com a câmera desligada, ou se o navegador não tiver suporte, continua a consulta a cada 15 s. O fluxo dura 10 minutos; o navegador reabre sozinho.

A página só trata a câmera como desligada depois de três avisos seguidos de "fora do ar". Um aviso isolado não apaga o vídeo nem fecha o fluxo.

### 3.9 Saúde do sistema

Rota `GET /api/health`.

- Sem login: só `{"status": "ok"}`, `degraded` ou `down`, para um monitor externo.
- Com login: banco, agregados (em dia ou não, contadores, gatilhos), cada câmera com os campos da seção 3.6, supervisor e espaço livre em disco.

`degraded` significa: agregados fora de dia, ou supervisor ligado com alguma câmera fora do ar. `down`, com resposta 503, significa banco inacessível.

### 3.10 Retenção: o banco não cresce para sempre

Comando `prune_events`.

Medido: cada evento ocupa cerca de 250 bytes no banco, índices incluídos. Uma linha com 2 frutas por segundo gera cerca de 173 mil eventos e 43 MB por dia, perto de 16 GB por ano.

`python manage.py prune_events --days 90` mostra quantos eventos brutos de câmera com mais de 90 dias existem. Com `--yes`, apaga. **Os agregados ficam**, então os gráficos da Linha e do Painel mantêm o histórico. O que se perde para o período apagado é o detalhe fruta a fruta: inspetor, replay de lote e simulação de limiar.

O comando nunca roda sozinho. Ele registra a data de corte (`horizon`): a reconstrução dos agregados nunca toca o que é anterior a essa data, porque os eventos que os geraram já não existem.

---

## 4. O que foi medido

Máquina de desenvolvimento, Windows, SQLite. Reproduzir: `python scripts/bench_realtime.py`. Saída completa: [bench.txt](../reports/realtime/bench.txt).

Banco de teste com 320.000 eventos: 170.000 passagens de câmera nas últimas 24 horas e 150.000 registros de foto em 3 anos. Mediana de 5 execuções, com o cache limpo antes de cada uma.

| Pergunta | Lendo eventos | Lendo agregados | Ganho |
|---|---|---|---|
| Resumo da linha, 24 h em janelas de 60 min | 2.062 ms | 93 ms | 22× |
| Resumo da linha, 60 min em janelas de 1 min | 210 ms | 17 ms | 12× |
| Carga dos dados do Painel | 1.739 ms | 320 ms | 5,4× |
| Painel completo: carga e as 7 estatísticas | 2.924 ms | 1.113 ms | 2,6× |
| "Há dado novo?" (chave do cache, a cada consulta) | 124 ms | 1,3 ms | 92× |

Leitura honesta dos números:

- O ganho do Painel completo é menor porque a maior parte do tempo que sobra é o cálculo estatístico (ajustes, previsão, testes), que não depende de quantos eventos existem.
- O tempo lendo eventos cresce com o número de eventos. O tempo lendo agregados cresce com o número de dias e setores. A diferença aumenta a cada dia de operação.
- A gravação custou 11,3 ms por transação (evento mais os dois agregados), o que dá 177 frutas por segundo nesta máquina. Uma linha gera de 2 a 4 por segundo.
- A reconstrução completa dos agregados a partir de 320.000 eventos levou 11,9 s.

**Navegador de verdade.** `python scripts/check_live.py --seconds 120` sobe um servidor e uma câmera simulada em banco temporário, abre a página Linha no Edge e compara, a cada 10 s, o total que a página mostra com o que a API responde. Saída: [live_check.txt](../reports/realtime/live_check.txt). Em 120 s: 1 conexão de fluxo, 95 mensagens de estado e 25 resumos, cobrindo três viradas de minuto; a página esteve igual à API em 12 de 12 conferências; a página não fez nenhuma consulta periódica depois de abrir o fluxo; 250 frutas contadas e 250 gravadas, fila vazia, nenhum erro na página.

**Processos de verdade.** Em banco temporário, com a esteira simulada: o supervisor ligou duas câmeras, uma delas foi encerrada à força no meio da execução, foi religada 1 s depois, e a parada final foi limpa. Resultado: 72 frutas contadas, 72 eventos no banco, 72 identificadores distintos, agregados em dia, fila vazia. Cada câmera rodou a 16 a 17 quadros por segundo, com cerca de 32 ms de análise por quadro.

**Migração de um banco existente.** Numa cópia do banco desta máquina, com 320.921 eventos, `python manage.py migrate` levou 13 s: criou as tabelas e os 3 gatilhos e montou os agregados (1.050 minutos de linha e 41.058 contagens diárias), que ficaram em dia. O banco original não foi alterado; ele é migrado na primeira execução de `scripts/pitch.ps1` ou de `python manage.py migrate`.

---

## 5. Como cada garantia foi testada

Testes em [core/tests/test_realtime.py](../../core/tests/test_realtime.py). Saída real da suíte completa: [reorg_realtime_legal_test_output.txt](../reports/tests/reorg_realtime_legal_test_output.txt). Os números da tabela vêm dessa execução; os que dependem da hora do dia mudam um pouco a cada vez e por isso aparecem arredondados.

| Garantia | Teste | Resultado |
|---|---|---|
| Gatilhos existem e contam inserção, alteração e exclusão | `test_triggers_exist_and_count_every_insert_update_and_delete` | 3 gatilhos; contador sobe 3 |
| Somas mantidas a cada gravação são iguais às de uma reconstrução completa | `test_funnel_keeps_aggregates_identical_to_a_full_rebuild` | 4.000 eventos em lotes de 250: cerca de 1.900 minutos de linha e 2.000 contagens diárias, idênticos nos dois modos |
| A mesma passagem nunca é gravada duas vezes | `test_same_passage_is_stored_once` | 120 reenvios, 0 gravados |
| Resumo da linha é o mesmo pelos dois caminhos | `test_line_summary_is_identical_from_aggregates_and_from_events` | 51 combinações de período, janela e fonte: respostas iguais; quantis de tamanho a no máximo 0,24 mm do valor exato |
| Painel é o mesmo pelos dois caminhos | `test_dashboard_is_identical_from_aggregates_and_from_events` | 252 resultados idênticos (7 estatísticas, 2 períodos, 3 fontes, 3 filtros de setor, 2 intervalos de datas) |
| Gravação por fora do funil é percebida e corrigida | `test_writes_outside_the_funnel_are_noticed_and_healed` | percebida; Painel correto pelo caminho de eventos; reconstrução iguala |
| Quantis do histograma conferem | `test_size_summary_equals_numpy_on_the_binned_values` | iguais aos do numpy sobre os centros das faixas |
| Apagar eventos antigos mantém o histórico | `test_pruning_raw_events_keeps_the_history_in_the_aggregates` | mais de 1.000 eventos apagados; Painel idêntico antes e depois |
| Comandos de carga deixam os agregados em dia | `test_seed_commands_leave_the_aggregates_in_step` | em dia |
| Fila em disco sobrevive a reinício, linha cortada e esvaziamento | `SpoolTests` (3 testes) | passam |
| Leitor entrega o quadro mais novo e reconecta | `GrabberTests` | câmera falsa: cerca de 200 quadros entregues, 25 lidos, os demais descartados, 1 reconexão |
| Passagens deixadas por uma queda são gravadas uma única vez | `test_passages_left_by_a_crashed_run_are_stored_exactly_once` | 5 na fila, 2 já no banco: 3 gravadas, 5 no total |
| Pedido de parada encerra sem perder nada | `test_stop_request_ends_the_run_and_nothing_is_lost` | parou em 7 s; contadas e gravadas em número igual (13 na execução registrada); estado `stopped` |
| Leitura do estado resiste à troca do arquivo | `test_status_read_survives_the_file_being_replaced` | duas falhas seguidas de leitura: câmera continua no ar |
| Gravador em thread própria grava tudo | `ThreadedWriterTests` | 5 s de simulação: contadas igual a gravadas |
| Supervisor religa com espera crescente e para em ordem | `SupervisorTests` | esperas de 1, 2, 4 e 8 s; volta a 1 s depois de 60 s no ar |
| Saúde: curta sem login, detalhada com login | `test_health_is_short_for_strangers_and_detailed_after_login` | passa |
| Fluxo ao vivo exige login e manda o mesmo resumo da API | `test_live_stream_needs_login_and_sends_the_same_summary_as_the_api` | 403 sem login; resumo igual |

Os testes antigos da câmera continuam valendo: um evento por fruta contada, e nenhuma perda com o banco travado três vezes seguidas.

---

## 6. Como operar

```powershell
python manage.py migrate
python manage.py run_line
python manage.py run_line --stop
python manage.py run_camera linha-1
python manage.py rebuild_rollups
python manage.py prune_events --days 90
```

| Linha | O que faz |
|---|---|
| `migrate` | Cria as tabelas novas e os gatilhos, e monta os agregados a partir dos eventos que já existem. Só na primeira vez depois desta atualização. |
| `run_line` | Mantém todas as câmeras de `config/cameras.json` no ar. Para com Ctrl+C. |
| `run_line --stop` | Pede a parada a partir de outro terminal. |
| `run_camera linha-1` | Liga uma câmera só, sem supervisor. |
| `rebuild_rollups` | Refaz os agregados. Com `--if-needed`, só se estiverem fora de dia. |
| `prune_events --days 90` | Mostra o que seria apagado. Com `--yes`, apaga. |

Para a fábrica, o `run_line` deve ser iniciado pelo sistema operacional junto com a máquina: Agendador de Tarefas no Windows, ou um serviço systemd no Linux. Isso ainda não foi configurado nem testado.

---

## 7. O que não foi verificado

- **Câmera de verdade.** Reconexão, descarte de quadros e limites de tempo foram testados com uma câmera falsa em memória e com a esteira simulada. Nenhuma câmera RTSP ou USB foi ligada.
- **Dias seguidos de operação.** O teste mais longo com processos reais durou 40 segundos. Não houve teste de 24 horas, nem medição de consumo de memória ao longo do tempo.
- **Queda de energia.** A fila em disco confirma cada escrita, mas o desligamento brusco da máquina não foi ensaiado.
- **Vários usuários no fluxo ao vivo.** Cada navegador com a página Linha aberta ocupa uma conexão do servidor pelo fluxo de dados e outra pelo vídeo. Foi testado com um navegador, por 2 minutos. Com muitos usuários, o servidor de desenvolvimento do Django não serve; é preciso um servidor de produção com conexões suficientes.
- **Outro banco de dados.** Os gatilhos e o modo de transação são do SQLite. Em PostgreSQL os gatilhos teriam de ser reescritos; sem eles, o sistema recua para a leitura por eventos.
- **Desempate entre tipos de fruta fora da lista.** Se dois tipos de fruta fora de caju, castanha e melão tiverem exatamente a mesma contagem, a ordem em que aparecem pode diferir entre os dois caminhos. Os totais são iguais.

---

## 8. Próximos passos sugeridos

1. Ligar uma câmera real e repetir o teste do supervisor com cabo desconectado e reconectado.
2. Rodar 24 horas com a simulação e registrar memória, tamanho da fila e quadros descartados.
3. Registrar o `run_line` como serviço do sistema operacional na máquina da fábrica.
4. Definir com o cliente por quantos dias guardar o detalhe fruta a fruta e agendar o `prune_events`.
5. Trocar o servidor de desenvolvimento por um servidor de produção antes de abrir a página para mais de uma pessoa.
