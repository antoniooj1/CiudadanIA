import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

TIPOS = ('Opción múltiple', 'Texto', 'Sí/No', 'Ubicación GPS', 'Imagen')
BD = Path(__file__).with_name('ciudadania.sqlite3')


class Regla(ValueError):
    pass


@contextmanager
def conexion():
    with sqlite3.connect(BD) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        yield db


def iniciar():
    with conexion() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS portafolio (
          id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
          descripcion TEXT NOT NULL, creado TEXT DEFAULT CURRENT_DATE);
        CREATE TABLE IF NOT EXISTS formulario (
          id INTEGER PRIMARY KEY, portafolio INTEGER NOT NULL REFERENCES portafolio(id),
          titulo TEXT NOT NULL, descripcion TEXT NOT NULL, consentimiento TEXT NOT NULL,
          estado TEXT NOT NULL DEFAULT 'Borrador',
          reportes INTEGER NOT NULL DEFAULT 0 CHECK(reportes >= 0));
        CREATE TABLE IF NOT EXISTS pregunta (
          id INTEGER PRIMARY KEY, formulario INTEGER NOT NULL REFERENCES formulario(id) ON DELETE CASCADE,
          enunciado TEXT NOT NULL, tipo TEXT NOT NULL, orden INTEGER NOT NULL,
          obligatoria INTEGER NOT NULL, opciones TEXT NOT NULL);
        """)


def obtener(db, tabla, id):
    fila = db.execute(f'SELECT * FROM {tabla} WHERE id=?', (id,)).fetchone()
    if fila is None:
        raise Regla('El registro no existe.')
    return fila


def buscar_portafolios(db, texto):
    return db.execute("""
        SELECT p.*, COUNT(f.id) AS cantidad FROM portafolio p
        LEFT JOIN formulario f ON f.portafolio=p.id
        WHERE instr(lower(p.nombre), lower(?)) > 0 OR ?=''
        GROUP BY p.id ORDER BY p.nombre
    """, (texto, texto)).fetchall()


def formularios(db, portafolio, estado):
    return db.execute("""
        SELECT * FROM formulario WHERE portafolio=? AND (estado=? OR ?='')
        ORDER BY titulo
    """, (portafolio, estado, estado)).fetchall()


def preguntas(db, formulario):
    return db.execute('SELECT * FROM pregunta WHERE formulario=? ORDER BY orden,id',
                      (formulario,)).fetchall()


def validar_texto(valor, etiqueta, limite, *, obligatorio=True):
    valor = valor.strip()
    if obligatorio and not valor:
        raise Regla(f'{etiqueta} es un campo obligatorio.')
    if len(valor) > limite:
        raise Regla(f'{etiqueta} permite hasta {limite} caracteres.')
    return valor


def guardar_portafolio(db, id, datos):
    nombre = validar_texto(datos.get('nombre', ''), 'Nombre', 120)
    if any(row['nombre'].casefold() == nombre.casefold() and row['id'] != id
           for row in db.execute('SELECT id,nombre FROM portafolio')):
        raise Regla('Ya existe un portafolio con ese nombre.')
    descripcion = validar_texto(datos.get('descripcion', ''), 'Descripción', 1000, obligatorio=False)
    if id:
        obtener(db, 'portafolio', id)
        db.execute('UPDATE portafolio SET nombre=?, descripcion=? WHERE id=?',
                   (nombre, descripcion, id))
        return id
    return db.execute('INSERT INTO portafolio(nombre,descripcion) VALUES (?,?)',
                      (nombre, descripcion)).lastrowid


def eliminar_portafolio(db, id):
    obtener(db, 'portafolio', id)
    if formularios(db, id, ''):
        raise Regla('Solo se puede eliminar un portafolio vacío.')
    db.execute('DELETE FROM portafolio WHERE id=?', (id,))


def guardar_formulario(db, id, portafolio, datos):
    campos = (
        ('titulo', 'Título', 160),
        ('descripcion', 'Descripción', 1000),
        ('consentimiento', 'Consentimiento', 4000),
    )
    valores = tuple(validar_texto(datos.get(campo, ''), etiqueta, limite)
                    for campo, etiqueta, limite in campos)
    if id:
        obtener(db, 'formulario', id)
        db.execute('UPDATE formulario SET titulo=?,descripcion=?,consentimiento=? WHERE id=?',
                   (*valores, id))
        return id
    obtener(db, 'portafolio', portafolio)
    return db.execute('INSERT INTO formulario(portafolio,titulo,descripcion,consentimiento) VALUES (?,?,?,?)',
                      (portafolio, *valores)).lastrowid


def cambiar_estado(db, id, destino):
    formulario = obtener(db, 'formulario', id)
    if (formulario['estado'], destino) == ('Borrador', 'Publicado'):
        if not preguntas(db, id):
            raise Regla('Agrega al menos una pregunta antes de publicar.')
    elif (formulario['estado'], destino) != ('Publicado', 'Cerrado'):
        raise Regla('El cambio de estado solicitado no está permitido.')
    db.execute('UPDATE formulario SET estado=? WHERE id=?', (destino, id))


def eliminar_formulario(db, id):
    formulario = obtener(db, 'formulario', id)
    if formulario['reportes']:
        db.execute("UPDATE formulario SET estado='Cerrado' WHERE id=?", (id,))
        return 'El formulario tiene reportes y se cerró.'
    if formulario['estado'] != 'Borrador':
        raise Regla('Solo se pueden eliminar formularios en Borrador.')
    db.execute('DELETE FROM formulario WHERE id=?', (id,))
    return 'Formulario eliminado.'


def editable(db, id):
    if obtener(db, 'formulario', id)['estado'] != 'Borrador':
        raise Regla('Las preguntas solo se pueden cambiar en Borrador.')


def reordenar(db, ids):
    db.executemany('UPDATE pregunta SET orden=? WHERE id=?', enumerate(ids, 1))


def guardar_pregunta(db, id, formulario, datos):
    editable(db, formulario)
    enunciado = validar_texto(datos.get('enunciado', ''), 'Enunciado', 500)
    tipo = datos.get('tipo')
    if tipo not in TIPOS:
        raise Regla('Selecciona un tipo de pregunta válido.')
    opciones = [linea.strip() for linea in datos.get('opciones', '').splitlines() if linea.strip()]
    if tipo == TIPOS[0]:
        if len({opcion.casefold() for opcion in opciones}) < 2:
            raise Regla('Una pregunta de opción múltiple necesita al menos dos opciones distintas.')
        opciones = [validar_texto(opcion, 'Cada opción', 160) for opcion in opciones]
    else:
        opciones = []
    ids = [fila['id'] for fila in preguntas(db, formulario) if fila['id'] != id]
    try:
        orden = int(datos.get('orden', ''))
    except ValueError:
        raise Regla('El orden debe ser un número entero.') from None
    if not 1 <= orden <= len(ids) + 1:
        raise Regla(f'El orden debe estar entre 1 y {len(ids) + 1}.')
    valores = (enunciado, tipo, orden, int(datos.get('obligatoria') == '1'), json.dumps(opciones))
    if id:
        if obtener(db, 'pregunta', id)['formulario'] != formulario:
            raise Regla('La pregunta no pertenece al formulario.')
        db.execute('UPDATE pregunta SET enunciado=?,tipo=?,orden=?,obligatoria=?,opciones=? WHERE id=?',
                   (*valores, id))
    else:
        id = db.execute('INSERT INTO pregunta(formulario,enunciado,tipo,orden,obligatoria,opciones) VALUES (?,?,?,?,?,?)',
                        (formulario, *valores)).lastrowid
    ids.insert(orden - 1, id)
    reordenar(db, ids)


def eliminar_pregunta(db, id):
    pregunta = obtener(db, 'pregunta', id)
    editable(db, pregunta['formulario'])
    db.execute('DELETE FROM pregunta WHERE id=?', (id,))
    reordenar(db, [fila['id'] for fila in preguntas(db, pregunta['formulario'])])
