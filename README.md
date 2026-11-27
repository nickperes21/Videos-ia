# Fábrica de Vídeos
Protótipo local gratuito. No CachyOS/Arch:

sudo pacman -S python python-pip ffmpeg espeak-ng ttf-dejavu ollama

Em um terminal: `ollama serve` (se já estiver rodando, ignore).
Em outro: `ollama pull qwen2.5:3b`
Na pasta do projeto:

python -m venv .venv
source .venv/bin/activate.fish  # para fish; bash: source .venv/bin/activate
pip install flask requests pillow
python app.py

Abra http://localhost:5000. No celular na mesma rede, use http://IP-DO-PC:5000 (consulte `ip addr`). Não exponha a porta à internet: não há autenticação. O PC precisa permanecer ligado. Pesquisa e imagens precisam de internet; IA e voz são locais. A voz é sintética e as cenas são imagens com movimento, não animação generativa. Revise fatos, créditos e licenças antes de publicar. A duração é aproximada. Não há publicação automática nem escritório virtual. Se não houver imagem, usa fundo gráfico. Requisitos: FFmpeg com drawtext/libx264. 
