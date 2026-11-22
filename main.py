"""SGRT: prototipo académico, acceso segmentado por rol y empresa."""
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from db import BASE, all_rows, connect, initialize, one, database_path
from security import check_password

initialize()
app = FastAPI(title='Sistema de Gestión de Requerimientos Técnicos', docs_url=None, redoc_url=None)
secret_path = BASE / '.secret'
secret = os.getenv('SGRT_SECRET')
if not secret:
    if not secret_path.exists():
        secret_path.write_text(secrets.token_hex(32), encoding='utf-8')
        try: secret_path.chmod(0o600)
        except OSError: pass
    secret = secret_path.read_text(encoding='utf-8').strip()
app.add_middleware(SessionMiddleware, secret_key=secret, https_only=os.getenv('SGRT_HTTPS')=='1', same_site='lax', max_age=3600)
app.mount('/static', StaticFiles(directory=str(BASE/'static')), name='static')
templates = Jinja2Templates(directory=str(BASE/'templates'))
MAX_BYTES = 2 * 1024 * 1024
ALLOWED = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.pdf':'application/pdf'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def current_user(request: Request):
    user_id = request.session.get('uid')
    if user_id is None: return None
    user = one('SELECT id,nombre,correo,rol,empresa_id,activo FROM usuarios WHERE id=?',(user_id,))
    return user if user and user['activo'] else None

def require(request: Request, *roles):
    user = current_user(request)
    if not user: raise HTTPException(401, 'Debes iniciar sesión')
    if roles and user['rol'] not in roles: raise HTTPException(403, 'Acceso denegado por rol')
    return user

def verify(request, token):
    if not token or not secrets.compare_digest(str(token), str(request.session.get('csrf',''))):
        raise HTTPException(403, 'Validación CSRF no válida')

def render(request, name, **extra):
    if 'csrf' not in request.session: request.session['csrf'] = secrets.token_urlsafe(24)
    context={'request':request,'user':current_user(request),'csrf':request.session['csrf'], **extra}
    return templates.TemplateResponse(request=request, name=name, context=context)

def redirect(path, message=''):
    if message: path += ('&' if '?' in path else '?')+'msg='+quote(message)
    return RedirectResponse(path, status_code=303)

def solicitud_visible(user, solicitud_id):
    row = one('''SELECT s.*,e.nombre AS empresa_nombre,u.nombre AS creador_nombre,
                 (SELECT group_concat(t.nombre, ', ') FROM asignaciones a JOIN usuarios t ON t.id=a.tecnico_id WHERE a.solicitud_id=s.id) AS tecnicos
                 FROM solicitudes s JOIN empresas e ON e.id=s.empresa_id
                 JOIN usuarios u ON u.id=s.creada_por WHERE s.id=?''',(solicitud_id,))
    if not row: raise HTTPException(404, 'Solicitud inexistente')
    if user['rol']=='cliente' and row['empresa_id']!=user['empresa_id']:
        raise HTTPException(403, 'No puedes consultar solicitudes de otra empresa')
    if user['rol']=='tecnico' and not one('SELECT 1 FROM asignaciones WHERE solicitud_id=? AND tecnico_id=?',(solicitud_id,user['id'])):
        raise HTTPException(403, 'No tienes esta solicitud asignada')
    return row

def event(conn, sid, uid, before, after, detail):
    conn.execute('INSERT INTO historial(solicitud_id,usuario_id,estado_anterior,estado_nuevo,detalle,fecha) VALUES(?,?,?,?,?,?)',
                 (sid,uid,before,after,detail,now()))

def bad(message):
    raise HTTPException(422, message)

@app.get('/', response_class=HTMLResponse)
def root(request: Request):
    return redirect('/solicitudes' if current_user(request) else '/login')

@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request): return redirect('/solicitudes')
    return render(request,'login.html')

@app.post('/login')
def login(request: Request, correo: str=Form(...), password: str=Form(...), csrf: str=Form(...)):
    verify(request,csrf)
    u=one('SELECT * FROM usuarios WHERE correo=? AND activo=1',(correo.strip().lower(),))
    if not u or not check_password(password,u['password_hash']):
        return render(request,'login.html',error='Correo o contraseña incorrectos')
    request.session.clear()
    request.session['uid']=u['id']
    request.session['csrf']=secrets.token_urlsafe(24)
    return redirect('/solicitudes')

@app.post('/logout')
def logout(request: Request, csrf: str=Form(...)):
    verify(request,csrf)
    request.session.clear()
    return redirect('/login')

@app.get('/solicitudes', response_class=HTMLResponse)
def solicitudes(request: Request):
    user=require(request)
    if user['rol']=='cliente':
        rows=all_rows('''SELECT s.*,e.nombre AS empresa_nombre FROM solicitudes s JOIN empresas e ON e.id=s.empresa_id
                         WHERE s.empresa_id=? ORDER BY s.id DESC''',(user['empresa_id'],))
    elif user['rol']=='tecnico':
        rows=all_rows('''SELECT s.*,e.nombre AS empresa_nombre FROM solicitudes s JOIN empresas e ON e.id=s.empresa_id
                         JOIN asignaciones a ON a.solicitud_id=s.id WHERE a.tecnico_id=? ORDER BY s.id DESC''',(user['id'],))
    else:
        rows=all_rows('''SELECT s.*,e.nombre AS empresa_nombre FROM solicitudes s JOIN empresas e ON e.id=s.empresa_id ORDER BY s.id DESC''')
    return render(request,'solicitudes.html',solicitudes=rows)

@app.get('/solicitudes/nueva', response_class=HTMLResponse)
def nueva_page(request: Request):
    require(request,'cliente')
    return render(request,'nueva.html')

@app.post('/solicitudes/nueva')
def nueva(request: Request, titulo: str=Form(...), descripcion: str=Form(...), ubicacion: str=Form(...),
          prioridad: str=Form(...), csrf: str=Form(...)):
    user=require(request,'cliente');verify(request,csrf)
    titulo=titulo.strip();descripcion=descripcion.strip();ubicacion=ubicacion.strip()
    if not (5<=len(titulo)<=120) or not (10<=len(descripcion)<=2000) or not (3<=len(ubicacion)<=180):
        bad('Título (5–120), descripción (10–2000) y ubicación (3–180) son obligatorios')
    if prioridad not in ('Baja','Media','Alta','Crítica'): bad('Prioridad inválida')
    with connect() as conn:
        cur=conn.execute('''INSERT INTO solicitudes(empresa_id,creada_por,titulo,descripcion,ubicacion,prioridad,creada_en)
                            VALUES(?,?,?,?,?,?,?)''', (user['empresa_id'],user['id'],titulo,descripcion,ubicacion,prioridad,now()))
        sid=cur.lastrowid
        event(conn,sid,user['id'],None,'Recibido','Registro inicial de solicitud')
    return redirect('/solicitudes/'+str(sid),'Solicitud registrada correctamente')

@app.get('/solicitudes/{sid}', response_class=HTMLResponse)
def detalle(request: Request, sid: int):
    user=require(request)
    sol=solicitud_visible(user,sid)
    historial=all_rows('''SELECT h.*,u.nombre FROM historial h JOIN usuarios u ON u.id=h.usuario_id
                          WHERE h.solicitud_id=? ORDER BY h.id DESC''',(sid,))
    visitas=all_rows('''SELECT v.*,u.nombre AS tecnico_nombre FROM visitas v JOIN usuarios u ON u.id=v.tecnico_id
                       WHERE v.solicitud_id=? ORDER BY v.id DESC''',(sid,))
    materiales_visita=all_rows('''SELECT d.visita_id,m.nombre,m.unidad,d.cantidad FROM detalle_material d
                                JOIN materiales m ON m.id=d.material_id JOIN visitas v ON v.id=d.visita_id
                                WHERE v.solicitud_id=?''',(sid,))
    evidencias=all_rows('''SELECT ev.*,v.solicitud_id FROM evidencias ev JOIN visitas v ON v.id=ev.visita_id
                          WHERE v.solicitud_id=?''',(sid,))
    tecnicos=all_rows("SELECT id,nombre FROM usuarios WHERE rol='tecnico' AND activo=1") if user['rol']=='coordinador' else []
    materiales=all_rows('SELECT * FROM materiales ORDER BY nombre') if user['rol']=='tecnico' else []
    return render(request,'detalle.html',sol=sol,historial=historial,visitas=visitas,materiales_visita=materiales_visita,
                  evidencias=evidencias,tecnicos=tecnicos,materiales=materiales)

@app.post('/solicitudes/{sid}/asignar')
def asignar(request: Request, sid: int, tecnico_id: int=Form(...), csrf: str=Form(...)):
    user=require(request,'coordinador');verify(request,csrf)
    sol=solicitud_visible(user,sid)
    if sol['estado']=='Cerrado': bad('Una solicitud cerrada no puede asignarse')
    tech=one("SELECT id,nombre FROM usuarios WHERE id=? AND rol='tecnico' AND activo=1",(tecnico_id,))
    if not tech: bad('Selecciona un técnico válido')
    if one('SELECT 1 FROM asignaciones WHERE solicitud_id=? AND tecnico_id=?',(sid,tecnico_id)):
        bad('El técnico ya está asignado a esta solicitud')
    # Disponibilidad simplificada: límite de 5 solicitudes no cerradas en cartera.
    carga=one('''SELECT count(*) AS n FROM asignaciones a JOIN solicitudes s ON s.id=a.solicitud_id
                WHERE a.tecnico_id=? AND s.estado!='Cerrado' ''',(tecnico_id,))['n']
    if carga>=5: bad('Técnico sin disponibilidad según límite del prototipo')
    with connect() as conn:
        conn.execute('INSERT INTO asignaciones(solicitud_id,tecnico_id,asignado_por,fecha) VALUES(?,?,?,?)',(sid,tecnico_id,user['id'],now()))
        new='Asignado' if sol['estado']=='Recibido' else sol['estado']
        conn.execute('UPDATE solicitudes SET estado=? WHERE id=?',(new,sid))
        event(conn,sid,user['id'],sol['estado'],new,'Asignado a '+tech['nombre'])
    return redirect('/solicitudes/'+str(sid),'Técnico asignado')

@app.post('/solicitudes/{sid}/visitas')
async def registrar_visita(request: Request, sid: int, informe: str=Form(...), resuelto: str=Form('no'),
                          material_id: str=Form(''), cantidad: str=Form(''), evidencia: UploadFile|None=File(None),
                          csrf: str=Form(...)):
    user=require(request,'tecnico');verify(request,csrf)
    sol=solicitud_visible(user,sid)
    if sol['estado']=='Cerrado': bad('La solicitud está cerrada')
    informe=informe.strip()
    if not 10<=len(informe)<=3000: bad('Informe debe contener entre 10 y 3000 caracteres')
    if resuelto not in ('si','no'): bad('Estado de resolución inválido')
    mid=None; qty=None
    if material_id or cantidad:
        try: mid=int(material_id);qty=float(cantidad)
        except ValueError: bad('Material y cantidad no válidos')
        if not (0<qty<=100000) or not one('SELECT id FROM materiales WHERE id=?',(mid,)):
            bad('Material o cantidad inválidos')
    file_data=None; ext=None; filename=None
    if evidencia and evidencia.filename:
        filename=Path(evidencia.filename).name
        ext=Path(filename).suffix.lower()
        if ext not in ALLOWED: bad('Evidencia: solo PNG, JPG o PDF')
        file_data=await evidencia.read(MAX_BYTES+1)
        if len(file_data)>MAX_BYTES: bad('El archivo supera los 2 MB permitidos')
        # Comprueba firmas básicas además de la extensión, sin ejecutar archivos.
        if ext in ('.jpg','.jpeg') and not file_data.startswith(b'\xff\xd8\xff'): bad('JPG no válido')
        if ext=='.png' and not file_data.startswith(b'\x89PNG\r\n\x1a\n'): bad('PNG no válido')
        if ext=='.pdf' and not file_data.startswith(b'%PDF-'): bad('PDF no válido')
    with connect() as conn:
        cur=conn.execute('INSERT INTO visitas(solicitud_id,tecnico_id,fecha,informe,resuelto) VALUES(?,?,?,?,?)',
                         (sid,user['id'],now(),informe,1 if resuelto=='si' else 0))
        vid=cur.lastrowid
        if mid is not None:
            conn.execute('INSERT INTO detalle_material(visita_id,material_id,cantidad) VALUES(?,?,?)',(vid,mid,qty))
        if file_data is not None:
            name=uuid.uuid4().hex+ext
            directory=database_path().parent/'evidencias'
            directory.mkdir(parents=True,exist_ok=True)
            (directory/name).write_bytes(file_data)
            conn.execute('INSERT INTO evidencias(visita_id,archivo,nombre_original,tipo,tamano) VALUES(?,?,?,?,?)',
                         (vid,name,filename,ALLOWED[ext],len(file_data)))
        new='Resuelto' if resuelto=='si' else 'En curso'
        conn.execute('UPDATE solicitudes SET estado=? WHERE id=?',(new,sid))
        event(conn,sid,user['id'],sol['estado'],new,'Visita registrada #'+str(vid))
    return redirect('/solicitudes/'+str(sid),'Informe de visita guardado')

@app.post('/solicitudes/{sid}/cerrar')
def cerrar(request: Request, sid: int, csrf: str=Form(...)):
    user=require(request,'coordinador');verify(request,csrf)
    sol=solicitud_visible(user,sid)
    if sol['estado']!='Resuelto': bad('Solo se cierran trabajos que el técnico haya marcado como resueltos')
    with connect() as conn:
        conn.execute('UPDATE solicitudes SET estado=?,cerrada_en=?,cerrado_por=? WHERE id=?',('Cerrado',now(),user['id'],sid))
        event(conn,sid,user['id'],sol['estado'],'Cerrado','Cierre confirmado por coordinación')
    return redirect('/solicitudes/'+str(sid),'Solicitud cerrada')

@app.get('/evidencias/{eid}')
def descargar_evidencia(request: Request, eid: int):
    user=require(request)
    record=one('''SELECT ev.*,v.solicitud_id FROM evidencias ev JOIN visitas v ON v.id=ev.visita_id WHERE ev.id=?''',(eid,))
    if not record: raise HTTPException(404,'Evidencia no encontrada')
    solicitud_visible(user,record['solicitud_id'])
    path=database_path().parent/'evidencias'/record['archivo']
    if not path.is_file(): raise HTTPException(404,'Archivo no disponible')
    return FileResponse(path,media_type=record['tipo'],filename=record['nombre_original'])

@app.get('/materiales', response_class=HTMLResponse)
def lista_materiales(request: Request):
    require(request,'coordinador')
    return render(request,'materiales.html',materiales=all_rows('SELECT * FROM materiales ORDER BY codigo'))

@app.post('/materiales')
def crear_material(request: Request, codigo: str=Form(...), nombre: str=Form(...),unidad: str=Form(...),csrf: str=Form(...)):
    require(request,'coordinador');verify(request,csrf)
    codigo=codigo.strip().upper();nombre=nombre.strip();unidad=unidad.strip()
    if not 2<=len(codigo)<=15 or not 3<=len(nombre)<=100 or not 1<=len(unidad)<=20: bad('Datos de material no válidos')
    try:
        with connect() as conn: conn.execute('INSERT INTO materiales(codigo,nombre,unidad) VALUES(?,?,?)',(codigo,nombre,unidad))
    except Exception as exc:
        import sqlite3
        if isinstance(exc,sqlite3.IntegrityError): bad('Ya existe este código de material')
        raise
    return redirect('/materiales','Material agregado')

@app.get('/salud')
def health():
    return {'estado':'ok','sistema':'SGRT','version':'3.0-prototipo'}
