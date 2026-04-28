# Mi Bitácora Pro

App de escritorio para registrar actividades diarias con seguimiento de gastos en pesos chilenos (CLP). Construida con Flet (Python) y PostgreSQL.

## Requisitos

- Python 3.10+
- PostgreSQL instalado y corriendo
- Dependencias Python:

```bash
pip install flet psycopg2-binary
```

## Configuración de la base de datos

1. Instalar PostgreSQL (Arch Linux):
```bash
sudo pacman -S postgresql
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

2. Crear la base de datos:
```bash
sudo -u postgres psql -c "CREATE DATABASE bitacora;"
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'tu_contraseña';"
```

3. Editar las credenciales en `main.py`:
```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "bitacora",
    "user":     "postgres",
    "password": "tu_contraseña",
}
```

## Uso

```bash
python main.py
```

## Funcionalidades

- Registro de actividades con detección automática de montos en CLP (soporta `5k`, `mil`, `lucas`, `$5000`)
- Categorías: Gimnasio, Comida, Gastos, General
- Campo extra de nombre de comida al seleccionar la categoría Comida
- Balance total en tiempo real
- Filtrado de registros por categoría

## Estructura de la base de datos

Tabla `registros`:

| Columna   | Tipo    | Descripción                        |
|-----------|---------|------------------------------------|
| id        | SERIAL  | Clave primaria autoincremental     |
| fecha     | TEXT    | Fecha y hora (dd/mm/yyyy HH:MM)    |
| texto     | TEXT    | Descripción de la actividad        |
| monto     | INTEGER | Monto en CLP (negativo = gasto)    |
| categoria | TEXT    | Gimnasio / Comida / Gastos / General |
| comida    | TEXT    | Nombre del plato (solo en Comida)  |
