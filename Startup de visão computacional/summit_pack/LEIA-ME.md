# Kit de materiais FruitCam_ai para o Siará Tech Summit

Gerado por `tools/build_summit_pack.py` a partir dos mesmos arquivos usados no app. Para atualizar, rode de novo os scripts (ver MEDIA.md na raiz do projeto).

## Conteúdo

- `figuras/`: 8 figuras científicas em SVG e PNG 300 dpi, com `LEGENDAS.md`.
- `logo/`: logotipo sobre fundo claro e escuro, ícone do app, ícones 512 px, favicon e imagem de compartilhamento.
- `imagens/`: 2 fotos ilustrativas de terceiros (com crédito obrigatório) e 2 capturas do app (linha com câmera simulada e inspeção por foto).
- `video/`: demonstração gravada do app (MP4 e WebM, sem áudio, com legendas e transcrição), storyboard em 4 quadros, a animação das etapas (MP4 e GIF) e a simulação da esteira vista pela câmera (MP4 e WebM).
- `LICENCAS.md`: autor, licença, fonte e modificações de cada foto de terceiros.

## Regras de uso

- Logotipo: use o arquivo do fundo correspondente (claro ou escuro), sem recolorir, distorcer ou redesenhar. Margem livre mínima em volta: 0.25× a altura do desenho. Altura mínima do desenho: 20 px (logotipo) e 16 px (ícone).
- Os logotipos são recortes provisórios da imagem do kit enviada pela equipe (PNG); substitua pelos arquivos vetoriais originais assim que existirem.
- Fotos de terceiros: sempre com o rótulo “Imagem ilustrativa” e o crédito de `LICENCAS.md`. Não apresente como foto de campo, cliente ou fábrica.
- Figuras 3, 4 e 5 e a captura do painel usam dados sintéticos: mantenha o rótulo. A Figura 6 é medição real em fotos de campo de teste (separadas por foto); cite as limitações da legenda.
- As capturas da linha usam uma câmera simulada e dados sintéticos: mantenha o selo. O classificador atual é fraco (acurácia balanceada perto de 50% em fotos de campo, com o acaso em 33%) e manda toda fruta para conferência manual; os dados públicos de treino tinham a numeração de classes trocada em 1.466 de 3.098 fotos, e um número antigo de 80,9% de acerto vinha desse erro: não o use. Não apresente números de desempenho em esteira real: eles ainda não existem.
- Não há clientes, fábricas, parceiros ou números de desempenho em campo: não os mencione.

## Arquivos

- `figuras/fig1-pipeline.png`: 185 KB, 2161×1047 px
- `figuras/fig1-pipeline.svg`: 111 KB
- `figuras/fig2-classificacao.png`: 1282 KB, 2161×1511 px
- `figuras/fig2-classificacao.svg`: 662 KB
- `figuras/fig3-evento-estatistica.png`: 155 KB, 2161×755 px
- `figuras/fig3-evento-estatistica.svg`: 116 KB
- `figuras/fig4-previsao.png`: 206 KB, 2161×779 px
- `figuras/fig4-previsao.svg`: 148 KB
- `figuras/fig5-gaussiana.png`: 337 KB, 2161×1370 px
- `figuras/fig5-gaussiana.svg`: 194 KB
- `figuras/fig6-qualidade.png`: 308 KB, 2161×1464 px
- `figuras/fig6-qualidade.svg`: 155 KB
- `figuras/fig7-linha.png`: 169 KB, 2161×826 px
- `figuras/fig7-linha.svg`: 107 KB
- `figuras/fig8-esteira.png`: 149 KB, 2161×826 px
- `figuras/fig8-esteira.svg`: 91 KB
- `figuras/LEGENDAS.md`: 9 KB
- `imagens/01-cajus-no-cajueiro-ben-tavener-cc-by-2-0.jpg`: 543 KB, 2560×1714 px
- `imagens/02-plantacao-de-caju-pacajus-porto-neto-cc-by-sa-4-0.jpg`: 2206 KB, 2560×1920 px
- `imagens/03-app-linha-camera-simulada.png`: 1058 KB, 2880×1800 px
- `imagens/04-app-inspecao-por-foto.png`: 1758 KB, 2880×1800 px
- `LICENCAS.md`: 7 KB
- `logo/favicon.ico`: 4 KB
- `logo/icone-512.png`: 77 KB, 512×512 px
- `logo/icone-app.png`: 14 KB, 181×181 px
- `logo/icone-maskable-512.png`: 59 KB, 512×512 px
- `logo/imagem-compartilhamento-1200x630.png`: 70 KB, 1200×630 px
- `logo/logo-sobre-claro.png`: 51 KB, 678×278 px
- `logo/logo-sobre-escuro.png`: 24 KB, 407×150 px
- `video/belt-sim.mp4`: 318 KB
- `video/belt-sim.webm`: 252 KB
- `video/demo-poster.png`: 256 KB, 1280×720 px
- `video/demo.mp4`: 1380 KB
- `video/demo.vtt`: 1 KB
- `video/demo.webm`: 1397 KB
- `video/pipeline.gif`: 1120 KB, 960×304 px
- `video/pipeline.mp4`: 145 KB
- `video/storyboard/1-linha.png`: 308 KB, 1280×720 px
- `video/storyboard/2-monitor.png`: 256 KB, 1280×720 px
- `video/storyboard/3-camera.png`: 79 KB, 1280×720 px
- `video/storyboard/4-inspecao.png`: 323 KB, 1280×720 px
- `video/storyboard.png`: 951 KB, 2016×1336 px
- `video/TRANSCRICAO.md`: 2 KB

Total: 16.6 MB.
