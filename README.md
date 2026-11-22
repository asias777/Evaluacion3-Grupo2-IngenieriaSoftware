# SGRT — Prototipo funcional, Evaluación 3 (INACAP)

**Sistema web de gestión de requerimientos técnicos para una empresa contratista eléctrica.** Continuidad de la Evaluación 2, Grupo 2, carrera Analista Programador, sede Copiapó.

## Requisitos
Python 3.10 o superior, conexión a internet solo para instalar dependencias por primera vez. No se requiere servicio externo.

## Iniciar en Windows
1. Descomprime el ZIP.
2. Abre la carpeta `prototipo`.
3. Ejecuta `run_windows.bat`, o desde una terminal:
   ```powershell
   py -m pip install -r requirements.txt
   py init_db.py
   py -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```
4. Visita `http://127.0.0.1:8000`.
5. Lee las claves generadas **solo en tu equipo** en `data/credenciales_demo.txt`.

**Importante:** El script de inicialización crea cuatro usuarios (2 clientes de empresas distintas, un coordinador y un técnico), junto a un catálogo de materiales. Genera contraseñas aleatorias. Si la base ya existe, no modifica usuarios ni contraseñas.

## Demostración sugerida
- Inicia como cliente: crea una solicitud (RF-01) y consulta su estado e historial (RF-02).
- Inicia como coordinador: asigna un técnico (RF-03) y administra el catálogo de materiales.
- Inicia como técnico: abre la orden asignada, registra visita, material, informe y una evidencia opcional (RF-04/05).
- Inicia como coordinador: cierra la orden solo si consta como resuelta (RF-06).
- Comprueba que el otro cliente no puede ver solicitudes ajenas y que el técnico no accede a órdenes sin asignación (RNF-01).

## Organización
```
prototipo/
  main.py           # rutas, roles y lógica de negocio
  db.py             # conexión y repositorio de consultas SQL
  security.py       # almacenamiento/verificación de contraseñas
  init_db.py        # inicialización y credenciales aleatorias
  schema.sql        # esquema de base de datos
  templates/        # interfaces web con Jinja2
  static/           # CSS
  tests/            # pruebas automatizadas
```

## Seguridad y limitaciones
- PBKDF2-HMAC-SHA256 con sal aleatoria; contraseñas **no** se almacenan en texto plano.
- Consultas SQL parametrizadas; validación servidor; tokens CSRF; sesiones firmadas HttpOnly/SameSite; segregación por rol y empresa; archivos almacenados fuera de carpeta pública y descarga autenticada.
- Las evidencias se limitan a JPG/PNG/PDF de hasta 2 MB con validación de firma básica. **Esto no reemplaza inspección antivirus ni una política corporativa completa de archivos.**
- El secreto de sesión se genera automáticamente en `.secret` (fuera de Git); en producción usar `SGRT_SECRET` en variable de entorno y `SGRT_HTTPS=1` detrás de HTTPS.
- No existe hosting, notificación real por correo ni integración con la empresa minera: son extensiones planteadas en el diseño, **no** funcionalidades implementadas. La disponibilidad del técnico usa una regla académica de máximo cinco solicitudes sin cierre; requiere validación con la empresa.
- La aplicación es un **prototipo académico local**, no debe desplegarse a internet como producto empresarial sin endurecimiento, revisión técnica y pruebas de seguridad adicionales (rate limit, registro centralizado, backups automatizados, gestión de usuarios, monitoreo y TLS).
- `data/`, archivos de evidencia, credenciales y `.secret` están excluidos de Git.

## Pruebas
Instala las dependencias de prueba y luego ejecuta:
```
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
Resultados deben verificarse localmente antes de adjuntar capturas al informe. Un fallo deberá corregirse antes de la entrega.

## Publicar en GitHub
Crea un repositorio **privado o público según instrucciones del docente**, sube `prototipo/` y `schema.sql`, documentación y pruebas, sin incluir `data/` ni `.secret`. Copia el enlace verdadero al espacio reservado del informe Word. El ZIP y el repositorio deben reflejar la **misma versión** (3.0).

## Respaldos
Con la aplicación detenida, realiza copia del archivo `data/sistema.db` y del directorio `data/evidencias/`, guardándolos en un lugar seguro. La estrategia automática y restauración deben validarse antes de uso real.

## Referencia de requerimientos
RF-01 registro; RF-02 consulta e historial; RF-03 asignación; RF-04 visitas; RF-05 materiales; RF-06 cierre; RNF-01 control de acceso por rol y empresa.
