"""Crear BD y usuarios de demostración; claves aleatorias fuera del repositorio."""
import secrets
from pathlib import Path
from db import connect, database_path, initialize
from security import hash_password

def seed():
    initialize()
    credentials = []
    with connect() as conn:
        if conn.execute('SELECT count(*) FROM usuarios').fetchone()[0]:
            print('Base de datos ya inicializada; no se sobrescribieron usuarios.')
            return []
        conn.execute("INSERT INTO empresas (nombre,contacto) VALUES (?,?)", ('Minera Atacama Demo','contacto@example.test'))
        conn.execute("INSERT INTO empresas (nombre,contacto) VALUES (?,?)", ('Minera Cordillera Demo','oficina@example.test'))
        entries = [
            ('Coordinación Demo','coordinador@demo.test','coordinador',None),
            ('Técnico Demo','tecnico@demo.test','tecnico',None),
            ('Cliente Atacama','cliente@demo.test','cliente',1),
            ('Cliente Cordillera','cliente2@demo.test','cliente',2),
        ]
        for nombre, correo, rol, empresa in entries:
            password = secrets.token_urlsafe(15)
            conn.execute('INSERT INTO usuarios (nombre,correo,password_hash,rol,empresa_id) VALUES (?,?,?,?,?)',
                        (nombre,correo,hash_password(password),rol,empresa))
            credentials.append((correo,password,rol))
        for codigo,nombre,unidad in [('CAB01','Cable eléctrico','m'),('INT01','Interruptor','un'),('CON01','Conector','un')]:
            conn.execute('INSERT INTO materiales(codigo,nombre,unidad) VALUES (?,?,?)',(codigo,nombre,unidad))
    out = database_path().parent/'credenciales_demo.txt'
    out.write_text('USUARIOS DE DEMOSTRACIÓN (NO PUBLICAR EN GITHUB)\n'+'\n'.join(f'{u} | {p} | {r}' for u,p,r in credentials)+'\n',encoding='utf-8')
    try: out.chmod(0o600)
    except OSError: pass
    print('Base de datos creada en:',database_path())
    print('Credenciales privadas generadas en:', out)
    return credentials

if __name__ == '__main__':
    seed()
