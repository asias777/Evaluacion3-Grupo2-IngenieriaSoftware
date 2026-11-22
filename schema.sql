PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS empresas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nombre TEXT NOT NULL UNIQUE,
 contacto TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS usuarios (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nombre TEXT NOT NULL,
 correo TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL,
 rol TEXT NOT NULL CHECK(rol IN ('cliente','coordinador','tecnico')),
 empresa_id INTEGER REFERENCES empresas(id),
 activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1)),
 CHECK ((rol='cliente' AND empresa_id IS NOT NULL) OR (rol!='cliente' AND empresa_id IS NULL))
);
CREATE TABLE IF NOT EXISTS solicitudes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 empresa_id INTEGER NOT NULL REFERENCES empresas(id),
 creada_por INTEGER NOT NULL REFERENCES usuarios(id),
 titulo TEXT NOT NULL,
 descripcion TEXT NOT NULL,
 ubicacion TEXT NOT NULL,
 prioridad TEXT NOT NULL CHECK(prioridad IN ('Baja','Media','Alta','Crítica')),
 estado TEXT NOT NULL DEFAULT 'Recibido' CHECK(estado IN ('Recibido','Asignado','En curso','Resuelto','Cerrado')),
 creada_en TEXT NOT NULL,
 cerrada_en TEXT,
 cerrado_por INTEGER REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS asignaciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
 tecnico_id INTEGER NOT NULL REFERENCES usuarios(id),
 asignado_por INTEGER NOT NULL REFERENCES usuarios(id),
 fecha TEXT NOT NULL,
 UNIQUE(solicitud_id, tecnico_id)
);
CREATE TABLE IF NOT EXISTS visitas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
 tecnico_id INTEGER NOT NULL REFERENCES usuarios(id),
 fecha TEXT NOT NULL,
 informe TEXT NOT NULL,
 resuelto INTEGER NOT NULL DEFAULT 0 CHECK(resuelto IN (0,1))
);
CREATE TABLE IF NOT EXISTS materiales (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL UNIQUE,
 nombre TEXT NOT NULL,
 unidad TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detalle_material (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 visita_id INTEGER NOT NULL REFERENCES visitas(id),
 material_id INTEGER NOT NULL REFERENCES materiales(id),
 cantidad REAL NOT NULL CHECK(cantidad>0)
);
CREATE TABLE IF NOT EXISTS evidencias (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 visita_id INTEGER NOT NULL REFERENCES visitas(id),
 archivo TEXT NOT NULL,
 nombre_original TEXT NOT NULL,
 tipo TEXT NOT NULL,
 tamano INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS historial (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 estado_anterior TEXT,
 estado_nuevo TEXT NOT NULL,
 detalle TEXT NOT NULL,
 fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sol_empresa ON solicitudes(empresa_id);
CREATE INDEX IF NOT EXISTS ix_asig_tecnico ON asignaciones(tecnico_id);
CREATE INDEX IF NOT EXISTS ix_hist_sol ON historial(solicitud_id);
