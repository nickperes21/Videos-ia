import os, json, subprocess, uuid, pathlib, re
import requests
from flask import Flask, request, jsonify, send_from_directory
from concurrent.futures import ThreadPoolExecutor
app=Flask(__name__); root=pathlib.Path(__file__).parent; out=root/'videos'; out.mkdir(exist_ok=True); jobs={}; pool=ThreadPoolExecutor(1)
def run(*args): subprocess.run(list(map(str,args)),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def generate(i,topic,duration,vertical):
 j=jobs[i]; d=out/i; d.mkdir(); w,h=(720,1280) if vertical else (1280,720)
 try:
  j['status']='Pesquisando e escrevendo roteiro'
  sources=[]
  try:
   r=requests.get('https://pt.wikipedia.org/w/api.php',params={'action':'query','generator':'search','gsrsearch':topic,'gsrlimit':4,'prop':'extracts','exintro':1,'explaintext':1,'format':'json'},headers={'User-Agent':'FabricaVideoLocal/1.0 (educational project)'},timeout=20).json()
   sources=[{'title':p['title'],'text':p.get('extract','')[:1800],'url':'https://pt.wikipedia.org/?curid='+str(p['pageid'])} for p in r.get('query',{}).get('pages',{}).values()]
  except Exception: pass
  prompt=f'Crie roteiro de vídeo em português brasileiro sobre {topic}, duração aproximada {duration} segundos. Use {int(duration*2.1)} palavras no total, 4 a 10 cenas. Não invente fatos, diferencie hipóteses. Retorne JSON com titulo, descricao, cenas (lista de objetos com narracao e busca, termo visual curto em inglês). Fontes: {json.dumps(sources,ensure_ascii=False)}'
  r=requests.post(os.getenv('OLLAMA_URL','http://localhost:11434')+'/api/generate',json={'model':os.getenv('OLLAMA_MODEL','qwen2.5:3b'),'prompt':prompt,'format':'json','stream':False},timeout=300); r.raise_for_status(); script=json.loads(r.json()['response']); scenes=script['cenas']; assert scenes
  j['script']=script; j['sources']=sources; clips=[]; credits=[]
  for n,s in enumerate(scenes[:12]):
   j['status']=f'Produzindo cena {n+1}/{len(scenes)}'; p=d/str(n); p.mkdir(); narration=str(s['narracao']); (p/'fala.txt').write_text(narration); run('espeak-ng','-v','pt-br','-s','155','-f',p/'fala.txt','-w',p/'voz.wav'); sec=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p/'voz.wav')]))
   img=p/'foto.jpg'; found=False
   try:
    data=requests.get('https://commons.wikimedia.org/w/api.php',params={'action':'query','generator':'search','gsrsearch':str(s['busca'])+' filetype:bitmap','gsrnamespace':6,'gsrlimit':6,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':1280,'format':'json'},headers={'User-Agent':'FabricaVideoLocal/1.0 (educational project)'},timeout=20).json()
    from PIL import Image
    import io
    for page in data.get('query',{}).get('pages',{}).values():
     info=page['imageinfo'][0]; m=info.get('extmetadata',{}); lic=m.get('LicenseShortName',{}).get('value','');
     if not ('CC BY' in lic or 'Public domain' in lic or 'CC0' in lic): continue
     rr=requests.get(info.get('thumburl',info['url']),timeout=20,headers={'User-Agent':'FabricaVideoLocal/1.0'}); rr.raise_for_status(); Image.open(io.BytesIO(rr.content)).convert('RGB').save(img); credits.append({'title':page['title'],'license':lic,'author':re.sub('<[^>]+>','',m.get('Artist',{}).get('value','')),'url':info.get('descriptionurl',info['url'])}); found=True; break
   except Exception: pass
   if not found:
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(w,h),'#14243b'); dr=ImageDraw.Draw(im); dr.ellipse((w*.15,h*.18,w*.85,h*.65),fill='#24486a'); im.save(img)
   import textwrap
   lines='\n'.join(textwrap.wrap(narration,width=34 if vertical else 58)); (p/'legenda.txt').write_text(lines)
   vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=30,drawtext=textfile='{p/'legenda.txt'}':fontcolor=white:fontsize=32:box=1:boxcolor=black@0.75:boxborderw=12:x=(w-tw)/2:y=h-th-80"
   clip=p/'clip.mp4'; run('ffmpeg','-y','-loop','1','-i',img,'-i',p/'voz.wav','-vf',vf,'-t',sec,'-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac',clip); clips.append(clip)
  (d/'concat.txt').write_text('\n'.join("file '"+str(c)+"'" for c in clips)); run('ffmpeg','-y','-f','concat','-safe','0','-i',d/'concat.txt','-c','copy',d/'video.mp4')
  from PIL import Image,ImageDraw,ImageFont,ImageOps
  import textwrap
  im=ImageOps.fit(Image.open(d/'0/foto.jpg'),(1280,720)); dr=ImageDraw.Draw(im); dr.rectangle((0,400,1280,720),fill='#111827'); font=ImageFont.truetype('DejaVuSans-Bold.ttf',55); dr.multiline_text((45,425),'\n'.join(textwrap.wrap(script['titulo'],32)[:4]),font=font,fill='#ffffff'); im.save(d/'thumbnail.jpg'); (d/'creditos.json').write_text(json.dumps({'fontes':sources,'imagens':credits},ensure_ascii=False,indent=2)); j.update(status='Pronto',done=True,credits=credits)
 except Exception as e: j.update(status='Erro: '+str(e)[:500],error=True)
@app.route('/')
def index(): return send_from_directory(root,'index.html')
@app.post('/generate')
def start():
 a=request.json; topic=str(a.get('topic','')).strip();
 if not topic: return jsonify(error='Informe um tema'),400
 i=uuid.uuid4().hex; jobs[i]={'status':'Na fila'}; pool.submit(generate,i,topic[:500],max(15,min(120,int(a.get('duration',60)))),bool(a.get('vertical',True))); return jsonify(id=i)
@app.get('/job/<i>')
def status(i): return jsonify(jobs.get(i,{'error':True,'status':'Projeto não encontrado'}))
@app.get('/videos/<path:p>')
def video(p): return send_from_directory(out,p)
if __name__=='__main__': app.run(host='0.0.0.0',port=5000)
