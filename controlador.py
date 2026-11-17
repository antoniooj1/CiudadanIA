import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import modelo as m
import vista as v


def campos(cadena):
    return {campo: valores[-1] for campo, valores in parse_qs(cadena, keep_blank_values=True).items()}


def seleccionar(db, ruta, query):
    if ruta == '/':
        q = query.get('q', '').strip()
        return ('Portafolios', v.lista_portafolios(m.buscar_portafolios(db, q), q), None)
    if ruta == '/p/nuevo':
        return ('Crear portafolio', v.formulario_portafolio(ruta, {}), '/')
    match = re.fullmatch(r'/(p|f|q)/(\d+)(?:/([a-z]+))?', ruta)
    if not match:
        raise m.Regla('Página no encontrada.')
    entidad, id, accion = match.groups()
    id = int(id)
    if entidad == 'p':
        p = m.obtener(db, 'portafolio', id)
        raiz = f'/p/{id}'
        if accion == 'editar':
            return ('Editar portafolio', v.formulario_portafolio(ruta, dict(p)), raiz)
        if accion == 'eliminar':
            return ('Eliminar portafolio', v.confirmar(ruta, raiz, f'¿Eliminar «{p["nombre"]}»?'), raiz)
        if accion == 'formulario':
            return ('Crear formulario', v.formulario_formulario(ruta, {}), raiz)
        if accion is None:
            estado = query.get('estado', '')
            return (p['nombre'], v.ficha_portafolio(p, m.formularios(db, id, estado), estado), '/')
    if entidad == 'f':
        f = m.obtener(db, 'formulario', id)
        raiz = f'/f/{id}'
        if accion == 'editar':
            return ('Editar formulario', v.formulario_formulario(ruta, dict(f)), raiz)
        if accion == 'eliminar':
            texto = (f'«{f["titulo"]}» tiene reportes. ¿Cerrar el formulario?' if f['reportes']
                     else f'¿Eliminar «{f["titulo"]}» y sus preguntas?')
            return ('Eliminar formulario', v.confirmar(ruta, raiz, texto), raiz)
        if accion == 'pregunta':
            m.editable(db, id)
            return ('Agregar pregunta', v.formulario_pregunta(ruta, {'orden': len(m.preguntas(db, id)) + 1}), raiz)
        if accion in (None, 'publicar', 'cerrar'):
            return (f['titulo'], v.ficha_formulario(f, m.preguntas(db, id)), f'/p/{f["portafolio"]}')
    if entidad == 'q':
        q = m.obtener(db, 'pregunta', id)
        raiz = f'/f/{q["formulario"]}'
        m.editable(db, q['formulario'])
        if accion == 'editar':
            valores = dict(q)
            valores['opciones'] = '\n'.join(json.loads(valores['opciones']))
            return ('Editar pregunta', v.formulario_pregunta(ruta, valores), raiz)
        if accion == 'eliminar':
            return ('Eliminar pregunta', v.confirmar(ruta, raiz, f'¿Eliminar «{q["enunciado"]}»?'), raiz)
    raise m.Regla('Página no encontrada.')


def guardar(db, ruta, datos):
    if ruta == '/p/nuevo':
        return f'/p/{m.guardar_portafolio(db, None, datos)}', 'Portafolio creado.'
    match = re.fullmatch(r'/(p|f|q)/(\d+)/([a-z]+)', ruta)
    if not match:
        raise m.Regla('Acción no encontrada.')
    entidad, id, accion = match.groups()
    id = int(id)
    if entidad == 'p':
        if accion == 'editar':
            m.guardar_portafolio(db, id, datos)
            return f'/p/{id}', 'Portafolio actualizado.'
        if accion == 'eliminar':
            m.eliminar_portafolio(db, id)
            return '/', 'Portafolio eliminado.'
        if accion == 'formulario':
            nuevo = m.guardar_formulario(db, None, id, datos)
            return f'/f/{nuevo}', 'Formulario creado en Borrador.'
    if entidad == 'f':
        f = m.obtener(db, 'formulario', id)
        if accion == 'editar':
            m.guardar_formulario(db, id, None, datos)
            return f'/f/{id}', 'Formulario actualizado.'
        if accion == 'eliminar':
            aviso = m.eliminar_formulario(db, id)
            return (f'/f/{id}' if f['reportes'] else f'/p/{f["portafolio"]}'), aviso
        if accion in ('publicar', 'cerrar'):
            destino = 'Publicado' if accion == 'publicar' else 'Cerrado'
            m.cambiar_estado(db, id, destino)
            return f'/f/{id}', f'Formulario {destino.lower()}.'
        if accion == 'pregunta':
            m.guardar_pregunta(db, None, id, datos)
            return f'/f/{id}', 'Pregunta agregada.'
    if entidad == 'q':
        q = m.obtener(db, 'pregunta', id)
        if accion == 'editar':
            m.guardar_pregunta(db, id, q['formulario'], datos)
            return f'/f/{q["formulario"]}', 'Pregunta actualizada.'
        if accion == 'eliminar':
            m.eliminar_pregunta(db, id)
            return f'/f/{q["formulario"]}', 'Pregunta eliminada.'
    raise m.Regla('Acción no encontrada.')


class Aplicacion(BaseHTTPRequestHandler):
    def enviar(self, cuerpo, estado=200, tipo='text/html; charset=utf-8'):
        contenido = cuerpo.encode('utf-8')
        self.send_response(estado)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/estilo.css':
            css = Path(__file__).with_name('estilo.css').read_text(encoding='utf-8')
            self.enviar(css, tipo='text/css; charset=utf-8')
            return
        query = campos(url.query)
        try:
            with m.conexion() as db:
                pagina = seleccionar(db, url.path, query)
            self.enviar(v.pagina(*pagina, aviso=query.get('aviso', '')))
        except m.Regla as error:
            self.enviar(v.pagina('Página no disponible', '', '/', error=str(error)), 404)

    def do_POST(self):
        ruta = urlsplit(self.path).path
        longitud = int(self.headers.get('Content-Length', '0'))
        if longitud > 1_000_000:
            self.enviar(v.pagina('Solicitud demasiado grande', '', '/'), 413)
            return
        datos = campos(self.rfile.read(longitud).decode('utf-8', errors='replace'))
        try:
            with m.conexion() as db:
                db.execute('BEGIN IMMEDIATE')
                destino, aviso = guardar(db, ruta, datos)
        except m.Regla as error:
            with m.conexion() as db:
                try:
                    titulo, cuerpo, volver = seleccionar(db, ruta, {})
                except m.Regla:
                    titulo, cuerpo, volver = 'Acción rechazada', '', '/'
            if titulo in ('Crear portafolio', 'Editar portafolio'):
                cuerpo = v.formulario_portafolio(ruta, datos)
            if titulo in ('Crear formulario', 'Editar formulario'):
                cuerpo = v.formulario_formulario(ruta, datos)
            if titulo in ('Agregar pregunta', 'Editar pregunta'):
                cuerpo = v.formulario_pregunta(ruta, datos)
            self.enviar(v.pagina(titulo, cuerpo, volver, error=str(error)), 422)
            return
        self.send_response(303)
        self.send_header('Location', destino + '?' + urlencode({'aviso': aviso}))
        self.end_headers()


if __name__ == '__main__':
    m.iniciar()
    print('Abre http://127.0.0.1:8000 en el navegador.', flush=True)
    with HTTPServer(('127.0.0.1', 8000), Aplicacion) as servidor:
        servidor.serve_forever()
