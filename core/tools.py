# core/tools.py — versión corregida con SQL seguro + RAG de leyes robusto
from langchain_core.tools import tool

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Si los usás en otra parte, podés reimportarlos; aquí los quito para limpiar dependencias no usadas
# from core.sql_agent import crear_agente_sql
from core.vectorizer import cargar_vectorstore
# from utils.excel_analyzer import cargar_excel
from core.mcp_runner import ejecutar_mcp

# ──────────────────────────────────────────────────────────────────────────────
# Carga .env
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# DB helpers (Postgres)
# ──────────────────────────────────────────────────────────────────────────────

# Helper: arma el where mínimo válido para Chroma (sin $and cuando hay 0/1 cláusulas)
def _where_minimal(**kv):
    conds = []
    for k, v in kv.items():
        if v is None:
            continue
        conds.append({k: {"$eq": v}})
    if not conds:
        return {}          # sin filtro
    if len(conds) == 1:
        return conds[0]    # una sola condición, sin $and
    return {"$and": conds} # 2+ condiciones -> $and

def _open_raw_collection():
    """
    Abre la colección Chroma *nativa* por nombre, sin pasar metadata extra.
    Evita el mismatch del wrapper de LangChain.
    """
    client = chromadb.PersistentClient(path=str(PERSIST_DIR), settings=CHROMA_SETTINGS)
    return client.get_or_create_collection(COLLECTION_NAME)

def _embed_query_vec(text: str) -> List[float]:
    """
    Embebe una consulta con el mismo embedder del indexado.
    """
    emb = _build_embedder()
    # CacheBackedEmbeddings / OpenAIEmbeddings usan .embed_query
    if hasattr(emb, "embed_query"):
        return emb.embed_query(text)
    # Fallback
    if hasattr(emb, "embed_documents"):
        return emb.embed_documents([text])[0]
    raise RuntimeError("No se pudo construir el embedder para consultas.")


def _db_config() -> Dict[str, str]:
    """Lee credenciales de la DB desde .env."""
    return {
        "dbname":   os.getenv("DB_NAME", "conocimiento_ia"),
        "user":     os.getenv("DB_USER", "lecaracciolo"),
        "password": os.getenv("DB_PASSWORD", "200797"),
        "host":     os.getenv("DB_HOST", "localhost"),
        "port":     os.getenv("DB_PORT", "5432"),
    }

def _tabla_nombre(workspace: str) -> str:
    """
    Normaliza el nombre de tabla a 'facturas_{workspace}' y restringe caracteres para evitar inyección.
    """
    base = f"facturas_{(workspace or '').lower()}"
    # permitir solo a-z, 0-9 y _
    seguro = re.sub(r"[^a-z0-9_]", "_", base)
    return seguro

def _execute_pg(query: Any, params: tuple | None = None) -> str:
    """
    Ejecuta una consulta (string o psycopg2.sql.Composable) y devuelve JSON (lista de objetos).
    """
    try:
        cfg = _db_config()
        dsn = f"dbname='{cfg['dbname']}' user='{cfg['user']}' password='{cfg['password']}' host='{cfg['host']}' port='{cfg['port']}'"
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                try:
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                    out = [dict(zip(cols, r)) for r in rows] if cols else rows
                    return json.dumps(out, ensure_ascii=False, default=str)
                except psycopg2.ProgrammingError:
                    # No hay resultados (p. ej., DDL/DML sin RETURNING)
                    return json.dumps({"ok": True}, ensure_ascii=False)
    except Exception as e:
        return f"Error al ejecutar la consulta: {e}"

# ──────────────────────────────────────────────────────────────────────────────
# Herramientas SQL / Facturas
# ──────────────────────────────────────────────────────────────────────────────
# tools_facturas.py
# Herramientas de consulta para LangGraph / LangChain sobre afip.*
# Requiere: pip install psycopg2-binary

import os
import json
import psycopg2
import psycopg2.extras
from datetime import date
from langchain.tools import tool
from urllib.parse import urlparse, parse_qs, unquote

AFIP_VIEW = "afip.facturas_flat"
T_FACTURA = "afip.factura"
T_CONTRIB = "afip.contribuyente"
T_IVA    = "afip.factura_iva"
T_PERCP  = "afip.factura_percepcion"
T_ITEM   = "afip.factura_item"

# ---------------------- Helpers ----------------------

def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definido en el entorno.")

    # Si ya es un DSN tipo "host=... dbname=...", úsalo directo
    if "://" not in url:
        return psycopg2.connect(url)

    # Parsear URL estilo SQLAlchemy
    p = urlparse(url)
    if not p.scheme.startswith("postgres"):
        raise RuntimeError(f"Esquema no soportado en DATABASE_URL: {p.scheme}")

    params = {
        "dbname": (p.path or "").lstrip("/") or None,
        "user": unquote(p.username) if p.username else None,
        "password": unquote(p.password) if p.password else None,
        "host": p.hostname or "localhost",
        "port": p.port or 5432,
    }
    # Query string (e.g., ?sslmode=require)
    qparams = {k: v[0] for k, v in parse_qs(p.query).items()}
    params.update(qparams)

    return psycopg2.connect(**{k: v for k, v in params.items() if v is not None})

def _execute(query: str, params: tuple | dict = ()):
    """Ejecuta SQL y devuelve JSON (lista de filas) o {'ok': True} si no hay resultset."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description is None:
                return json.dumps({"ok": True})
            rows = cur.fetchall()
            return json.dumps(rows, default=str)

def _execute_one(query: str, params: tuple = ()):
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            val = cur.fetchone()
            return json.dumps(val[0] if val else None, default=str)

def _limit(n: int | None, default: int = 5, maxn: int = 100):
    if not n or n <= 0:
        return default
    return min(n, maxn)

# ---------------------- TOOLS (Vista: afip.facturas_flat) ----------------------

@tool
def listar_facturas_por_cuit_emisor(cuit_emisor: str, limit: int = 5, workspace: str = "") -> str:
    """
    Últimas N facturas por CUIT emisor.
    Úsalo para: "mostrame facturas del CUIT 30-XXXX".
    """
    q = f"""
        SELECT
          id, fecha_emision, tipo_comprobante, letra_comprobante, punto_venta, numero_factura,
          razon_social_emisor, importe_total, moneda, emisor_mail
        FROM {AFIP_VIEW}
        WHERE cuit_emisor = %s
        ORDER BY fecha_emision DESC, id DESC
        LIMIT %s;
    """
    return _execute(q, (cuit_emisor, _limit(limit)))

@tool
def listar_facturas_por_cuit_receptor(cuit_receptor: str, limit: int = 5, workspace: str = "") -> str:
    """
    Últimas N facturas recibidas por CUIT receptor.
    """
    q = f"""
        SELECT
          id, fecha_emision, tipo_comprobante, letra_comprobante, punto_venta, numero_factura,
          razon_social_receptor, importe_total, moneda, emisor_mail
        FROM {AFIP_VIEW}
        WHERE cuit_receptor = %s
        ORDER BY fecha_emision DESC, id DESC
        LIMIT %s;
    """
    return _execute(q, (cuit_receptor, _limit(limit)))

@tool
def listar_facturas_por_email_remitente(email: str, limit: int = 10, workspace: str = "") -> str:
    """
    Facturas cuyo correo remitente (del e-mail) sea el indicado. Ordena por fecha de recepción desc.
    Útil cuando querés ver todo lo que mandó cierto remitente.
    """
    q = f"""
        SELECT
          id, fecha_recepcion, file_name, fecha_emision, tipo_comprobante, letra_comprobante,
          punto_venta, numero_factura, razon_social_emisor, razon_social_receptor,
          importe_total, moneda, emisor_mail
        FROM {AFIP_VIEW}
        WHERE emisor_mail = %s
        ORDER BY fecha_recepcion DESC, id DESC
        LIMIT %s;
    """
    return _execute(q, (email, _limit(limit, default=10)))

@tool
def buscar_por_numero_factura(punto_venta: int, numero_factura: int, cuit_emisor: str = "", workspace: str = "") -> str:
    """
    Busca una factura por PV y Nro. (opcionalmente por CUIT emisor) y devuelve TODAS las coincidencias (incluye duplicados).
    Útil para confirmar duplicados.
    """
    if cuit_emisor:
        q = f"""
            SELECT *
            FROM {AFIP_VIEW}
            WHERE punto_venta = %s AND numero_factura = %s AND cuit_emisor = %s
            ORDER BY fecha_recepcion DESC, id DESC;
        """
        return _execute(q, (punto_venta, numero_factura, cuit_emisor))
    else:
        q = f"""
            SELECT *
            FROM {AFIP_VIEW}
            WHERE punto_venta = %s AND numero_factura = %s
            ORDER BY fecha_recepcion DESC, id DESC;
        """
        return _execute(q, (punto_venta, numero_factura))

@tool
def contar_duplicados_por_clave_natural(limit: int = 100) -> str:
    """
    Lista todas las filas de facturas que tienen una clave natural duplicada.
    La clave es (emisor_id, cod, letra, PV, número).
    Muestra todos los campos de cada factura duplicada.
    """
    q = f"""
        WITH Duplicados AS (
            SELECT
                emisor_id, codigo_comprobante, letra_comprobante, punto_venta, numero_factura,
                COUNT(*) AS repeticiones
            FROM {T_FACTURA}
            GROUP BY 1,2,3,4,5
            HAVING COUNT(*) > 1
        )
        SELECT f.*,
            d.repeticiones
        FROM {T_FACTURA} f
        JOIN Duplicados d ON
            f.punto_venta = d.punto_venta AND
            f.numero_factura = d.numero_factura
        ORDER BY f.emisor_id, f.numero_factura, f.id
        LIMIT %s;
    """
    return _execute(q, (_limit(limit, default=100, maxn=1000),))

@tool
def buscar_por_cae(cae_numero: str, workspace: str = "") -> str:
    """
    Busca facturas por número de CAE exacto.
    """
    q = f"""
        SELECT id, fecha_emision, tipo_comprobante, letra_comprobante, punto_venta, numero_factura,
               cuit_emisor, razon_social_emisor, importe_total, cae_numero, cae_fecha_vto
        FROM {AFIP_VIEW}
        WHERE cae_numero = %s
        ORDER BY fecha_emision DESC, id DESC;
    """
    return _execute(q, (cae_numero,))

@tool
def total_facturado_por_emisor_y_mes(cuit_emisor: str, desde: str, hasta: str, workspace: str = "") -> str:
    """
    Suma de importe_total por mes para un CUIT emisor entre fechas (YYYY-MM-DD).
    """
    q = f"""
        SELECT
          date_trunc('month', fecha_emision)::date AS mes,
          SUM(importe_total) AS total_mensual
        FROM {AFIP_VIEW}
        WHERE cuit_emisor = %s
          AND fecha_emision >= %s::date AND fecha_emision <= %s::date
        GROUP BY 1
        ORDER BY 1;
    """
    return _execute(q, (cuit_emisor, desde, hasta))

@tool
def kpis_resumen(desde: str, hasta: str, workspace: str = "") -> str:
    """
    KPIs básicos entre fechas: cantidad, suma neto gravado, IVA total, total, y promedio ticket.
    """
    q = f"""
        SELECT
          COUNT(*)                           AS cantidad,
          COALESCE(SUM(importe_neto_gravado), 0) AS neto_gravado,
          COALESCE(SUM(iva_total), 0)            AS iva_total,
          COALESCE(SUM(importe_total), 0)        AS total,
          CASE WHEN COUNT(*)>0 THEN AVG(importe_total) ELSE 0 END AS ticket_promedio
        FROM {AFIP_VIEW}
        WHERE fecha_emision >= %s::date AND fecha_emision <= %s::date;
    """
    return _execute(q, (desde, hasta))

@tool
def top_emisores_por_monto(desde: str, hasta: str, limit: int = 10, workspace: str = "") -> str:
    """
    Top N emisores por importe_total entre fechas.
    """
    q = f"""
        SELECT
          cuit_emisor, razon_social_emisor,
          COUNT(*) AS cantidad, SUM(importe_total) AS total
        FROM {AFIP_VIEW}
        WHERE fecha_emision >= %s::date AND fecha_emision <= %s::date
        GROUP BY 1,2
        ORDER BY total DESC
        LIMIT %s;
    """
    return _execute(q, (desde, hasta, _limit(limit, default=10)))

@tool
def facturas_por_condicion_venta(condicion: str, desde: str = None, hasta: str = None, limit: int = 50, workspace: str = "") -> str:
    """
    Facturas filtradas por condición de venta (e.g., 'Contado', '30 Días', etc.) y rango opcional.
    """
    base = f"""
        SELECT id, fecha_emision, tipo_comprobante, letra_comprobante, punto_venta, numero_factura,
               condicion_venta, importe_total, razon_social_emisor
        FROM {AFIP_VIEW}
        WHERE condicion_venta ILIKE %s
    """
    params = [f"%{condicion}%"]
    if desde and hasta:
        base += " AND fecha_emision >= %s::date AND fecha_emision <= %s::date"
        params += [desde, hasta]
    base += " ORDER BY fecha_emision DESC, id DESC LIMIT %s"
    params.append(_limit(limit, default=50))
    return _execute(base, tuple(params))

@tool
def facturas_vencen_entre(desde: str, hasta: str, workspace: str = "") -> str:
    """
    Lista facturas cuyo vencimiento está entre fechas (YYYY-MM-DD).
    """
    q = f"""
        SELECT id, fecha_emision, fecha_vencimiento, razon_social_emisor, importe_total, tipo_comprobante, letra_comprobante, punto_venta, numero_factura
        FROM {AFIP_VIEW}
        WHERE fecha_vencimiento IS NOT NULL
          AND fecha_vencimiento >= %s::date AND fecha_vencimiento <= %s::date
        ORDER BY fecha_vencimiento ASC, id DESC;
    """
    return _execute(q, (desde, hasta))

@tool
def facturas_por_moneda(moneda: str = "ARS", desde: str = None, hasta: str = None, limit: int = 50, workspace: str = "") -> str:
    """
    Facturas en una moneda específica (ARS, USD, EUR, ...).
    """
    base = f"""
        SELECT id, fecha_emision, moneda, cotizacion_moneda, importe_total, razon_social_emisor,
               tipo_comprobante, letra_comprobante, punto_venta, numero_factura
        FROM {AFIP_VIEW}
        WHERE moneda = %s
    """
    params = [moneda]
    if desde and hasta:
        base += " AND fecha_emision >= %s::date AND fecha_emision <= %s::date"
        params += [desde, hasta]
    base += " ORDER BY fecha_emision DESC, id DESC LIMIT %s"
    params.append(_limit(limit, default=50))
    return _execute(base, tuple(params))

@tool
def buscar_facturas_por_texto_libre(texto: str, limit: int = 25, workspace: str = "") -> str:
    """
    Búsqueda 'like' básica sobre razón social emisor/receptor y file_name.
    """
    like = f"%{texto}%"
    q = f"""
        SELECT id, file_name, fecha_emision, razon_social_emisor, razon_social_receptor, importe_total
        FROM {AFIP_VIEW}
        WHERE razon_social_emisor ILIKE %s
           OR razon_social_receptor ILIKE %s
           OR file_name ILIKE %s
        ORDER BY fecha_emision DESC, id DESC
        LIMIT %s;
    """
    return _execute(q, (like, like, like, _limit(limit, default=25)))

@tool
def ultimas_facturas(limit: int = 20, workspace: str = "") -> str:
    """
    Devuelve las últimas N facturas ingresadas.
    """
    q = f"""
        SELECT fecha_recepcion, file_name, fecha_emision, razon_social_emisor,
               tipo_comprobante, letra_comprobante, punto_venta, numero_factura, importe_total, moneda, emisor_mail
        FROM {AFIP_VIEW}
        ORDER BY id DESC
        LIMIT %s;
    """
    return _execute(q, (_limit(limit, default=20),))

# ---------------------- TOOLS (Tablas detalle) ----------------------

@tool
def detalle_factura(factura_id: int) -> str:
    """
    Devuelve la factura (vista) + sus IVAs, percepciones e items como JSON embebido.
    """
    q = f"""
        SELECT
          v.*,
          COALESCE(
            (SELECT json_agg(json_build_object(
                'alicuota', alicuota, 'neto_gravado', neto_gravado, 'importe_iva', importe_iva
             ) ORDER BY alicuota)
             FROM {T_IVA} vi WHERE vi.factura_id = v.id), '[]'
          ) AS ivas,
          COALESCE(
            (SELECT json_agg(json_build_object(
                'tipo', tipo, 'jurisdiccion', jurisdiccion, 'monto', monto
             ) ORDER BY tipo, jurisdiccion)
             FROM {T_PERCP} p WHERE p.factura_id = v.id), '[]'
          ) AS percepciones,
          COALESCE(
            (SELECT json_agg(json_build_object(
                'cod_servicio', cod_servicio, 'detalle', detalle,
                'cantidad', cantidad, 'precio_unitario', precio_unitario,
                'subtotal', subtotal, 'alicuota_iva', alicuota_iva
             ) ORDER BY id)
             FROM {T_ITEM} it WHERE it.factura_id = v.id), '[]'
          ) AS items
        FROM {AFIP_VIEW} v
        WHERE v.id = %s;
    """
    return _execute(q, (factura_id,))

@tool
def resumen_percepciones_iibb(desde: str, hasta: str, cuit_emisor: str = "", workspace: str = "") -> str:
    """
    Resumen de percepciones IIBB por jurisdicción entre fechas (opcional filtrar por CUIT emisor).
    """
    if cuit_emisor:
        q = f"""
            SELECT p.jurisdiccion, SUM(p.monto) AS total
            FROM {T_PERCP} p
            JOIN {T_FACTURA} f ON f.id = p.factura_id
            JOIN {T_CONTRIB} e ON e.id = f.emisor_id
            WHERE p.tipo = 'IIBB'
              AND f.fecha_emision >= %s::date AND f.fecha_emision <= %s::date
              AND e.cuit = %s
            GROUP BY p.jurisdiccion
            ORDER BY total DESC;
        """
        return _execute(q, (desde, hasta, cuit_emisor))
    else:
        q = f"""
            SELECT p.jurisdiccion, SUM(p.monto) AS total
            FROM {T_PERCP} p
            JOIN {T_FACTURA} f ON f.id = p.factura_id
            WHERE p.tipo = 'IIBB'
              AND f.fecha_emision >= %s::date AND f.fecha_emision <= %s::date
            GROUP BY p.jurisdiccion
            ORDER BY total DESC;
        """
        return _execute(q, (desde, hasta))

@tool
def resumen_iva_por_alicuota(desde: str, hasta: str, cuit_emisor: str = "", workspace: str = "") -> str:
    """
    Suma de IVA por alícuota (ej. 21, 10.5, 27) entre fechas, global u opcional por emisor.
    """
    if cuit_emisor:
        q = f"""
            SELECT vi.alicuota, SUM(vi.importe_iva) AS total_iva, SUM(vi.neto_gravado) AS neto
            FROM {T_IVA} vi
            JOIN {T_FACTURA} f ON f.id = vi.factura_id
            JOIN {T_CONTRIB} e ON e.id = f.emisor_id
            WHERE f.fecha_emision >= %s::date AND f.fecha_emision <= %s::date
              AND e.cuit = %s
            GROUP BY vi.alicuota
            ORDER BY vi.alicuota;
        """
        return _execute(q, (desde, hasta, cuit_emisor))
    else:
        q = f"""
            SELECT vi.alicuota, SUM(vi.importe_iva) AS total_iva, SUM(vi.neto_gravado) AS neto
            FROM {T_IVA} vi
            JOIN {T_FACTURA} f ON f.id = vi.factura_id
            WHERE f.fecha_emision >= %s::date AND f.fecha_emision <= %s::date
            GROUP BY vi.alicuota
            ORDER BY vi.alicuota;
        """
        return _execute(q, (desde, hasta))

@tool
def items_de_factura(factura_id: int) -> str:
    """
    Devuelve los ítems de una factura (detalle, cantidades, precios).
    """
    q = f"""
        SELECT id, cod_servicio, detalle, cantidad, precio_unitario, subtotal, alicuota_iva
        FROM {T_ITEM}
        WHERE factura_id = %s
        ORDER BY id;
    """
    return _execute(q, (factura_id,))

# ---------------------- TOOLS (Controles APOCRIFAS - CAE - MIS COMPROBANTES) ----------------------
@tool
def listar_apocrifas(limit: int = 20) -> str:
    """
    Facturas cuyo emisor figura en apócrifas.
    """
    q = """
      SELECT fecha_emision, razon_social_emisor AS emisor, cuit_emisor,
             pv_num AS comprobante, importe_total, moneda, emisor_mail,
             fecha_condicion_apocrifo, fecha_publicacion, apocrifas_desc
      FROM afip.vw_facturas_apocrifas
      WHERE emisor_en_apocrifas = TRUE
      ORDER BY fecha_emision DESC NULLS LAST
      LIMIT %(lim)s::int;
    """
    return _execute(q, {"lim": _limit(limit)})

# Inicio Controles CAE ---------------------------------------------------------------------------------
@tool
def listar_cae(motivo: str = "NO_EN_PADRON", limit: int = 20) -> str:
    """
    Facturas por estado de validación de CAE: OK | NO_EN_PADRON | FECHA_NO_COINCIDE | SIN_CAE.
    """
    motivo = (motivo or "").upper().strip()
    if motivo not in {"OK", "NO_EN_PADRON", "FECHA_NO_COINCIDE", "SIN_CAE"}:
        motivo = "NO_EN_PADRON"
    q = """
      SELECT fecha_emision, razon_social_emisor AS emisor, cuit_emisor,
             pv_num AS comprobante, cae_numero, cae_fecha_vto,
             validacion_cae, estado_cae, vencimiento_cae
      FROM afip.vw_facturas_cae
      WHERE validacion_cae = %(motivo)s
      ORDER BY fecha_emision DESC NULLS LAST
      LIMIT %(lim)s::int;
    """
    return _execute(q, {"motivo": motivo, "lim": _limit(limit)})

CAE_VIEW = "afip.vw_facturas_cae"

@tool
def listar_no_en_padron_cae(
    limit: int = 100,
    desde: str = "",
    hasta: str = "",
    moneda: str = "",
    incluir_totales: bool = True
) -> str:
    """
    Lista facturas cuyo CAE NO figura en el padrón (validacion_cae = 'NO_EN_PADRON').
    Parámetros opcionales:
      - desde / hasta: YYYY-MM-DD (filtra por fecha_emision)
      - moneda: filtra por moneda exacta (ej. 'ARS', 'USD')
      - incluir_totales: agrega columnas de total por moneda y total general
      - limit: cantidad de filas
    """
    d = (desde or "").strip() or None
    h = (hasta or "").strip() or None
    m = (moneda or "").strip() or None

    tot_cols = ", sum(importe_total) OVER (PARTITION BY moneda) AS total_por_moneda, sum(importe_total) OVER () AS total_general" if incluir_totales else ""

    q = f"""
      SELECT
        fecha_emision,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        moneda,
        importe_total,
        cae_numero,
        cae_fecha_vto,
        estado_cae,
        vencimiento_cae
        {tot_cols}
      FROM {CAE_VIEW}
      WHERE validacion_cae = 'NO_EN_PADRON'
        AND (%(desde)s::date IS NULL OR fecha_emision >= %(desde)s::date)
        AND (%(hasta)s::date IS NULL OR fecha_emision <= %(hasta)s::date)
        AND (%(moneda)s IS NULL OR moneda = %(moneda)s)
      ORDER BY fecha_emision DESC NULLS LAST
      LIMIT %(lim)s::int;
    """
    return _execute(q, {"desde": d, "hasta": h, "moneda": m, "lim": _limit(limit)})

@tool
def listar_autorizacion_cae(
    tipo: str = "NO_AUTORIZADAS",
    limit: int = 100,
    desde: str = "",
    hasta: str = "",
    moneda: str = "",
    incluir_totales: bool = True
) -> str:
    """
    Lista facturas AUTORIZADAS o NO AUTORIZADAS según 'validacion_cae' contra el padrón.
    Definición por defecto:
      - AUTORIZADAS: validacion_cae = 'OK'
      - NO_AUTORIZADAS: validacion_cae IN ('FECHA_NO_COINCIDE','NO_EN_PADRON','SIN_CAE')

    Parámetros:
      - tipo: 'AUTORIZADAS' | 'NO_AUTORIZADAS'
      - desde / hasta: YYYY-MM-DD (filtra por fecha_emision)
      - moneda: filtra por moneda exacta
      - incluir_totales: agrega total_por_moneda y total_general
      - limit: cantidad de filas
    """
    t = (tipo or "").upper().strip()
    if t not in {"AUTORIZADAS", "NO_AUTORIZADAS"}:
        t = "NO_AUTORIZADAS"

    d = (desde or "").strip() or None
    h = (hasta or "").strip() or None
    m = (moneda or "").strip() or None

    if t == "AUTORIZADAS":
        cond = "validacion_cae = 'OK'"
    else:
        cond = "validacion_cae IN ('FECHA_NO_COINCIDE','NO_EN_PADRON','SIN_CAE')"

    tot_cols = ", sum(importe_total) OVER (PARTITION BY moneda) AS total_por_moneda, sum(importe_total) OVER () AS total_general" if incluir_totales else ""

    q = f"""
      SELECT
        fecha_emision,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        moneda,
        importe_total,
        cae_numero,
        cae_fecha_vto,
        estado_cae,
        vencimiento_cae,
        validacion_cae
        {tot_cols}
      FROM {CAE_VIEW}
      WHERE {cond}
        AND (%(desde)s::date IS NULL OR fecha_emision >= %(desde)s::date)
        AND (%(hasta)s::date IS NULL OR fecha_emision <= %(hasta)s::date)
        AND (%(moneda)s IS NULL OR moneda = %(moneda)s)
      ORDER BY fecha_emision DESC NULLS LAST
      LIMIT %(lim)s::int;
    """
    return _execute(q, {"desde": d, "hasta": h, "moneda": m, "lim": _limit(limit)})

# Inicio Controles CAE ---------------------------------------------------------------------------------

@tool
def listar_no_en_mis_comprobantes(limit: int = 20) -> str:
    """
    Facturas que NO figuran en mis_comprobantes (por CUIT/PV/Número).
    """
    q = """
      SELECT
        fecha_emision AS fecha,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        importe_total,
        moneda,
        emisor_mail
      FROM afip.vw_facturas_mis_comprobantes
      WHERE COALESCE(existe_en_mis_comprobantes, FALSE) = FALSE
      ORDER BY fecha DESC NULLS LAST
      LIMIT %s;
    """
    return _execute(q, (_limit(limit),))

@tool
def listar_en_mis_comprobantes(limit: int = 20) -> str:
    """
    Facturas que SÍ figuran en mis_comprobantes (match por CUIT/PV/Número).
    Muestra también la fila que las hizo coincidir en “Mis comprobantes”.
    """
    q = """
      SELECT
        fecha_emision AS fecha,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        importe_total,
        moneda,
        emisor_mail,
        fecha_mis,
        numero_desde,
        numero_hasta
      FROM afip.vw_facturas_mis_comprobantes
      WHERE COALESCE(existe_en_mis_comprobantes, FALSE) = TRUE
      ORDER BY fecha_mis DESC NULLS LAST, fecha DESC NULLS LAST
      LIMIT %s;
    """
    return _execute(q, (_limit(limit),))

@tool
def listar_no_en_mis_comprobantes_por_cuit(cuit: str, limit: int = 20) -> str:
    """
    Facturas de un CUIT que NO figuran en 'mis_comprobantes'.
    El CUIT puede venir con guiones o espacios.
    """
    # normalizo CUIT a solo dígitos
    digits = "".join(ch for ch in (cuit or "") if ch.isdigit())

    q = """
      SELECT
        fecha_emision,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        importe_total,
        moneda,
        emisor_mail
      FROM afip.vw_facturas_mis_comprobantes
      WHERE cuit_emisor = %s
        AND COALESCE(existe_en_mis_comprobantes, FALSE) = FALSE
      ORDER BY fecha_emision DESC NULLS LAST
      LIMIT %s;
    """
    return _execute(q, (digits, _limit(limit)))

@tool
def listar_en_mis_comprobantes_por_cuit(cuit: str, limit: int = 20) -> str:
    """
    Facturas de un CUIT que SÍ aparecen en 'mis_comprobantes'.
    Muestra además la fila de MC que hizo match (fecha y rango).
    """
    digits = "".join(ch for ch in (cuit or "") if ch.isdigit())

    q = """
      SELECT
        fecha_emision,
        razon_social_emisor AS emisor,
        cuit_emisor,
        pv_num AS comprobante,
        importe_total,
        moneda,
        emisor_mail,
        fecha_mis,
        numero_desde,
        numero_hasta
      FROM afip.vw_facturas_mis_comprobantes
      WHERE cuit_emisor = %s
        AND COALESCE(existe_en_mis_comprobantes, FALSE) = TRUE
      ORDER BY fecha_mis DESC NULLS LAST, fecha_emision DESC NULLS LAST
      LIMIT %s;
    """
    return _execute(q, (digits, _limit(limit)))


# @tool
# def resumen_validaciones() -> str:
#     """
#     Resumen global (usa la consolidada).
#     """
#     q = """
#     WITH c AS (
#       SELECT validacion_cae, COUNT(*)::bigint n
#       FROM afip.vw_facturas_cae
#       GROUP BY validacion_cae
#     ),
#     m AS (
#       SELECT
#         SUM(CASE WHEN COALESCE(existe_en_mis_comprobantes,FALSE) THEN 1 ELSE 0 END)::bigint AS en_mis,
#         SUM(CASE WHEN COALESCE(existe_en_mis_comprobantes,FALSE) THEN 0 ELSE 1 END)::bigint AS fuera_mis
#       FROM afip.vw_facturas_mis_comprobantes
#     ),
#     a AS (
#       SELECT COUNT(*)::bigint AS apocrifas
#       FROM afip.vw_facturas_apocrifas
#     )
#     SELECT
#       a.apocrifas,
#       COALESCE(MAX(CASE WHEN c.validacion_cae='OK' THEN c.n END),0)                AS cae_ok,
#       COALESCE(MAX(CASE WHEN c.validacion_cae='NO_EN_PADRON' THEN c.n END),0)       AS cae_no_en_padron,
#       COALESCE(MAX(CASE WHEN c.validacion_cae='FECHA_NO_COINCIDE' THEN c.n END),0)  AS cae_fecha_no_coincide,
#       COALESCE(MAX(CASE WHEN c.validacion_cae='SIN_CAE' THEN c.n END),0)            AS cae_sin_cae,
#       m.en_mis,
#       m.fuera_mis;
#     """
#     return _execute(q, {})

# ---------------------- TOOLS (utilitarias) ----------------------

@tool
def ping_db() -> str:
    """
    Valida conexión a la base y versión de Postgres.
    """
    return _execute_one("SELECT version();")

@tool
def info_factura_min(factura_id: int) -> str:
    """
    Devuelve info mínima de una factura (por id).
    """
    q = f"""
        SELECT id, file_name, emisor_mail, fecha_recepcion, fecha_emision,
               tipo_comprobante, letra_comprobante, punto_venta, numero_factura, importe_total
        FROM {AFIP_VIEW}
        WHERE id = %s;
    """
    return _execute(q, (factura_id,))


# ──────────────────────────────────────────────────────────────────────────────
# RAG por-workspace (índice local del workspace)
# ──────────────────────────────────────────────────────────────────────────────

@tool
def buscar_en_documentos_de_conocimiento(consulta: str, workspace: str) -> str:
    """
    Busca contexto en el vectorstore del workspace (PDF/DOCX/Excel cargados allí).
    Útil para dudas generales del workspace (no el índice central de leyes).
    """
    vectordb = cargar_vectorstore(workspace)
    if not vectordb:
        return "La base de conocimiento vectorial no está disponible."
    docs = vectordb.similarity_search(consulta, k=4)
    if not docs:
        return "No se encontraron documentos relevantes."
    # Recortamos cada chunk para no inundar
    partes = []
    for d in docs:
        txt = d.page_content or ""
        if len(txt) > 2000:
            txt = txt[:2000] + " …"
        partes.append(txt)
    contexto = "\n\n".join(partes)
    return f"Contexto encontrado:\n{contexto}"

# ──────────────────────────────────────────────────────────────────────────────
# RAG LEYES (ÍNDICE CENTRAL CHROMA creado por central_vectorizer.py)
# ──────────────────────────────────────────────────────────────────────────────

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
import chromadb
from chromadb.config import Settings

CENTRAL_ROOT    = Path(os.getenv("CENTRAL_DOCS_ROOT", "../Leyes")).resolve()
PERSIST_DIR     = Path(os.getenv("VECTORSTORE_DIR", "../leyes_vectorizer")).resolve()
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "central_leyes")
DOMAIN_TAG      = os.getenv("DOMAIN_TAG", "leyes")

EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "auto")  # auto | openai | local
OPENAI_EMBED_MODEL  = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CACHE_EMBEDDINGS    = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"
CHROMA_SETTINGS = Settings(
    anonymized_telemetry=os.getenv("CHROMA_TELEMETRY", "false").lower() == "true"
)

def _build_embedder():
    """Replica la lógica del indexado para evitar mismatch de dimensiones."""
    use_openai = (EMBEDDINGS_PROVIDER == "openai") or (
        EMBEDDINGS_PROVIDER == "auto" and os.getenv("OPENAI_API_KEY")
    )
    if use_openai:
        base = OpenAIEmbeddings(model=OPENAI_EMBED_MODEL)
    else:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            return f"Error: EMBEDDINGS_PROVIDER='{EMBEDDINGS_PROVIDER}' requiere 'sentence-transformers' instalado. {e}"
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        class _Local:
            def embed_documents(self, texts: List[str]):
                return model.encode(texts, normalize_embeddings=True).tolist()
            def embed_query(self, text: str):
                return self.embed_documents([text])[0]
        base = _Local()

    if CACHE_EMBEDDINGS:
        cache_dir = PERSIST_DIR / "embed_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 🔐 Encoder SHA-256 para la caché (evita el warning de SHA-1)
        def _sha256_encoder(x: bytes) -> str:
            return hashlib.sha256(x).hexdigest()

        try:
            return CacheBackedEmbeddings.from_bytes_store(
                base,
                LocalFileStore(str(cache_dir)),
                key_encoder=_sha256_encoder,
            )
        except Exception:
            return base
    return base


# ===================== HELPERS CHROMA (RAW) =====================

def _open_raw_collection():
    """
    Abre la colección Chroma nativa por nombre, evitando el wrapper de LangChain.
    """
    client = chromadb.PersistentClient(path=str(PERSIST_DIR), settings=CHROMA_SETTINGS)
    return client.get_or_create_collection(COLLECTION_NAME)

def _embed_query_vec(text: str) -> List[float]:
    """
    Genera el embedding de la consulta usando el mismo embedder del indexado.
    """
    emb = _build_embedder()
    if hasattr(emb, "embed_query"):
        return emb.embed_query(text)
    if hasattr(emb, "embed_documents"):
        return emb.embed_documents([text])[0]
    raise RuntimeError("No se pudo construir el embedder para consultas.")

# ===================== EXTRACTORES LEGALES (regex/heurísticas) =====================

_ART_SPLIT_RE = re.compile(r'(?im)^\s*art[íi]culo\s+(\d+[a-z]?)\s*\.?\s*[-–—]?\s*(.*)$')
_PERCENT_RE   = re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*%')

def _split_articles(full_text: str) -> List[Dict[str, str]]:
    """
    Separa el texto en artículos: [{"num":"3", "title":"...", "body":"..."}]
    Robusto ante may/minus, acentos y guiones.
    """
    lines = full_text.splitlines()
    idxs = []
    for i, line in enumerate(lines):
        if _ART_SPLIT_RE.match(line.strip()):
            idxs.append(i)
    if not idxs:
        return [{"num": None, "title": None, "body": full_text.strip()}]

    idxs.append(len(lines))
    arts = []
    for a, b in zip(idxs, idxs[1:]):
        head = lines[a].strip()
        m = _ART_SPLIT_RE.match(head)
        num = m.group(1) if m else None
        title = m.group(2).strip() if (m and m.group(2)) else None
        body = "\n".join(lines[a+1:b]).strip()
        arts.append({"num": num, "title": title, "body": body})
    return arts

def _normalize_space(x: str) -> str:
    return re.sub(r'\s+', ' ', x).strip()

def _sentences(text: str) -> List[str]:
    # corte simple por puntuación fuerte
    return [s.strip() for s in re.split(r'(?<=[\.\?!])\s+', _normalize_space(text)) if s.strip()]

def _extract_key_points(full_text: str) -> Dict[str, Any]:
    """
    Devuelve un resumen estructurado con:
      - agents: quiénes deben actuar como agentes (frases y artículo)
      - operations: lista de operaciones si se mencionan (ventas, servicios, locaciones, obras, etc.)
      - subjects: 'sujetos pasibles' si aparecen
      - rates: lista de {"rate":"2%","sentence":"...","article": "..."}
      - validity: oraciones de vigencia/aplicación
      - articles_index: lista de artículos disponibles
    """
    out = {"agents": [], "operations": [], "subjects": [], "rates": [], "validity": [], "articles_index": []}

    arts = _split_articles(full_text)
    out["articles_index"] = [a["num"] for a in arts if a.get("num")]

    # 1) AGENTES / OBLIGACIONES
    for a in arts:
        body = a["body"]
        for s in _sentences(body):
            if re.search(r'\bagentes?\s+de\s+(retenci[oó]n|percepci[oó]n|informaci[oó]n)\b', s, flags=re.I) or \
               re.search(r'est[áa]n\s+obligad[oa]s?\s+a\s+actuar\s+como\s+agentes?', s, flags=re.I):
                out["agents"].append({"article": a.get("num"), "text": s})

    # 2) OPERACIONES (busco en Art. 1/2 y donde aparezca 'operaciones')
    for a in arts:
        if a.get("num") in ("1","2", None) or re.search(r'\boperaci[oó]nes?\b', a["body"], flags=re.I):
            m = re.search(r'(ventas? de bienes?.*?)(?:\.\s|;|$)', a["body"], flags=re.I|re.S)
            if m:
                frag = _normalize_space(m.group(1))
                items = [i.strip(" .;:") for i in re.split(r',|\sy\s', frag) if len(i.strip())>=3]
                uniq = []
                for it in items:
                    if it.lower() not in [u.lower() for u in uniq] and len(it) <= 120:
                        uniq.append(it)
                if uniq:
                    out["operations"] = uniq
                    break

    # 3) SUJETOS PASIBLES
    for a in arts:
        for s in _sentences(a["body"]):
            if re.search(r'\bsujet[oa]s?\s+pasibles?\b', s, flags=re.I):
                out["subjects"].append({"article": a.get("num"), "text": s})

    # 4) ALÍCUOTAS / PORCENTAJES
    for a in arts:
        for s in _sentences(a["body"]):
            if _PERCENT_RE.search(s) or re.search(r'\bal[ií]cuota\b|\bpercepci[oó]n\b', s, flags=re.I):
                rates = _PERCENT_RE.findall(s)
                if rates:
                    for r in rates:
                        out["rates"].append({"rate": r.replace(',', '.' ) + "%", "sentence": s, "article": a.get("num")})
                else:
                    out["rates"].append({"rate": None, "sentence": s, "article": a.get("num")})

    # 5) VIGENCIA
    for a in arts:
        for s in _sentences(a["body"]):
            if re.search(r'entrar[aá]n?\s+en\s+vigencia|rigen?\s+a\s+partir|aplicar[aá]n?\s+a\s+partir|vigencia', s, flags=re.I):
                out["validity"].append({"article": a.get("num"), "text": s})

    # deduplicados / límites
    def _dedup(lst, key="text"):
        seen = set(); out2 = []
        for x in lst:
            val = (x.get(key) or "").lower()
            if val and val not in seen:
                seen.add(val); out2.append(x)
        return out2[:6]

    out["agents"]   = _dedup(out["agents"])
    out["subjects"] = _dedup(out["subjects"])
    out["validity"] = _dedup(out["validity"])
    out["rates"]    = out["rates"][:6]
    out["operations"] = out["operations"][:8]
    return out

# ===================== BUSCAR_LEYES (COMPLETO) =====================

def _normalize_where(clauses: List[Dict]) -> Dict:
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}

def _where_domain(domain: str, law: Optional[str]=None,
                  root: Optional[str]=None, province: Optional[str]=None) -> Dict:
    clauses = [{"domain": {"$eq": domain}}]
    # Si pasás law, filtramos por ley exacta
    if law:
        clauses.append({"law": {"$eq": law}})
    # Si pasás root/province, usamos $contains sobre file_path (no requiere reindexar)
    if root:
        clauses.append({"file_path": {"$contains": f"{root}/"}})
    if province:
        # si root también vino, queda root/province; si no, solo province
        clauses.append({"file_path": {"$contains": f"{root}/{province}/"}} if root
                       else {"file_path": {"$contains": f"{province}/"}})
    return _normalize_where(clauses)


@tool
def buscar_fragmentos_de_leyes(
    query: str,
    k: int = 5,
    law: Optional[str] = None,
    root: Optional[str] = None,
    province: Optional[str] = None,
    workspace: Optional[str] = None
) -> str:
    """
    Recupera fragmentos relevantes (chunks) y aplica un RERANK simple por coincidencias literales
    de la query en el texto, con un pequeño boost por provincia. Devuelve JSON compacto.
    """
    # -------- helpers locales --------
    def _where_minimal(**kv) -> Dict:
        """
        Construye un filtro Chroma válido:
        - 0 cláusulas  -> {}
        - 1 cláusula   -> esa cláusula (sin $and)
        - 2+ cláusulas -> {"$and":[...]}
        """
        clauses = []
        for kname, val in kv.items():
            if val is None:
                continue
            clauses.append({kname: {"$eq": val}})
        if not clauses:
            return {}
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _trim(s: str, n: int = 1000) -> str:
        return s if not s or len(s) <= n else (s[:n] + " …")

    def _content_hits(text: str, toks: List[str]) -> int:
        if not text:
            return 0
        tl = text.lower()
        return sum(1 for t in toks if t in tl)

    def _province_boost_text(text: str, prov: Optional[str]) -> int:
        if not prov or not text:
            return 0
        return 1 if prov.lower() in text.lower() else 0

    # normaliza root/province a MAYÚSCULAS si vienen
    root = root.upper() if isinstance(root, str) else root
    province = province.upper() if isinstance(province, str) else province

    # abrir colección cruda
    try:
        col = _open_raw_collection()
    except Exception as e:
        return f"Error en buscar_fragmentos_de_leyes: Chroma open error: {e}"

    # where por metadatos (usa SOLO $eq)
    where = _where_minimal(domain=DOMAIN_TAG, law=law, root=root, province=province)

    # embed query
    try:
        qvec = _embed_query_vec(query)
    except Exception as e:
        return f"Error en buscar_fragmentos_de_leyes: embedding error: {e}"

    # oversampling para poder rerankear
    n_fetch = min(200, max(int(k) * 6, 30))
    try:
        qr = col.query(
            query_embeddings=[qvec],
            n_results=n_fetch,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return f"Error en buscar_fragmentos_de_leyes: Chroma query error: {e}"

    docs  = (qr.get("documents") or [[]])[0]
    metas = (qr.get("metadatas") or [[]])[0]
    dists = (qr.get("distances") or [[]])[0]

    tri = list(zip(docs, metas, dists))
    if not tri:
        # fallback: si el filtro fue muy restrictivo, probá sin root/province/law
        where_fb = _where_minimal(domain=DOMAIN_TAG)
        try:
            qr2 = col.query(
                query_embeddings=[qvec],
                n_results=n_fetch,
                where=where_fb,
                include=["documents", "metadatas", "distances"],
            )
            docs  = (qr2.get("documents") or [[]])[0]
            metas = (qr2.get("metadatas") or [[]])[0]
            dists = (qr2.get("distances") or [[]])[0]
            tri = list(zip(docs, metas, dists))
        except Exception:
            tri = []

    if not tri:
        return json.dumps({
            "status": "no_results",
            "query": query,
            "used_filters": {"domain": DOMAIN_TAG, "law": law, "root": root, "province": province},
            "found": 0
        }, ensure_ascii=False)

    # ------------- RERANK combinado (METADATOS + CONTENIDO) -------------
    # tokens “simples” de la query
    q_lc = (query or "").lower().strip()
    q_noext = re.sub(r"\.pdf$", "", q_lc)
    q_tokens = [t for t in re.findall(r"[a-záéíóúñ0-9]+", q_lc) if len(t) >= 3]

    def _content_hits(text: str, toks: List[str]) -> int:
        if not text:
            return 0
        tl = text.lower()
        return sum(1 for t in toks if t in tl)

    def _province_boost_text(text: str, prov: Optional[str]) -> int:
        if not prov or not text:
            return 0
        return 1 if prov.lower() in text.lower() else 0

    def _meta_score(md: dict) -> int:
        md = md or {}
        corpus = " ".join([
            md.get("file_name") or "",
            md.get("file_path") or "",
            md.get("law") or "",
            md.get("root") or "",
            md.get("province") or "",
        ]).lower()

        s = 0
        # hits por tokens de la query en metadatos
        for t in q_tokens:
            if t in corpus:
                s += 3

        # boost por acrónimos comunes en fiscalidad
        if any(x in corpus for x in ["sircreb", "sircip", "sircar", "sirtac", "comarb"]):
            s += 8

        # match exacto por nombre de archivo (con o sin .pdf)
        fname_noext = re.sub(r"\.pdf$", "", (md.get("file_name") or "").lower())
        if q_noext and q_noext == fname_noext:
            s += 20

        return s

    def _score(row) -> tuple:
        text, md, dist = row
        # ponderación combinada (metadatos tienen más peso para forzar el archivo correcto)
        meta = _meta_score(md)
        hits = _content_hits(text or "", q_tokens)
        pboost = _province_boost_text(text or "", province)
        total = (5 * meta) + hits + (2 * pboost)
        # orden ascendente: mayor score => más arriba (negativo), y a igualdad, menor distancia
        return (-(total), dist if dist is not None else 999)

    tri.sort(key=_score)
    tri = tri[:max(1, int(k))]


    # salida compacta y estable
    out = []
    for text, md, dist in tri:
        md = md or {}
        out.append({
            "texto": _trim(text or "", 1000),
            "ley": md.get("law"),
            "articulo": md.get("article"),
            "article_num": md.get("article_num"),
            "archivo": md.get("file_name"),
            "file_path": md.get("file_path"),
            "distancia": float(dist) if dist is not None else None,
            "chunk_index": md.get("chunk_index"),
            "root": md.get("root"),
            "province": md.get("province"),
        })

    return json.dumps({
        "status": "ok",
        "mode": "fragments",
        "query": query,
        "used_filters": {"domain": DOMAIN_TAG, "law": law, "root": root, "province": province},
        "found": len(out),
        "results": out,
        "diagnostics": {
            "persist_dir": str(PERSIST_DIR),
            "collection": COLLECTION_NAME,
            "domain_tag": DOMAIN_TAG
        }
    }, ensure_ascii=False)

from langchain_core.tools import tool

@tool
def contar_articulos_por_archivo(nombre_archivo: str, workspace: str | None = None) -> str:
    """
    Cuenta artículos de un archivo por NOMBRE (ej: 'SIRCREB' o 'SIRCREB.pdf').
    - 1) Intento match exacto por file_name (con y sin .pdf).
    - 2) Si no aparece exacto, hago una búsqueda aproximada y filtro por 'file_name' que contenga el término.
    Devuelve JSON con count y lista (acotada) de artículos detectados.
    """
    try:
        col = _open_raw_collection()

        # normalizo nombre: con y sin .pdf
        base = (nombre_archivo or "").strip()
        base_noext = re.sub(r"\.pdf$", "", base, flags=re.I)
        candidates = [base_noext + ".pdf", base] if base_noext else [base]

        got = None
        for cand in candidates:
            try:
                res = col.get(
                    where={"$and": [
                        {"domain": {"$eq": DOMAIN_TAG}},
                        {"file_name": {"$eq": cand}}
                    ]},
                    include=["metadatas", "documents"]
                )
                if res and res.get("ids"):
                    got = res
                    break
            except Exception:
                pass

        # Si no hubo match exacto, busco aprox y filtro por file_name que contenga el término
        pairs = []
        if not got:
            qr = col.query(
                query_texts=[base_noext or base],
                n_results=50,
                where={"domain": {"$eq": DOMAIN_TAG}},
                include=["metadatas", "documents", "distances"]
            )
            docs = (qr.get("documents") or [[]])[0]
            metas = (qr.get("metadatas") or [[]])[0]
            for md, txt in zip(metas, docs):
                fn = (md.get("file_name") or "").lower()
                if base_noext and base_noext.lower() in fn or base.lower() in fn:
                    pairs.append((md, txt))
        else:
            metas = got.get("metadatas") or []
            docs = got.get("documents") or []
            pairs = list(zip(metas, docs))

        if not pairs:
            return json.dumps({
                "status":"not_found",
                "file_query": nombre_archivo,
                "note":"No encontré ese archivo por nombre en el índice."
            }, ensure_ascii=False)

        # 1) Si hay metadatos 'article', úsalo (más fiable)
        arts = set()
        for md, _ in pairs:
            a = (md or {}).get("article")
            if a:
                arts.add(a.strip())
        if arts:
            ordered = sorted(arts, key=lambda s: (int(re.match(r"(\d+)", s).group(1)) if re.match(r"(\d+)", s) else 9999, s))
            return json.dumps({
                "status":"ok",
                "file_query": nombre_archivo,
                "count": len(ordered),
                "articles": ordered[:200]
            }, ensure_ascii=False)

        # 2) Si el PDF no tiene 'article' en metadatos, conteo heurístico por texto
        full = "\n\n".join(t for _, t in pairs if isinstance(t, str))
        matches = re.findall(r'(?im)^\s*art[íi]culo\s+\d+[^\n]*$', full)
        return json.dumps({
            "status":"ok",
            "file_query": nombre_archivo,
            "count": len(matches),
            "articles_detected": matches[:200],
            "note":"No había etiquetas 'article' en metadatos; se contó por texto."
        }, ensure_ascii=False)

    except Exception as e:
        return f"Error en contar_articulos_por_archivo: {e}"

@tool
def listar_articulos_de_ley(
    ley: str,
    workspace: Optional[str] = None
) -> str:
    """
    Devuelve el índice (lista) de artículos disponibles para una ley específica.
    'ley' debe ser el valor exacto de metadata 'law' (lo obtenés desde buscar_fragmentos_de_leyes).
    """
    try:
        col = _open_raw_collection()
        got = col.get(
            where=_where_domain(DOMAIN_TAG, law=ley),
            include=["metadatas"]
        )
        ids = got.get("ids") or []
        if not ids:
            return f"No se encontró la ley '{ley}'. Verifica el nombre usando `buscar_fragmentos_de_leyes`."

        seen = set()
        arts = []
        for md in got.get("metadatas") or []:
            label = (md or {}).get("article")
            if label and label not in seen:
                seen.add(label)
                arts.append(label)

        if not arts:
            return f"La ley '{ley}' fue encontrada pero no se pudieron extraer sus artículos."

        # ordenar por número si empieza con "Artículo N"
        def _key(a: str):
            m = re.search(r'(?i)art[íi]culo\s+(\d+)', a or "")
            return (int(m.group(1)) if m else 999999, a or "")
        arts = sorted(arts, key=_key)

        return json.dumps({"ley": ley, "articulos": arts}, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Error en listar_articulos_de_ley: {e}"


@tool
def obtener_articulo_completo(
    ley: str,
    articulo_num: str,
    workspace: Optional[str] = None
) -> str:
    """
    Devuelve el texto completo del artículo N de la 'ley' dada (metadata 'law').
    Acepta variantes de encabezado: 'Artículo 2', 'Art. 2º', 'Art 2°:', 'Artículo 2 bis', etc.
    Si existe metadata 'article_num' normalizada, la usa primero.
    """
    # --- helpers locales robustos ---
    def _where_minimal(**kv) -> Dict[str, Any]:
        clauses = []
        for k, v in kv.items():
            if v is None:
                continue
            clauses.append({k: {"$eq": v}})
        if not clauses:
            return {}
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _trim(s: str, n: int = 8000) -> str:
        return s if not s or len(s) <= n else (s[:n] + " …")

    # normaliza "2º", "2°", "2o", espacios y sufijos como bis/ter
    def _norm_art_num(s: str) -> str:
        s = (s or "").strip().lower()
        # quitar ordinales al final (º ° o)
        s = re.sub(r"\s*(?:º|°|o)\s*$", "", s)
        s = re.sub(r"\s+", " ", s)
        # normalizar variantes acentuadas de quáter, etc.
        s = (s
             .replace("quáter", "quater")
             .replace("quáter", "quater")
             .replace("quáter", "quater")
             .replace("quâter", "quater")
             .replace("quínties", "quinquies")
            )
        return s

    # regex que reconoce encabezados de artículo con variantes
    #   - Art., Art, Artículo (con/sin acento)
    #   - números con opcional º/°/o
    #   - sufijos: bis/ter/quater/quinquies (opcionales)
    #   - separadores: -, –, —, :, .
    _ART_HEAD_RE = re.compile(
        r"(?im)^\s*(?:art(?:[íi]culo)?\.?)\s*"
        r"(\d+)\s*(?:º|°|o)?\s*(?:\b(bis|ter|qu(?:a|á)ter|quinquies)\b)?\s*"
        r"[-–—:\.]?\s*(.*)$"
    )

    def _extract_norm_num(label_or_text: str) -> Optional[str]:
        """
        Si le pasás el label 'Artículo 2º - ...' o un bloque de texto que arranca con el encabezado,
        devuelve '2', '2 bis', etc. normalizado. Si no matchea, None.
        """
        if not label_or_text:
            return None
        m = _ART_HEAD_RE.search(label_or_text)
        if not m:
            return None
        num = m.group(1)
        suf = (m.group(2) or "").strip().lower()
        nn = f"{num} {suf}".strip()
        return _norm_art_num(nn)

    try:
        col = _open_raw_collection()

        # 1) Traer TODOS los chunks de esa ley
        got = col.get(
            where=_where_minimal(domain=DOMAIN_TAG, law=ley),
            include=["documents", "metadatas"]
        )
        ids = got.get("ids") or []
        if not ids:
            return f"No se encontró la ley '{ley}'. Verifica el nombre usando `buscar_fragmentos_de_leyes`."

        metas = got.get("metadatas") or []
        docs  = got.get("documents") or []

        # 2) Normalizar el número pedido
        target = _norm_art_num(articulo_num)

        # 3) Intento A: usar metadata 'article_num' si existe (reindex recomendado)
        target_docs, cites = [], []
        for md, txt in zip(metas, docs):
            md = md or {}
            md_num = _norm_art_num(md.get("article_num", "") or "")
            if md_num and md_num == target:
                target_docs.append(txt or "")
                cites.append({
                    "file_path": md.get("file_path"),
                    "file_name": md.get("file_name"),
                    "chunk_index": md.get("chunk_index"),
                })

        # 4) Intento B: si no hay 'article_num', comparar contra el label 'article' (si está)
        if not target_docs:
            for md, txt in zip(metas, docs):
                md = md or {}
                lbl = md.get("article") or ""
                nn = _extract_norm_num(lbl)
                if nn and nn == target:
                    target_docs.append(txt or "")
                    cites.append({
                        "file_path": md.get("file_path"),
                        "file_name": md.get("file_name"),
                        "chunk_index": md.get("chunk_index"),
                    })

        # 5) Intento C: último recurso, mirar el propio texto del chunk (por si el label no se guardó)
        #    Esto funciona si el chunk comienza con el encabezado del artículo.
        if not target_docs:
            for md, txt in zip(metas, docs):
                nn = _extract_norm_num((txt or "")[:300])  # inspecciono el inicio del chunk
                if nn and nn == target:
                    target_docs.append(txt or "")
                    cites.append({
                        "file_path": (md or {}).get("file_path"),
                        "file_name": (md or {}).get("file_name"),
                        "chunk_index": (md or {}).get("chunk_index"),
                    })

        if not target_docs:
            return (
                f"No se encontró el Artículo {articulo_num} en la ley '{ley}'. "
                f"Probá usar `listar_articulos_de_ley` para ver los disponibles. "
                f"Si este PDF abrevia con 'Art. N°', reindexá con el regex ampliado."
            )

        full = "\n\n".join(target_docs)
        return json.dumps({
            "ley": ley,
            "articulo": f"Artículo {articulo_num}",
            "texto": _trim(full, 8000),
            "citaciones": cites,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Error en obtener_articulo_completo: {e}"



# ──────────────────────────────────────────────────────────────────────────────
# Generación de archivos (Word/Excel vía MCP)
# ──────────────────────────────────────────────────────────────────────────────

@tool
def generar_documento_word(nombre_archivo: str, contenido: str, workspace: str) -> str:
    """Genera un .docx con el contenido proporcionado."""
    try:
        ruta_archivo = ejecutar_mcp(
            "generar_word",
            nombre_archivo=nombre_archivo,
            contenido=contenido,
            workspace=workspace
        )
        return f"Documento Word '{nombre_archivo}.docx' generado exitosamente. La ruta es: {ruta_archivo}"
    except Exception as e:
        return f"Error al generar el documento Word: {e}"

@tool
def generar_reporte_excel(nombre_archivo: str, tabla_json: str, workspace: str) -> str:
    """
    Genera un .xlsx a partir de 'tabla_json' (string JSON: lista de listas o lista de dicts).
    """
    try:
        tabla = json.loads(tabla_json)
        ruta_archivo = ejecutar_mcp(
            "generar_excel",
            nombre_archivo=nombre_archivo,
            tabla=tabla,
            workspace=workspace
        )
        return f"Reporte Excel '{nombre_archivo}.xlsx' generado. La ruta es: {ruta_archivo}"
    except Exception as e:
        return f"Error al generar el reporte Excel: {e}. Asegúrate de que la entrada sea un JSON válido."

# ──────────────────────────────────────────────────────────────────────────────
# Export: lista de herramientas
# ──────────────────────────────────────────────────────────────────────────────
lista_de_herramientas = [
    listar_facturas_por_cuit_receptor,
    listar_facturas_por_email_remitente,
    buscar_por_numero_factura,
    contar_duplicados_por_clave_natural,
    buscar_por_cae,
    total_facturado_por_emisor_y_mes,
    kpis_resumen,
    top_emisores_por_monto,
    facturas_por_condicion_venta,
    facturas_vencen_entre,
    facturas_por_moneda,
    buscar_facturas_por_texto_libre,
    ultimas_facturas,
    detalle_factura,
    resumen_percepciones_iibb,
    resumen_iva_por_alicuota,
    items_de_factura,
    info_factura_min,
    # Controles
    listar_apocrifas,
    listar_cae,
    listar_no_en_mis_comprobantes,
    listar_en_mis_comprobantes,
    listar_no_en_mis_comprobantes_por_cuit,
    listar_en_mis_comprobantes_por_cuit,
    # resumen_validaciones,
    # Controles CAE
    listar_no_en_padron_cae,
    listar_autorizacion_cae,
    # Controles CAE
    buscar_en_documentos_de_conocimiento,  # RAG por-workspace
    # RAG leyes (nuevas)
    buscar_fragmentos_de_leyes,
    contar_articulos_por_archivo,
    listar_articulos_de_ley,
    obtener_articulo_completo,
    generar_documento_word,
    generar_reporte_excel,
]
