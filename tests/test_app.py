"""Pruebas E3: RF-01 a RF-06, RNF-01, CSRF y validaciones."""
import re
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import db
import init_db
from main import app

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('SGRT_DB',str(tmp_path/'database.sqlite'))
    accounts=init_db.seed()
    users={role:(email,password) for email,password,role in accounts[:3]}
    users['cliente2'] = accounts[3][:2]
    return users

def csrf(page):
    result=re.search(r'name="csrf"[^>]*value="([^"]+)"',page.text)
    assert result, page.text[:100]
    return result.group(1)

def log_in(client, identity):
    page=client.get('/login')
    result=client.post('/login',data={'correo':identity[0],'password':identity[1],'csrf':csrf(page)},follow_redirects=False)
    assert result.status_code==303

def make_request(client):
    form=client.get('/solicitudes/nueva')
    response=client.post('/solicitudes/nueva',data={'titulo':'Falla en tablero de faena','descripcion':'El tablero presenta apagones intermitentes durante las noches.','ubicacion':'Faena sector norte','prioridad':'Alta','csrf':csrf(form)},follow_redirects=False)
    assert response.status_code==303
    return int(response.headers['location'].split('?')[0].rsplit('/',1)[1])

def test_workflow_end_to_end(setup):
    with TestClient(app) as c:
        log_in(c,setup['cliente']); sid=make_request(c)
        detail=c.get(f'/solicitudes/{sid}')
        assert 'Recibido' in detail.text
        assert 'Falla en tablero' in detail.text
        # Un cliente de otra minera no puede ver la orden.
        logout=c.post('/logout',data={'csrf':csrf(detail)},follow_redirects=False)
        assert logout.status_code==303
        log_in(c,setup['cliente2'])
        assert c.get(f'/solicitudes/{sid}').status_code==403
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['coordinador']); detail=c.get(f'/solicitudes/{sid}')
        result=c.post(f'/solicitudes/{sid}/asignar',data={'tecnico_id':'2','csrf':csrf(detail)},follow_redirects=False)
        assert result.status_code==303
        # No cerrar antes de resolución.
        assert c.post(f'/solicitudes/{sid}/cerrar',data={'csrf':csrf(c.get(f'/solicitudes/{sid}'))}).status_code==422
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['tecnico']); detail=c.get(f'/solicitudes/{sid}')
        result=c.post(f'/solicitudes/{sid}/visitas',data={'informe':'Se realizó revisión y recambio de componentes del tablero.','resuelto':'si','material_id':'1','cantidad':'2','csrf':csrf(detail)},follow_redirects=False)
        assert result.status_code==303
        assert 'Resuelto' in c.get(f'/solicitudes/{sid}').text
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['coordinador']); detail=c.get(f'/solicitudes/{sid}')
        assert c.post(f'/solicitudes/{sid}/cerrar',data={'csrf':csrf(detail)},follow_redirects=False).status_code==303
        assert 'Cerrado' in c.get(f'/solicitudes/{sid}').text
        hist=db.all_rows('SELECT * FROM historial WHERE solicitud_id=?',(sid,))
        assert len(hist)==4
        assert db.one('SELECT estado FROM solicitudes WHERE id=?',(sid,))['estado']=='Cerrado'
        assert db.one('SELECT cantidad FROM detalle_material')['cantidad']==2

def test_auth_csrf_and_validation(setup):
    with TestClient(app) as c:
        assert c.get('/solicitudes').status_code==401
        log_in(c,setup['cliente'])
        assert c.post('/solicitudes/nueva',data={'titulo':'prueba','descripcion':'x'*40,'ubicacion':'faena','prioridad':'Alta','csrf':'invalido'}).status_code==403
        form=c.get('/solicitudes/nueva')
        assert c.post('/solicitudes/nueva',data={'titulo':'c','descripcion':'corto','ubicacion':'ab','prioridad':'incorrecta','csrf':csrf(form)}).status_code==422
        assert c.get('/materiales').status_code==403
        assert c.post('/materiales',data={'codigo':'AA','nombre':'Cable','unidad':'m','csrf':csrf(c.get('/solicitudes'))}).status_code==403


def test_password_hashing():
    from security import hash_password,check_password
    hashed=hash_password('LargaYSegura123!')
    assert 'LargaYSegura123!' not in hashed
    assert check_password('LargaYSegura123!',hashed)
    assert not check_password('incorrecta',hashed)


def test_evidence_permission_and_negative_material(setup):
    import io
    with TestClient(app) as c:
        log_in(c,setup['cliente']); sid=make_request(c)
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['coordinador'])
        assert c.post(f'/solicitudes/{sid}/asignar',data={'tecnico_id':'2','csrf':csrf(c.get(f'/solicitudes/{sid}'))},follow_redirects=False).status_code==303
        assert c.post(f'/solicitudes/{sid}/asignar',data={'tecnico_id':'2','csrf':csrf(c.get(f'/solicitudes/{sid}'))},follow_redirects=False).status_code==422
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['tecnico'])
        data={'informe':'Informe completo de la actividad técnica realizada.','resuelto':'no','material_id':'1','cantidad':'-2','csrf':csrf(c.get(f'/solicitudes/{sid}'))}
        assert c.post(f'/solicitudes/{sid}/visitas',data=data).status_code==422
        data['cantidad']='1'
        # Imagen PNG válida de 1x1 píxel, generada para la prueba.
        png=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082')
        result=c.post(f'/solicitudes/{sid}/visitas',data=data,files={'evidencia':('evidencia.png',png,'image/png')},follow_redirects=False)
        assert result.status_code==303
        ev_id=db.one('SELECT id FROM evidencias')['id']
        assert c.get(f'/evidencias/{ev_id}').status_code==200
        c.post('/logout',data={'csrf':csrf(c.get('/solicitudes'))})
        log_in(c,setup['cliente2'])
        assert c.get(f'/evidencias/{ev_id}').status_code==403
