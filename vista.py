import json
from html import escape

import modelo


def e(valor):
    return escape(str(valor), quote=True)


def enlace(url, texto):
    return f'<a href="{e(url)}">{e(texto)}</a>'


def accion(url, texto):
    return f'<form method="post" action="{e(url)}"><button>{e(texto)}</button></form>'


def campo(nombre, etiqueta, valores, largo=False):
    valor = e(valores.get(nombre, ''))
    control = (f'<textarea name="{nombre}" rows="3">{valor}</textarea>' if largo
               else f'<input name="{nombre}" value="{valor}">')
    return f'<label>{etiqueta}{control}</label>'


def selector(nombre, etiqueta, opciones, valor):
    items = ''.join(f'<option value="{e(v)}" {"selected" if v == valor else ""}>{e(t)}</option>'
                    for v, t in opciones)
    return f'<label>{etiqueta}<select name="{nombre}">{items}</select></label>'


def editar(url, contenido):
    return f'<form class="editor" method="post" action="{e(url)}">{contenido}<button>Guardar</button></form>'


def pagina(titulo, cuerpo, volver=None, aviso='', error=''):
    regreso = enlace(volver, '← Volver') if volver else ''
    mensaje = (f'<p class="error" role="alert">{e(error)}</p>' if error else
               f'<p class="aviso" role="status">{e(aviso)}</p>' if aviso else '')
    return f'''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)} · CiudadanIA</title><link rel="stylesheet" href="/estilo.css">
<header><div>{enlace('/', 'CiudadanIA')}<span>Investigador simulado</span></div></header>
<main>{regreso}<h1>{e(titulo)}</h1>{mensaje}{cuerpo}</main></html>'''


def lista_portafolios(filas, busqueda):
    lista = ''.join(f'<li>{enlace("/p/" + str(p["id"]), p["nombre"])}'
                    f'<span>{p["cantidad"]} formulario(s)</span></li>' for p in filas)
    busqueda_html = campo('q', 'Buscar por nombre', {'q': busqueda})
    resultados = f'<ul>{lista}</ul>' if lista else '<p>No hay portafolios que coincidan.</p>'
    return (f'<form class="barra" method="get">{busqueda_html}<button>Buscar</button></form>'
            f'<p>{enlace("/p/nuevo", "Crear portafolio")}</p>{resultados}')


def ficha_portafolio(p, filas, estado):
    url = f'/p/{p["id"]}'
    estados = [('', 'Todos'), *((s, s) for s in ('Borrador', 'Publicado', 'Cerrado'))]
    filtro = selector('estado', 'Filtrar por estado', estados, estado)
    lista = ''.join(f'<li>{enlace("/f/" + str(f["id"]), f["titulo"])}<span>{e(f["estado"])}</span></li>'
                    for f in filas)
    return (f'<p>{e(p["descripcion"])}</p><p>Creado el {e(p["creado"])}</p>'
            f'<nav>{enlace(url + "/editar", "Editar portafolio")} '
            f'{enlace(url + "/eliminar", "Eliminar portafolio")} '
            f'{enlace(url + "/formulario", "Crear formulario")}</nav>'
            f'<h2>Formularios</h2><form class="barra">{filtro}<button>Filtrar</button></form>'
            + (f'<ul>{lista}</ul>' if lista else '<p>No hay formularios que coincidan.</p>'))


def ficha_formulario(f, filas):
    url = f'/f/{f["id"]}'
    borrador = f['estado'] == 'Borrador'
    acciones = enlace(url + '/editar', 'Editar formulario')
    if borrador or (f['reportes'] and f['estado'] != 'Cerrado'):
        acciones += enlace(url + '/eliminar', 'Eliminar formulario')
    if borrador:
        acciones += enlace(url + '/pregunta', 'Agregar pregunta')
        acciones += accion(url + '/publicar', 'Publicar')
    elif f['estado'] == 'Publicado':
        acciones += accion(url + '/cerrar', 'Cerrar')
    lista = []
    for q in filas:
        detalle = f'{e(q["tipo"])} · {"Obligatoria" if q["obligatoria"] else "Opcional"}'
        opciones = json.loads(q['opciones'])
        if opciones:
            detalle += ' · ' + e(', '.join(opciones))
        cambios = ''
        if borrador:
            cambios = (enlace(f'/q/{q["id"]}/editar', 'Editar') + ' ' +
                       enlace(f'/q/{q["id"]}/eliminar', 'Eliminar'))
        lista.append(f'<li><div><strong>{q["orden"]}. {e(q["enunciado"])}</strong>'
                     f'<div>{detalle}</div></div><div>{cambios}</div></li>')
    return (f'<p class="estado">{e(f["estado"])}</p><p>{e(f["descripcion"])}</p>'
            f'<h2>Consentimiento informado</h2><p>{e(f["consentimiento"])}</p>'
            f'<nav>{acciones}</nav><h2>Preguntas</h2>'
            + ('<ul>' + ''.join(lista) + '</ul>' if lista else '<p>Aún no hay preguntas.</p>'))


def formulario_portafolio(url, valores):
    return editar(url, campo('nombre', 'Nombre', valores) +
                  campo('descripcion', 'Descripción', valores, True))


def formulario_formulario(url, valores):
    return editar(url, campo('titulo', 'Título', valores) +
                  campo('descripcion', 'Descripción', valores, True) +
                  campo('consentimiento', 'Consentimiento informado', valores, True))


def formulario_pregunta(url, valores):
    tipos = [(tipo, tipo) for tipo in modelo.TIPOS]
    return editar(url, campo('enunciado', 'Enunciado', valores) +
                  selector('tipo', 'Tipo', tipos, valores.get('tipo', 'Texto')) +
                  campo('orden', 'Posición', valores) +
                  selector('obligatoria', 'Obligatoria', [('0', 'No'), ('1', 'Sí')],
                           str(valores.get('obligatoria', 0))) +
                  campo('opciones', 'Opciones (una por línea, para opción múltiple)', valores, True))


def confirmar(url, volver, texto):
    return f'<p>{e(texto)}</p><nav>{accion(url, "Confirmar")}{enlace(volver, "Cancelar")}</nav>'
