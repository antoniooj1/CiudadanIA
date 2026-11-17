# CiudadanIA — Gestión de Formularios

Requiere Python 3. No necesita bibliotecas adicionales. Desde esta carpeta:

```sh
python3 controlador.py
```

Abre http://127.0.0.1:8000. En Windows también puedes usar `py controlador.py`. Cierra con Ctrl+C. La base SQLite se crea al iniciar y conserva los datos.

- `modelo.py` administra la persistencia y valida las reglas.
- `vista.py` y `estilo.css` generan la interfaz.
- `controlador.py` recibe solicitudes y coordina el modelo y la vista.

La aplicación local simula al investigador. El campo `reportes` de cada formulario se reserva para el módulo de reportes y empieza en cero. La regla de cierre al intentar eliminar un formulario que tiene reportes está implementada en el modelo.

## RNF03 e integridad de datos

El modelo controla los campos obligatorios, la unicidad del nombre, las opciones y las transiciones de estado. El proyecto fija los siguientes máximos en caracteres: nombre 120, título 160, descripción 1 000, consentimiento 4 000, enunciado 500 y cada opción 160.
