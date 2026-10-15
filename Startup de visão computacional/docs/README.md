# Documentação do FruitCam_ai

Índice de tudo o que está em `docs/`. Os guias explicam como cada parte funciona, do conceito ao código. Os planos foram escritos antes de cada trabalho. Os relatórios são saídas reais de execuções.

A maior parte dos guias está em inglês, como foi escrita; os mais recentes estão em português.

---

## Guias: como cada parte funciona

| Guia | Assunto |
|---|---|
| [guides/webapp.md](guides/webapp.md) | A aplicação web: login, envio de foto, API, segurança |
| [guides/camera.md](guides/camera.md) | A câmera na esteira: detecção, rastreamento, classificador de três classes, estatística da linha |
| [guides/analytics.md](guides/analytics.md) | A camada estatística: crescimento, defeitos, previsão, ajuste gaussiano |
| [guides/dashboard.md](guides/dashboard.md) | O painel: os 8 gráficos e seus estados de honestidade |
| [guides/certificate.md](guides/certificate.md) | O certificado em PDF |
| [guides/showcase.md](guides/showcase.md) | Os dados sintéticos de demonstração |
| [guides/media.md](guides/media.md) | Logotipo, fotos, vídeos, figuras e animação |
| [guides/design.md](guides/design.md) | Identidade visual (substituída pela sala de controle) |
| [guides/control_and_motion.md](guides/control_and_motion.md) | Sala de controle: tema, barra de comandos, inspetor, simulação de limiar, replay, animações |
| [guides/dataset_and_layout.md](guides/dataset_and_layout.md) | Conjuntos de dados de esteira e o layout do site |
| [guides/model_v3.md](guides/model_v3.md) | Busca de dados reais, conferência dos downloads, ordem das classes nos rótulos e o classificador atual (`belt_v3`) |
| [guides/real_belt_kit.md](guides/real_belt_kit.md) | Kit de gravação e medição em esteira real: bandejas, somas de verificação, avaliação por bandeja |
| [guides/model_checks.md](guides/model_checks.md) | Calibração e alarme de podre, diagnóstico do lote excluído de Uganda, erros de contagem |
| [guides/ttst.md](guides/ttst.md) | Autotreino em tempo de teste (TTST): módulo opcional, desligado, com conjunto de controle e reversão |

## Arquitetura

| Documento | Assunto |
|---|---|
| [architecture/realtime.md](architecture/realtime.md) | Operação contínua: serviço de câmera, agregados incrementais, fluxo ao vivo |

## Dados

| Documento | Assunto |
|---|---|
| [data/collection.md](data/collection.md) | Checklist de campo, de uma página, para gravar bandejas na esteira |
| [data/requests.md](data/requests.md) | Pedidos de dados prontos para enviar |
| [data/datasets/README.md](data/datasets/README.md) | Conjuntos externos avaliados, com fichas e medições |

## Planos

| Plano | Trabalho |
|---|---|
| [plans/layout.md](plans/layout.md) | Reorganização do layout do site |
| [plans/control_room.md](plans/control_room.md) | Sala de controle |
| [plans/reorg_realtime_licenses.md](plans/reorg_realtime_licenses.md) | Organização das pastas, tempo real e licenças |

## Relatórios

| Pasta | Conteúdo |
|---|---|
| [reports/tests/](reports/tests/) | Saídas reais das suítes de teste de cada etapa |
| [reports/layout/](reports/layout/) | Capturas de tela antes e depois da reorganização do layout |
| [reports/visual/](reports/visual/) | Capturas antes e depois da sala de controle, e o [relatório de desempenho](reports/visual/perf.md) |
| [reports/bundle/](reports/bundle/) | Tamanhos do pacote da interface |
| [reports/reorg/](reports/reorg/) | Mapa de movimentação das pastas e as suítes de antes e depois |
| [reports/realtime/](reports/realtime/) | Testes e medições da arquitetura de tempo real |
| [reports/real_belt_kit/](reports/real_belt_kit/) | Ensaio de ponta a ponta do kit de esteira com vídeo gravado (teste do programa, não desempenho) |
| [reports/calibration/](reports/calibration/) | Calibração, curvas de precisão e ponto de operação do alarme de podre |
| [reports/uganda_diagnosis/](reports/uganda_diagnosis/) | Diagnóstico do lote excluído de Uganda, com folhas de contato |
| [reports/counting/](reports/counting/) | Contagem dupla e sobreposição na esteira simulada, antes e depois |
| [reports/ttst/](reports/ttst/) | Experimento de autotreino com mudança de domínio simulada e registro de cada atualização |

## Licenças

Não ficam aqui. O único lugar é [../LICENSES.md](../LICENSES.md), gerado de `legal/registry.json`. Os relatórios sobre licenças (por exemplo, a busca de conjuntos de dados) ficam em `legal/reports/`.
