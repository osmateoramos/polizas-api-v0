# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** <número> · **Integrantes:** Oscar Mateo Ramos, Vanessa Acosta, Brayan David Barreto

> Tres defectos. Las cuatro secciones de cada uno son obligatorias y se parsean.
> El peso está en **«Cómo lo comprobamos»**, y la comprobación tiene una forma
> concreta: **una mutación**. Introduzcan a propósito un defecto en el servicio,
> muestren que el test original sigue en verde y que el corregido se pone en rojo,
> y vuelvan a dejar el servicio como estaba. Afirmar que un test es malo no vale;
> demostrar que no detecta nada, sí.

## Defecto 1

- **Qué está mal**: la batería dice aislar la base de datos con
  `app.dependency_overrides[get_db] = get_db`, pero `get_db` es una función
  **local** del propio archivo, distinta del objeto `database.get_db` que
  realmente usan las rutas (`Depends(get_db)` en `main.py`, importado de
  `database`). FastAPI solo activa un override cuando la llave del diccionario
  es el mismo objeto que la ruta pide por `Depends(...)`; como nunca coincide,
  el override no hace nada y la sesión real sigue siendo `database.get_db`
  sobre `app.db`, la base de desarrollo. Antes de correr la suite, `app.db`
  tenía 0 pólizas con prefijo `POL-IA-`; después de correrla una vez, tenía 7
  (una por cada póliza que crean los 6 tests). La batería no aísla nada: escribe
  en la base real.
- **Por qué es un defecto** (módulo · sección): M10 · 5. TestClient de FastAPI
- **Cómo lo comprobamos**: como la batería original corre sobre `app.db`, su
  resultado depende de lo que esa base ya tenga, no del código que se entrega.
  Para mostrarlo metimos un defecto que solo se ve en una base nueva: la
  migración inicial crea la tabla de predicciones con otro nombre. Sobre el
  `app.db` de desarrollo, migrado antes de la mutación, la tabla `predicciones`
  sigue ahí y la batería **original sigue en verde**. La **corregida** migra
  una base limpia, como lo hará el calificador, y **se pone en rojo**: `/score`
  no puede registrar la predicción y responde 500. Después se revirtió con
  `git checkout -- alembic/`.

```diff
--- a/alembic/versions/dece2037edb8_esquema_inicial_polizas_siniestros_y_.py
+++ b/alembic/versions/dece2037edb8_esquema_inicial_polizas_siniestros_y_.py
@@ -33,7 +33,7 @@ def upgrade() -> None:
     sa.PrimaryKeyConstraint('id'),
     sa.UniqueConstraint('numero')
     )
-    op.create_table('predicciones',
+    op.create_table('predicciones_mutada',
     sa.Column('id', sa.Integer(), nullable=False),
     sa.Column('poliza_id', sa.Integer(), nullable=False),
     sa.Column('puntaje', sa.Float(), nullable=False),
@@ -42,7 +42,7 @@ def upgrade() -> None:
     sa.ForeignKeyConstraint(['poliza_id'], ['polizas.id'], ondelete='CASCADE'),
     sa.PrimaryKeyConstraint('id')
     )
-    with op.batch_alter_table('predicciones', schema=None) as batch_op:
+    with op.batch_alter_table('predicciones_mutada', schema=None) as batch_op:
         batch_op.create_index(batch_op.f('ix_predicciones_poliza_id'), ['poliza_id'], unique=False)
 
     op.create_table('siniestros',
```

```
$ pytest ia_tests_propuesta.py -v
ia_tests_propuesta.py::test_crear_poliza_responde PASSED                 [ 16%]
ia_tests_propuesta.py::test_primas_variadas_son_aceptadas PASSED         [ 33%]
ia_tests_propuesta.py::test_consultar_poliza_inexistente PASSED          [ 50%]
ia_tests_propuesta.py::test_listar_polizas_no_falla PASSED               [ 66%]
ia_tests_propuesta.py::test_resumen_devuelve_lista PASSED                [ 83%]
ia_tests_propuesta.py::test_score_de_poliza_recien_creada PASSED         [100%]
======================== 6 passed, 1 warning in 9.44s =========================
```

```
$ pytest tests/test_ia_corregido.py -v
...
tests/test_ia_corregido.py::test_score_de_poliza_recien_creada FAILED    [ 92%]
...
>       assert r.status_code == 200
E       assert 500 == 200
E        +  where 500 = <Response [500 Internal Server Error]>.status_code
================== 1 failed, 13 passed, 1 warning in 26.80s ===================
```

  Comprobación complementaria: con `database.get_db` mutado para que lance
  `RuntimeError`, la original se cae entera (6 failed) y la corregida sigue en
  verde. Eso confirma que la original usa la sesión real aunque diga que la
  sustituye.

- **Corrección**: `tests/test_ia_corregido.py` sigue el mismo patrón que
  `tests/test_contrato.py`: pone `DATABASE_URL` en una base temporal **antes**
  de importar `main`, aplica `alembic upgrade head` sobre ella, y la fixture
  `_aislar` hace `app.dependency_overrides[database.get_db] = _get_db` — la
  llave es la dependencia real, no una función local sin uso.

## Defecto 2

- **Qué está mal**: varios asserts aceptan tanto el resultado correcto como el
  roto, así que no pueden fallar aunque el servicio tenga un bug:
  `test_crear_poliza_responde` acepta `(200, 201, 422)`,
  `test_consultar_poliza_inexistente` acepta `(200, 404)` —un recurso
  inexistente que responde 200 sería un bug grave, y el test lo deja pasar—, y
  `test_listar_polizas_no_falla` solo exige `< 500`. `test_primas_variadas_son_aceptadas`
  tiene el mismo problema disfrazado: su nombre promete que las primas se
  aceptan, pero como `422` está en la tupla, el test pasaría igual aunque el
  servicio rechazara las cinco.
- **Por qué es un defecto** (módulo · sección): M10 · 4. Framework pytest
- **Cómo lo comprobamos**: quitamos el `404` de `/polizas/{id}` cuando la
  póliza no existe —uno de los ejemplos que da el propio enunciado— y lo
  cambiamos por `200`.

```diff
--- a/main.py
+++ b/main.py
@@ -29,7 +29,8 @@ def poliza_o_404(id_poliza: int, db: Session = Depends(get_db)) -> Poliza:
     poliza = crud.obtener_poliza(db, id_poliza)
     if poliza is None:
-        raise HTTPException(status_code=404, detail=f"no existe la póliza {id_poliza}")
+        # MUTACIÓN DICTAMEN_IA defecto 2: el 404 deja de devolverse.
+        raise HTTPException(status_code=200, detail=f"no existe la póliza {id_poliza}")
     return poliza
```

```
$ pytest ia_tests_propuesta.py -v
ia_tests_propuesta.py::test_crear_poliza_responde PASSED
ia_tests_propuesta.py::test_primas_variadas_son_aceptadas PASSED
ia_tests_propuesta.py::test_consultar_poliza_inexistente PASSED
ia_tests_propuesta.py::test_listar_polizas_no_falla PASSED
ia_tests_propuesta.py::test_resumen_devuelve_lista PASSED
ia_tests_propuesta.py::test_score_de_poliza_recien_creada PASSED
======================== 6 passed, 1 warning in 8.56s =========================
```

```
$ pytest tests/test_ia_corregido.py -v
...
tests/test_ia_corregido.py::test_poliza_inexistente_da_404 FAILED
...
    def test_poliza_inexistente_da_404():
>       assert cliente.get("/polizas/999999").status_code == 404
E       AssertionError: assert 200 == 404
================== 1 failed, 13 passed, 1 warning in 28.58s ===================
```

- **Corrección**: cada test corregido exige el único código correcto para su
  caso: `test_poliza_inexistente_da_404` exige `== 404` (no admite 200),
  `test_crear_poliza_devuelve_201` exige `== 201`, `test_listar_polizas_responde_200`
  exige `== 200`, y `test_primas_variadas_son_realmente_aceptadas` exige `== 201`
  en las cinco vueltas —si una sola prima válida fuera rechazada, el test lo nota—.
  Añadimos además `test_prima_no_positiva_da_422`, un caso negativo dedicado que
  el archivo de la IA no tenía.

  Un código correcto en la respuesta tampoco basta si nadie comprueba lo que
  quedó guardado. Por eso la batería corregida también lee de vuelta lo que
  escribe: la póliza creada (`test_poliza_creada_se_lee_de_vuelta`), el
  siniestro declarado (`test_siniestro_declarado_queda_guardado`), el cambio de
  un PUT parcial (`test_put_parcial_queda_guardado`) y la predicción en
  `/predicciones` tras `/score`. También exige los 422 de los validadores
  (`test_fechas_invertidas_dan_422`,
  `test_siniestro_con_monto_no_positivo_da_422`, `test_put_invalido_da_422`) y
  el 404 en `PUT` y en `POST /polizas/{id}/siniestros`. Lo comprobamos con ocho
  mutaciones más: quitar el commit de la predicción y pasar a `flush` el de
  crear, el del PUT y el del siniestro; un `model_validator` de fechas que no
  lanza; un `monto` sin `gt=0`; un PUT que acepta `null`; y `poliza_o_404` sin
  404. La batería original de la IA sigue en verde (6 passed) con siete de ellas.
  Solo detecta la de crear, porque su test de `/score` busca la póliza en otra
  petición. La corregida pone al menos un test en rojo con las ocho.

## Defecto 3

- **Qué está mal**: el número de póliza se genera al azar
  (`f"POL-IA-{uuid.uuid4().hex[:6].upper()}"`, unas 16 millones de
  combinaciones) sin comprobar que no exista ya. Combinado con el defecto 1
  —los datos se acumulan en la base real entre corridas, para siempre—, la
  probabilidad de una colisión no es cero: el día que ocurra, `crear_poliza`
  responde `409`, un código que ninguno de los asserts de la batería admite, y
  el mismo test que venía pasando empieza a fallar sin que el servicio haya
  cambiado. Es un test cuyo resultado depende del azar entre una corrida y
  otra, no del comportamiento del servicio.
- **Por qué es un defecto** (módulo · sección): M10 · 6. Fixtures en pytest
- **Cómo lo comprobamos**: en vez de esperar a que el azar produzca una
  colisión real (con 16 millones de combinaciones, tomaría miles de corridas),
  mutamos el servicio para que el caso de número duplicado —que la IA nunca
  prueba— deje de avisar: en lugar de `409`, devuelve la póliza existente como
  si la hubiera creado.

```diff
--- a/crud.py
+++ b/crud.py
@@ -30,11 +30,10 @@ def crear_poliza(db: Session, datos: PolizaEntrada, secreto_firma: str) -> Poliz
     db.add(poliza)
     try:
         db.commit()
-    except IntegrityError as error:
-        # Sin rollback la sesión queda inservible; es de esta petición, pero se
-        # deja limpia de todos modos antes de avisar del conflicto.
+    except IntegrityError:
+        # MUTACIÓN DICTAMEN_IA defecto 3: el duplicado deja de avisar.
         db.rollback()
-        raise NumeroDuplicado(datos.numero) from error
+        return obtener_poliza_por_numero(db, datos.numero)
     db.refresh(poliza)
     return poliza
```

```
$ pytest ia_tests_propuesta.py -v
ia_tests_propuesta.py::test_crear_poliza_responde PASSED
ia_tests_propuesta.py::test_primas_variadas_son_aceptadas PASSED
ia_tests_propuesta.py::test_consultar_poliza_inexistente PASSED
ia_tests_propuesta.py::test_listar_polizas_no_falla PASSED
ia_tests_propuesta.py::test_resumen_devuelve_lista PASSED
ia_tests_propuesta.py::test_score_de_poliza_recien_creada PASSED
======================== 6 passed, 1 warning in 8.21s =========================
```

```
$ pytest tests/test_ia_corregido.py -v
...
tests/test_ia_corregido.py::test_numero_duplicado_da_409_y_el_servicio_sigue_vivo FAILED
...
        r = cliente.post("/polizas", json=datos)
>       assert r.status_code == 409, f"devolvió {r.status_code}"
E       AssertionError: devolvió 201
================== 1 failed, 13 passed, 1 warning in 35.73s ===================
```

- **Corrección**: `test_numero_duplicado_da_409_y_el_servicio_sigue_vivo` prueba
  el caso directo, sin esperar al azar: crea una póliza, la vuelve a crear con
  el mismo número, y exige `409` en la segunda —más, de regalo, que el servicio
  siga respondiendo después del conflicto, igual que el último test de
  `tests/test_contrato.py`—. Así el defecto se detecta siempre, no solo el día
  que el azar produzca una colisión.
