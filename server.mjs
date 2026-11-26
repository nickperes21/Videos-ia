import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import os from 'node:os';
import path from 'node:path';
const run=promisify(execFile);
import http from 'node:http';
import fs from 'node:fs';
const providers=[['Claude','ANTHROPIC_API_KEY','https://api.anthropic.com/v1/messages',process.env.CLAUDE_MODEL||'claude-sonnet-4-5'],['Gemini','GEMINI_API_KEY','',process.env.GEMINI_MODEL||'gemini-2.5-flash'],['Groq','GROQ_API_KEY','https://api.groq.com/openai/v1/chat/completions',process.env.GROQ_MODEL||'llama-3.3-70b-versatile'],['OpenRouter','OPENROUTER_API_KEY','https://openrouter.ai/api/v1/chat/completions',process.env.OPENROUTER_MODEL||'openrouter/free']];
http.createServer(async(req,res)=>{
if(req.method==='GET'&&req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(fs.readFileSync(new URL('./index.html',import.meta.url)));}
res.setHeader('Content-Type','application/json');
const send=(status,data)=>{res.statusCode=status;res.end(JSON.stringify(data));};
if(req.method!=='POST'||!['/api/script','/api/voice'].includes(req.url))return send(404,{error:'Rota inexistente.'});
if(!process.env.APP_PASSWORD||req.headers.authorization!==`Bearer ${process.env.APP_PASSWORD}`)return send(401,{error:'Configure a senha do servidor.'});
try{let raw='';for await(const c of req){raw+=c;if(raw.length>16000)throw Error('Pedido muito longo');}const {prompt,text,voice,rate}=JSON.parse(raw);
if(req.url==='/api/voice'){
 if(typeof text!=='string'||!text.trim()||text.length>2000)return send(400,{error:'Texto de voz inválido'});
 const allowed=['pt-BR-AntonioNeural','pt-BR-FranciscaNeural','pt-BR-ThalitaMultilingualNeural'];
 const selected=allowed.includes(voice)?voice:allowed[0];
 const speed=Math.max(-30,Math.min(30,Math.round(Number(rate)||0)));
 const dir=await fs.promises.mkdtemp(path.join(os.tmpdir(),'viral-voice-'));
 try{const output=path.join(dir,'voice.mp3');const input=path.join(dir,'text.txt');await fs.promises.writeFile(input,text);
 await run(process.env.EDGE_TTS_BIN||'edge-tts',['--voice',selected,'--rate='+ (speed>=0?'+':'')+speed+'%','--file',input,'--write-media',output],{timeout:60000,maxBuffer:1024*1024});
 const audio=await fs.promises.readFile(output);if(!audio.length)throw Error('empty');res.setHeader('Content-Type','audio/mpeg');return res.end(audio);
 }catch(e){return send(502,{error:e.code==='ENOENT'?'Edge TTS não instalado. Confira o Build Command.':e.killed?'Edge TTS: tempo limite excedido.':'Edge TTS não conseguiu gerar áudio. Serviço indisponível ou voz não suportada.'});}finally{await fs.promises.rm(dir,{recursive:true,force:true}).catch(()=>{});}

}
const instruction=`Crie roteiro factual em português para vídeo vertical low-poly 3D. Retorne apenas JSON {title,caption,scenes:[{text,duration,kind,objects:[{shape,x,y,z,sx,sy,sz,color,motion}]}]}. 4 a 6 cenas, texto de 8 a 16 palavras por cena. Cada cena deve ter 8 a 25 objetos personalizados, formando uma composição visual que explique o texto. shape: box, sphere, cone, cylinder, tree, house, mountain, person, cloud, rock, ring. Coordenadas x,z entre -5 e 5, y altura da base entre 0 e 7. sx,sy,sz dimensões entre 0.1 e 8. color hexadecimal #RRGGBB. motion: none, spin, float, orbit, rise, fall. kind: city, rain, sun, space, ocean, volcano, forest, desert, mountain. Use cores harmoniosas, composição central e objetos específicos do assunto. Não use código. Pedido: ${String(prompt)}`;
const errors=[];
for(const [name,env,url,model] of providers){const key=process.env[env]?.trim();if(!key)continue;
try{const gem=name==='Gemini',claude=name==='Claude';const endpoint=gem?'https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(model.replace(/^models\//,''))+':generateContent':url;
const headers={'Content-Type':'application/json',...(gem?{'x-goog-api-key':key}:claude?{'x-api-key':key,'anthropic-version':'2023-06-01'}:{Authorization:'Bearer '+key})};
const body=gem?{contents:[{parts:[{text:instruction}]}],generationConfig:{responseMimeType:'application/json',maxOutputTokens:16384}}:{model,messages:[{role:'user',content:instruction}],max_tokens:8192};
const r=await fetch(endpoint,{method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(90000)});
if(!r.ok){const j=await r.json().catch(()=>({}));const reason=j.error?.status||j.error?.type||'';const safe=/^[A-Za-z_]+$/.test(reason)?reason:'';errors.push(`${name}: HTTP ${r.status} ${safe} — ${r.status===429?'limite de uso ou cota':r.status===401||r.status===403?'chave ou permissão':r.status===404?'modelo indisponível':r.status===400?'pedido ou chave inválida':'falha do provedor'}`);continue;}
const j=await r.json();const s=gem?j.candidates?.[0]?.content?.parts?.filter(p=>!p.thought).map(p=>p.text||'').join(''):claude?j.content?.find(p=>p.type==='text')?.text:j.choices?.[0]?.message?.content;
if(!s)throw Error('Resposta vazia');let data;try{data=JSON.parse(s.trim().replace(/^```(?:json)?\s*|\s*```$/g,''));}catch{throw Error('Resposta JSON inválida ou incompleta');}if(!Array.isArray(data.scenes)||!data.scenes.length)throw Error('Resposta sem cenas');return send(200,{...data,provider:name});
}catch(e){errors.push(name+': '+(e.name==='TimeoutError'?'tempo de resposta excedido':['Resposta vazia','Resposta JSON inválida ou incompleta','Resposta sem cenas'].includes(e.message)?e.message:'falha de conexão ou processamento'));}}
return send(503,{error:errors.length?errors.join(' | '):'Nenhuma chave de API configurada. Verifique GEMINI_API_KEY no Render.'});
}catch(e){return send(400,{error:'Pedido inválido.'});}
}).listen(process.env.PORT||3000);
