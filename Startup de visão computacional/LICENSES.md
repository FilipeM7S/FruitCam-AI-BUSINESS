# Licenças, créditos e direitos autorais

Este é o único lugar do projeto com licenças, créditos e avisos de direitos autorais. Nenhuma outra página, documento ou arquivo de código repete essas informações: eles apontam para cá.

Arquivo gerado por `python tools/build_legal.py` a partir de [`legal/registry.json`](legal/registry.json). Não edite à mão: mude o registro e gere de novo. No site, o mesmo conteúdo está na página **Créditos e licenças** (`/creditos`).

| Seção | Itens |
|---|---|
| [1. Material próprio](#1-material-próprio) | 7 |
| [2. Fotos e vídeos de terceiros](#2-fotos-e-vídeos-de-terceiros) | 10 |
| [3. Conjuntos de dados](#3-conjuntos-de-dados) | 7 usados, 13 avaliados e não usados |
| [4. Tipografia](#4-tipografia) | 3 |
| [5. Software de código aberto](#5-software-de-código-aberto) | 22 |
| [6. Regras](#6-regras) | |
| [7. Como manter](#7-como-manter) | |

---

## 1. Material próprio

| Item | Licença | Origem | Observação | Arquivos publicados |
|---|---|---|---|---|
| Código-fonte, documentação e modelo treinado (`codigo`) | Material próprio da FruitCam. A equipe ainda não escolheu uma licença de distribuição; até lá vale a regra padrão: todos os direitos reservados. | Este repositório | O modelo foi treinado com o conjunto Coffee and Cashew Nut, listado em Conjuntos de dados; o crédito a esse conjunto acompanha qualquer uso do modelo. | 0 |
| Logotipo FruitCam_ai (provisório) (`brand`) | Marca da FruitCam; uso restrito | assets/brand/source/logo-kit-sheet.png (imagem do kit enviada pela equipe) | Recortes exatos, sem alterar cores nem proporções, da imagem do kit enviada pela equipe; serão substituídos pelos arquivos vetoriais originais. | 18 |
| Vídeo de demonstração do app (`demo-video`) | Material próprio da FruitCam; as fotos de terceiros visíveis na interface mantêm suas licenças, listadas em Fotos e vídeos de terceiros | Gravação de tela do app real em execução (tools/record_demo.py), com dados sintéticos | Gravação de tela do app FruitCam_ai (tools/record_demo.py). A interface gravada exibe fotos de terceiros da Wikimedia Commons, que mantêm suas licenças; autores e licenças em Fotos e vídeos de terceiros. | 12 |
| Vídeo da primeira análise (`primeira-analise-video`) | Material próprio da FruitCam; as fotos de terceiros visíveis na interface mantêm suas licenças, listadas em Fotos e vídeos de terceiros | Gravação de tela do app real em execução (tools/record_clip.py, Playwright recordVideo); foto real e saída real do modelo | Gravação de tela do app FruitCam_ai (tools/record_clip.py). A interface gravada exibe fotos de terceiros da Wikimedia Commons, que mantêm suas licenças; autores e licenças em Fotos e vídeos de terceiros. | 12 |
| Vídeo de simulação da esteira (`belt-sim`) | Material próprio da FruitCam | Gerado por tools/record_belt.py: esteira e frutas desenhadas por código, processadas pelo mesmo pipeline da câmera | Rótulos vêm da simulação, não do modelo de IA. | 8 |
| Figuras científicas (`figures`) | Material próprio da FruitCam | Geradas por assets/figures/make_figures.py a partir de dados sintéticos e de medições reais | A Figura 2 contém a foto “caju-vermelho”, listada em Fotos e vídeos de terceiros. | 19 |
| Esteira simulada ao vivo (página Linha) (`esteira-ao-vivo`) | Material próprio da FruitCam; os recortes de caju vêm do conjunto Coffee and Cashew Nut, listado em Conjuntos de dados | Gerada em tempo real por belt/simulate.py com os recortes de assets/media_src/belt_crops | As classes mostradas vêm das anotações do conjunto, não do modelo de IA. | 0 |

---

## 2. Fotos e vídeos de terceiros

### Plantação de caju em Pacajus (CE) (`caju-pacajus`)

- Crédito: “Plantação de caju em Pacajus”, por Porto Neto (Porto Neto), CC BY-SA 4.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Plantação_de_caju_em_Pacajus.jpg
- Autor: Porto Neto
- Licença: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Planta%C3%A7%C3%A3o_de_caju_em_Pacajus.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/8/8f/Planta%C3%A7%C3%A3o_de_caju_em_Pacajus.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2023-05-28 14:41:22; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras. Os derivados seguem a mesma licença (CC BY-SA).
- Onde aparece: Página Como funciona (faixa de abertura)
- Arquivos publicados: 12

### Cajus com castanha no cajueiro (`caju-arvore`)

- Crédito: “Cashew apple with nut - Caju”, por Ben Tavener (Ben Tavener), CC BY 2.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Cashew_apple_with_nut_-_Caju.jpg
- Autor: Ben Tavener
- Licença: [CC BY 2.0](https://creativecommons.org/licenses/by/2.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Cashew_apple_with_nut_-_Caju.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/b/b2/Cashew_apple_with_nut_-_Caju.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2011-09-07 14:55:31; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; convertido para AVIF, WebP e JPEG em várias larguras.
- Onde aparece: Inspeção por foto (faixa do topo); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Caju vermelho no cajueiro (`caju-vermelho`)

- Crédito: “Anacardium occidentale from Margarita island”, por Wilfredor (Wilfredor), dedicada ao domínio público (CC0), via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Anacardium_occidentale_from_Margarita_island.jpg
- Autor: Wilfredor
- Licença: [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en)
- Fonte: https://commons.wikimedia.org/wiki/File:Anacardium_occidentale_from_Margarita_island.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/2/24/Anacardium_occidentale_from_Margarita_island.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2013-05-13 16:39:58; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras.
- Onde aparece: Tela de análise (cartão de fruta: caju); Vídeo de demonstração e capturas de tela do app (aparece na interface gravada); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada); Figura 2 (Como funciona e kit do Summit)
- Arquivos publicados: 9

### Castanhas de caju cruas (`castanha`)

- Crédito: “Raw cashew”, por Fumikas Sagisavas (Fumikas Sagisavas), dedicada ao domínio público (CC0), via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Raw_cashew.jpg
- Autor: Fumikas Sagisavas
- Licença: [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en)
- Fonte: https://commons.wikimedia.org/wiki/File:Raw_cashew.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/c/c5/Raw_cashew.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2024-07-21 17:50:24; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras.
- Onde aparece: Tela de análise (cartão de fruta: castanha); Vídeo de demonstração e capturas de tela do app (aparece na interface gravada); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Melões amarelos (`melao`)

- Crédito: “Honeydew melon”, por Salil Kumar Mukherjee (Salil Kumar Mukherjee), CC BY-SA 4.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Honeydew_melon.jpg
- Autor: Salil Kumar Mukherjee
- Licença: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Honeydew_melon.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/e/e4/Honeydew_melon.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2023-06-04 09:53:14; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras. Os derivados seguem a mesma licença (CC BY-SA).
- Onde aparece: Tela de análise (cartão de fruta: melão); Vídeo de demonstração e capturas de tela do app (aparece na interface gravada); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Cajus sobre fundo branco (`guia-bom`)

- Crédito: “Cahew nut fruit 01”, por Prabhupuducherry (Prabhupuducherry), CC BY-SA 4.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Cahew_nut_fruit_01.jpg
- Autor: Prabhupuducherry
- Licença: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Cahew_nut_fruit_01.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/7/75/Cahew_nut_fruit_01.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2020-04-15 19:55:01; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras. Os derivados seguem a mesma licença (CC BY-SA).
- Onde aparece: Tela de análise (guia: exemplo bom); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Cajus amontoados (`guia-varias`)

- Crédito: “Cajús”, por Roberta Martins (Roberta Martins), CC BY-SA 3.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Cajús.jpg
- Autor: Roberta Martins
- Licença: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Caj%C3%BAs.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/d/d0/Caj%C3%BAs.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2013-09-23; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras. Os derivados seguem a mesma licença (CC BY-SA).
- Onde aparece: Tela de análise (guia: várias frutas); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Cajus pequenos entre folhas (`guia-longe`)

- Crédito: “Ripe cashew fruit (483016375)”, por Colleen Taugher (Colleen Taugher from Lewiston Idaho, USA), CC BY 2.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Ripe_cashew_fruit_(483016375).jpg
- Autor: Colleen Taugher from Lewiston Idaho, USA
- Licença: [CC BY 2.0](https://creativecommons.org/licenses/by/2.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Ripe_cashew_fruit_(483016375).jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/6/6a/Ripe_cashew_fruit_%28483016375%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2005-11-05 15:36; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras.
- Onde aparece: Tela de análise (guia: longe, entre folhas); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Cajus em cena com pouca luz (`guia-escuro`)

- Crédito: “Cashew 2”, por Ashay vb (Ashay vb), CC BY-SA 4.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Cashew_2.jpg
- Autor: Ashay vb
- Licença: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0)
- Fonte: https://commons.wikimedia.org/wiki/File:Cashew_2.jpg
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/a/a8/Cashew_2.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: 2018-04-08 17:59:03; obtida em 2026-10-03
- Modificações: Original reduzido para no máximo 2560 px e sem metadados; recortado; convertido para AVIF, WebP e JPEG em várias larguras. Os derivados seguem a mesma licença (CC BY-SA).
- Onde aparece: Tela de análise (guia: pouca luz); Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)
- Arquivos publicados: 9

### Seleção de batatas em esteira (Montana, EUA) (`video-batatas`)

- Crédito: “Potatoes Sorting Montana2026 (55252116350)”, por USDA (USDAgov), em domínio público (Public domain), via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Potatoes_Sorting_Montana2026_(55252116350).webm
- Autor: USDAgov
- Licença: [Public domain](https://commons.wikimedia.org/wiki/Template:PD-USGov-USDA)
- Fonte: https://commons.wikimedia.org/wiki/File:Potatoes_Sorting_Montana2026_(55252116350).webm
- Arquivo original: https://upload.wikimedia.org/wikipedia/commons/6/6a/Potatoes_Sorting_Montana2026_%2855252116350%29.webm?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original
- Data original: Taken on 6 May 2026, 00:57:18; obtida em 2026-10-04
- Modificações: Trecho de 6 s a partir de 23 s, recortado para excluir mãos e rostos, reduzido para 960 px de largura, sem áudio; convertido para WebM (VP9) e MP4 (H.264); quadro central como pôster em AVIF, WebP e JPEG.
- Onde aparece: Vídeo de demonstração e capturas de tela do app (aparece na interface gravada); Tela de login (fundo em vídeo)
- Arquivos publicados: 8

---

## 3. Conjuntos de dados

### Coffee and Cashew Nut Dataset (cashew part) (`cashew_makerere`)

- Atribuição exigida: Nakatumba-Nabende, J.; Katumba, A.; Sanya, R.; Tusubira, J.; Murindanyi, S.; Namanya, G.; Nabiryo, A. (2023). Coffee and Cashew Nut Dataset. Mendeley Data, V1. https://doi.org/10.17632/r46c6bpfpf.1. Licensed under CC BY 4.0.
- Autores: Joyce Nakatumba-Nabende, Andrew Katumba, Rahman Sanya, Jeremy Tusubira, Sudi Murindanyi, Gloria Namanya, Ann Nabiryo (Makerere University, Uganda)
- Versão: Mendeley Data version 1 (published 2023-11-10)
- Página: https://data.mendeley.com/datasets/r46c6bpfpf/1
- DOI: https://doi.org/10.17632/r46c6bpfpf.1
- Licença: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Licença como está escrita na fonte: Mendeley Data licence field on version 1: CC BY 4.0 (Creative Commons Attribution 4.0 International)
- Uso comercial: allowed with attribution
- Uso neste projeto: Treino, validação e teste do classificador de três classes (fotos de Uganda).
- Modificações: Recortes quadrados das caixas de frutos, com os estágios do fruto agrupados em boa, baixa qualidade e podre. No modelo atual (belt_v3) entram os 1.440 arquivos de rótulo com as classes em ordem alfabética (segundo lote). Os 1.589 arquivos do primeiro lote e os 69 sem ordem identificável ficam de fora.
- Citação: Sanya R., Nabiryo A. L., Tusubira J. F., Murindanyi S., Katumba A., Nakatumba-Nabende J. Coffee and cashew nut dataset: A dataset for detection, classification, and yield estimation for machine learning applications. Data in Brief 52 (2024) 109952.
- Material derivado: **Recortes de caju da esteira simulada** (`assets/media_src/belt_crops`), usado em: Página Linha (esteira simulada ao vivo). Recorte quadrado em volta da caixa anotada, fundo removido por máscara (GrabCut), ampliado para 128 px (Lanczos e leve aumento de nitidez). Só entram máscaras compactas (solidez ≥ 0,92) e lisas (textura < 4), o que exclui tufos de folhas anotados como fruta. As classes vêm das anotações do conjunto (podem ter erros), não do modelo.
- Material derivado: **Folhas de contato do diagnóstico dos rótulos** (`docs/reports/uganda_diagnosis`), usado em: Relatório interno docs/reports/uganda_diagnosis/report.md; não aparece no site. Recortes quadrados das caixas anotadas, reduzidos para 96 px e montados em grade com o nome da origem e da classe. As classes são as das anotações do conjunto, que este relatório põe em dúvida para um dos lotes.

### Potatoes Dataset (`potatoes`)

- Atribuição exigida: Štursa, D.; Doležel, P.; Ksiažek, J. (2025). Potatoes Dataset. University of Pardubice. Zenodo. https://doi.org/10.5281/zenodo.17494608. Licensed under CC BY 4.0.
- Autores: Dominik Štursa, Petr Doležel, Jakub Ksiažek (University of Pardubice, Czech Republic)
- Versão: Zenodo record 17494608 (published 2025-10-31)
- Página: https://zenodo.org/records/17494608
- DOI: https://doi.org/10.5281/zenodo.17494608
- Licença: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Licença como está escrita na fonte: Zenodo record licence field: cc-by-4.0; metadata file inside the zip: "License: CC BY 4.0"
- Uso comercial: allowed with attribution
- Uso neste projeto: Somente avaliação: segmentação, receita de treino e sensibilidade ao fundo numa esteira industrial real (batatas). Não entra no modelo do app.
- Modificações: Cópias rotacionadas, espelhadas e quase idênticas agrupadas; nova divisão sem repetição entre treino e teste; recortes redimensionados para 128 px.
- Citação: Štursa D., Doležel P., Ksiažek J. Potatoes Dataset. Zenodo, 2025. doi:10.5281/zenodo.17494608

### Lemons quality control dataset (`lemons`)

- Atribuição exigida: Lemons quality control dataset, Maciej Adamiak, SoftwareMill (2020), https://github.com/softwaremill/lemon-dataset, doi:10.5281/zenodo.3965568. MIT License, Copyright (c) 2020 SoftwareMill.
- Autores: Maciej Adamiak (SoftwareMill) (SoftwareMill)
- Versão: v1.0.0 (GitHub tag v1.0.0, archived on Zenodo 2020-07-29)
- Página: https://github.com/softwaremill/lemon-dataset
- DOI: https://doi.org/10.5281/zenodo.3965568
- Licença: [MIT](https://opensource.org/licenses/MIT)
- Licença como está escrita na fonte: README at tag v1.0.0: "MIT License, Copyright (c) 2020 SoftwareMill". The Zenodo record's licence field says "other-open".
- Uso comercial: allowed; keep the copyright and permission notice
- Uso neste projeto: Somente avaliação: sensibilidade ao fundo (bancada de laboratório, não esteira). Não entra no modelo do app.
- Modificações: Rótulo por imagem a partir das regiões anotadas (o pior defeito decide); todas as fotos de um mesmo limão no mesmo conjunto; imagens redimensionadas para 128 px.
- Citação: Adamiak M. Lemons quality control dataset. SoftwareMill, 2020. doi:10.5281/zenodo.3965568

### FruitNet: Indian Fruits Dataset with quality (Good, Bad & Mixed quality) (`fruitnet`)

- Atribuição exigida: Meshram, V.; Patil, K. (2022). FruitNet: Indian Fruits Dataset with quality (Good, Bad & Mixed quality). Mendeley Data, V3. https://doi.org/10.17632/b6fftwbr2v.3. Licensed under CC BY 4.0.
- Autores: Vishal Meshram, Kailas Patil
- Versão: Mendeley Data version 3 (published 2022-03-08)
- Página: https://data.mendeley.com/datasets/b6fftwbr2v/3
- DOI: https://doi.org/10.17632/b6fftwbr2v.3
- Licença: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Licença como está escrita na fonte: Mendeley Data licence field on version 3: CC BY 4.0 (Creative Commons Attribution 4.0 International)
- Uso comercial: allowed with attribution
- Uso neste projeto: Baixado para avaliação futura (fotos de celular, não esteira). Não entra no modelo do app.
- Modificações: Imagens “Mistas” excluídas; fotos quase idênticas agrupadas antes da divisão; imagens redimensionadas para 128 px.
- Citação: Meshram V., Patil K. FruitNet: Indian fruits image dataset with quality for machine learning applications. Data in Brief 40 (2022) 107686. doi:10.1016/j.dib.2021.107686

### Drone-based Agricultural Dataset for Crop Yield Estimation (partes de caju) (`cashew_drone_full`)

- Atribuição exigida: KaraAgro AI Foundation; Makerere AI Lab; Uganda Marconi Lab; National Coffee Research Institute; National Crops Resources Research Institute (2023). Drone-based Agricultural Dataset for Crop Yield Estimation. Hugging Face. https://doi.org/10.57967/hf/0959. Licensed under CC BY 4.0.
- Autores: KaraAgro AI Foundation (Gana); Makerere AI Lab, Uganda Marconi Lab, National Coffee Research Institute e National Crops Resources Research Institute (Uganda) (KaraAgro AI Foundation; Makerere University)
- Versão: Hugging Face revision 54ba9307e6f9ef441839a7286eee96b674993135 (last modified 2023-08-11)
- Página: https://huggingface.co/datasets/KaraAgroAI/Drone-based-Agricultural-Dataset-for-Crop-Yield-Estimation
- DOI: https://doi.org/10.57967/hf/0959
- Licença: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Licença como está escrita na fonte: Dataset card on Hugging Face, metadata block: "license: cc-by-4.0". The card also says the dataset has the DOI 10.57967/hf/0959 and was funded by the Lacuna Fund.
- Uso comercial: allowed with attribution
- Uso neste projeto: Treino, validação e teste do classificador belt_v3: fotos de Gana (resolução original) e conferência da ordem das classes nos rótulos de Uganda. É a fonte original, em resolução cheia, do conjunto Coffee and Cashew Nut listado acima.
- Modificações: Só parte das fotos de Gana foi baixada (1.712 de 4.715, escolhidas pelas anotações); recortes quadrados das caixas de frutos com lado de pelo menos 24 px, reduzidos para até 160 px; os quatro estágios do fruto foram agrupados em boa, baixa qualidade e podre.
- Citação: KaraAgro AI Foundation et al. Drone-based Agricultural Dataset for Crop Yield Estimation. Hugging Face, 2023. doi:10.57967/hf/0959
- Material derivado: **Folhas de contato do diagnóstico dos rótulos** (`docs/reports/uganda_diagnosis`), usado em: Relatório interno docs/reports/uganda_diagnosis/report.md; não aparece no site. Recortes quadrados das caixas anotadas, reduzidos para 96 px e montados em grade com o nome da origem e da classe. As classes são as das anotações do conjunto, que este relatório põe em dúvida para um dos lotes.

### Vídeos de linhas de seleção e embalagem (batata-semente e cítricos) (`usda_line_videos`)

- Atribuição exigida: U.S. Department of Agriculture (USDA), via Wikimedia Commons. Public domain.
- Autores: U.S. Department of Agriculture (USDA) (U.S. Department of Agriculture)
- Versão: copies kept by the media repository named on the page, uploaded there on 2026-03-17 and 2026-05-08
- Página: https://commons.wikimedia.org/wiki/Category:Files_from_U.S._Department_of_Agriculture_Flickr_stream
- DOI: —
- Licença: [Public domain](https://commons.wikimedia.org/wiki/Template:PD-USGov-USDA)
- Licença como está escrita na fonte: Wikimedia Commons, on each file page: "Public domain", category "PD USDA" (work of the United States Department of Agriculture). The files were copied from the USDA Flickr stream by a bot, and Commons volunteers confirm the licence shown on Flickr file by file. Checked again on 2026-10-12 through the Commons API: 10 of the 11 files were still in the category "Flickr videos review needed" and 1 was in "Flickr videos reviewed by trusted users" (potato_0912_b.webm). No file had a deletion request, and the SHA-1 of every file was the one recorded at download.
- Uso comercial: allowed; no attribution required
- Uso neste projeto: Fundos reais para o classificador belt_v3: quadros dos clipes de batata entram no treino como fundo dos recortes de caju; quadros do clipe de cítricos ficam só para teste. Os vídeos não têm rótulos e não ensinam o que é fruta boa ou ruim. Enquanto a revisão da licença na origem não terminar, nenhum quadro desses vídeos entra no site, no material de divulgação nem no repositório: eles ficam só no disco de dados. Os pesos do belt_v3 foram treinados com esses quadros como fundo; se a revisão for negativa, o modelo deve ser treinado de novo sem eles (python -m training.train_v3 --video-share 0).
- Modificações: Quadros extraídos a 2 por segundo, recortados nas regiões com produto e esteira (sem rostos) e reduzidos para 360 px no lado menor.
- Citação: Wikimedia Commons files: File:20260209-O-RD001-Lone Star Citrus Growers Facility.webm; File:Potatoes Sorting Montana2026 (55252116350).webm; File:20260429-P-OC319-DSC 0921.webm; File:20260429-P-OC319-DSC 0919.webm; File:20260429-P-OC319-DSC 0922.webm; File:20260429-P-OC319-DSC 0920.webm; File:20260429-P-OC319 DSC 0912.webm; File:20260429-P-OC319-DSC 0934.webm; File:20260429-P-OC319-DSC 0912.webm; File:20260429-P-OC319 0912.webm; File:20260429-P-OC319 DSC 0918 2.webm

### Apple grading and packing (vídeo) (`apple_grading_video`)

- Atribuição exigida: “Apple grading and packing”, por Amanpanta1990, CC BY-SA 4.0, via Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Apple_grading_and_packing.webm
- Autores: Amanpanta1990 (Wikimedia Commons)
- Versão: file uploaded to the media repository named on the page on 2025-09-23
- Página: https://commons.wikimedia.org/wiki/File:Apple_grading_and_packing.webm
- DOI: —
- Licença: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Licença como está escrita na fonte: Wikimedia Commons file page: "CC BY-SA 4.0", source "Own work".
- Uso comercial: allowed with attribution; adaptations must be shared under the same licence
- Uso neste projeto: Somente teste: fundos reais para medir se a resposta do classificador muda quando o fundo muda. Não entra no treino de nenhum modelo, por causa da cláusula de compartilhamento pela mesma licença.
- Modificações: Quadros extraídos a 2 por segundo e recortados na região das maçãs; usados só durante a avaliação.
- Citação: Amanpanta1990. Apple grading and packing. Wikimedia Commons, 2025.

### Conjuntos avaliados e não usados

| Conjunto | Página | Licença como está escrita na fonte | Motivo |
|---|---|---|---|
| FruitRoll-360 | https://ieee-dataport.org/documents/fruitroll-360 | Terms of Use: "This dataset is released solely for academic and research purposes. Any commercial use requires prior written permission from the authors. Users must not redistribute the dataset or any subset thereof without authorization." | research only; commercial use needs written permission; IEEE DataPort login required |
| Oranges Classification | https://ieee-dataport.org/documents/oranges-classification | No licence in the visible page text. The page's embedded schema.org metadata declares "license": "https://creativecommons.org/licenses/by/4.0/". | files are behind an IEEE DataPort login/subscription, which this task excludes; the CC BY 4.0 appears only in machine-readable page metadata, so confirm it with the author before relying on it |
| Sisfrutos Papaya | https://github.com/jhony2507/Sisfrutos-Papaya | README, section "License to use and download": "The Sisfrutos dataset is made available free of charge to academic and non-academic entities, such as research, teaching, scientific publications or personal experimentation, on a non-commercial basis. The use of this dataset, in whole or in part, is expressly prohibited for commercial purposes." | explicitly non-commercial; download links only on request |
| CSTAR-Det cashew kernel conveyor images (Nguyen-Duc, Kim, Pham; Array, 2026) | https://doi.org/10.1016/j.array.2026.101282 | The article is open access (CC BY according to OpenAlex). No dataset link or dataset licence could be read: the publisher page refused automated access. | closest match for cashew on a belt, but whether the images are public is unknown; a request to the authors is the next step |
| cashew grading (Roboflow Universe, workspace cashew-uznuc) | https://universe.roboflow.com/cashew-uznuc/cashew-grading-qdxdk | Search results list CC BY 4.0; the page itself refused access, so nothing could be confirmed. | origin of the images and the licence could not be verified |
| berry-conveyor-detection and berry-conveyor-segmentation (Hugging Face, Viper4717) | https://huggingface.co/datasets/Viper4717/berry-conveyor-detection | No licence field and no dataset card. | no licence, so no permission to use |
| Cashew_Dataset (Hugging Face, pt-sk) | https://huggingface.co/datasets/pt-sk/Cashew_Dataset | Licence field: mit. No dataset card, no description of origin. | origin not stated; a licence field alone does not show who made the images |
| Healthy-Defective Fruits (GitHub, luischuquim) | https://github.com/luischuquim/Healthy-Defective-Fruits | The repository has no licence file. | no licence |
| Assessment of Physicochemical Properties of Cashew Apple through Computer Vision (Mendeley Data) | https://data.mendeley.com/datasets/67kn43rj5c/1 | Mendeley Data licence field: CC BY 4.0. | licence is fine, but the images exist only inside a PDF presentation (6 varieties, 2 maturity stages): too few and not usable as training files |
| CocoaBeansQCV (Mendeley Data) | https://data.mendeley.com/datasets/sr279sf4hs/1 | Mendeley Data licence field: CC BY 4.0. | licence is fine and the setting is a conveyor, but the product is cocoa beans; not downloaded, kept as a candidate for a generic belt test |
| Conveyor-belt apple videos used in arXiv:2602.19278 | https://arxiv.org/abs/2602.19278 | The paper says the videos were "obtained from YouTube" and releases no data. | third-party YouTube footage with no licence and no labels |
| The Westland (HD) (Wikimedia Commons) | https://commons.wikimedia.org/wiki/File:The_Westland_(HD).webm | File page says public domain; the description is the text of a video channel asking for likes and subscriptions. | looks like a re-upload of a third-party video; the public-domain claim is not credible enough |
| Water Treaty Roundtable clip (Wikimedia Commons, USDA) | https://commons.wikimedia.org/wiki/File:Water_Treaty_Roundtable-Clip_Low_Bit_Rate_(55100033341).webm | Public domain (USDA). | licence is fine, but it is a filmed meeting: people talking, no usable line footage |

---

## 4. Tipografia

### Fraunces (`fonte-fraunces`)

- Autor: Undercase Type (Phaedra Charles e Flavia Zimbardi)
- Licença: [SIL Open Font License 1.1](https://openfontlicense.org); texto completo em [`legal/texts/OFL-fraunces.txt`](legal/texts/OFL-fraunces.txt)
- Fonte: https://github.com/google/fonts/tree/main/ofl/fraunces
- Modificações: Instâncias estáticas da fonte variável; no site, subconjunto com letras latinas e acentos do português, em WOFF2 (12 KB).
- Onde aparece: Títulos do site e do certificado em PDF

### Inter (`fonte-inter`)

- Autor: Rasmus Andersson
- Licença: [SIL Open Font License 1.1](https://openfontlicense.org); texto completo em [`legal/texts/OFL-inter.txt`](legal/texts/OFL-inter.txt)
- Fonte: https://github.com/google/fonts/tree/main/ofl/inter
- Modificações: Instâncias estáticas (regular, medium, semibold, bold) da fonte variável.
- Onde aparece: Texto, tabelas e gráficos do certificado em PDF

### JetBrains Mono (`fonte-jetbrains-mono`)

- Autor: JetBrains
- Licença: [SIL Open Font License 1.1](https://openfontlicense.org); texto completo em [`legal/texts/OFL-jetbrainsmono.txt`](legal/texts/OFL-jetbrainsmono.txt)
- Fonte: https://github.com/google/fonts/tree/main/ofl/jetbrainsmono
- Modificações: Instâncias estáticas (regular e semibold) da fonte variável.
- Onde aparece: Números, códigos e impressão digital do certificado em PDF

---

## 5. Software de código aberto

As versões estão em `requirements.txt` e `frontend/package.json`.

| Pacote | Origem | Licença | Papel | Observação |
|---|---|---|---|---|
| [Django](https://www.djangoproject.com) | python | BSD-3-Clause | Produto em execução |  |
| [djangorestframework](https://www.django-rest-framework.org) | python | BSD-3-Clause | Produto em execução |  |
| [whitenoise](https://whitenoise.readthedocs.io) | python | MIT | Produto em execução |  |
| [torch](https://pytorch.org) | python | BSD-3-Clause | Produto em execução |  |
| [torchvision](https://github.com/pytorch/vision) | python | BSD-3-Clause | Treino e construção | Usado só no treino. A rede em belt/mobilenet.py reproduz a arquitetura MobileNetV3-Small dessa biblioteca. |
| [opencv-python](https://github.com/opencv/opencv-python) | python | Apache-2.0 | Produto em execução | O pacote inclui bibliotecas de terceiros com licenças próprias, entre elas o FFmpeg (LGPL). |
| [pillow](https://python-pillow.github.io) | python | MIT-CMU | Produto em execução |  |
| [numpy](https://numpy.org) | python | BSD-3-Clause | Produto em execução | O pacote inclui componentes sob 0BSD, MIT, Zlib e CC0-1.0. |
| [pandas](https://pandas.pydata.org) | python | BSD-3-Clause | Produto em execução |  |
| [scipy](https://scipy.org) | python | BSD-3-Clause | Produto em execução |  |
| [reportlab](https://www.reportlab.com) | python | BSD-3-Clause | Produto em execução |  |
| [matplotlib](https://matplotlib.org) | python | Matplotlib License (baseada na PSF) | Treino e construção |  |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | python | BSD-2-Clause | Treino e construção | O pacote traz um executável do FFmpeg, que tem licença própria (LGPL ou GPL, conforme a compilação). É usado só para converter vídeos na construção das mídias; não é distribuído com o produto. |
| [requests](https://requests.readthedocs.io) | python | Apache-2.0 | Treino e construção |  |
| [playwright](https://github.com/microsoft/playwright-python) | python | Apache-2.0 | Somente testes |  |
| [pypdf](https://github.com/py-pdf/pypdf) | python | BSD-3-Clause | Somente testes |  |
| [vue](https://vuejs.org) | npm | MIT | Produto em execução |  |
| [vue-router](https://router.vuejs.org) | npm | MIT | Produto em execução |  |
| [chart.js](https://www.chartjs.org) | npm | MIT | Produto em execução |  |
| [vite](https://vite.dev) | npm | MIT | Treino e construção |  |
| [@vitejs/plugin-vue](https://github.com/vitejs/vite-plugin-vue) | npm | MIT | Treino e construção |  |
| [axe-core](https://www.deque.com/axe/) | npm | MPL-2.0 | Somente testes |  |

---

## 6. Regras

- Toda mídia de terceiros é hospedada neste servidor; nada é carregado de outros sites.
- Só entram mídias e conjuntos de dados com licença que permite uso comercial e adaptação.
- Foto ou vídeo de terceiros aparece no site com o rótulo “Imagem ilustrativa”, que leva à página Créditos.
- Conteúdo que sai do repositório sozinho (kit do Summit) leva a própria lista de créditos, gerada a partir deste registro.
- Licenças aceitas para mídia: expressão `^(CC0|Public domain|CC BY(-SA)? [0-9.]+)$`.
- Licenças aceitas para conjuntos de dados: CC0, CC BY 4.0, CC BY-SA 4.0, MIT, Apache 2.0, Public domain.

---

## 7. Como manter

1. Entrou uma foto, um vídeo, um conjunto de dados, uma fonte ou uma biblioteca nova? Registre em `legal/registry.json`. As fotos da Wikimedia Commons são registradas por `python tools/fetch_media.py`.
2. Rode `python tools/build_media.py` se a mídia mudou; ele atualiza `legal/usage.json` (onde cada item aparece e quais arquivos publicados vêm dele).
3. Rode `python tools/build_legal.py`. Ele reescreve este arquivo e `legal/site.json`, que alimenta a página Créditos.
4. Rode `python manage.py test core.tests.test_legal`. Os testes falham se algum arquivo publicado ficar sem registro, se este arquivo estiver desatualizado ou se uma licença for citada fora daqui.
