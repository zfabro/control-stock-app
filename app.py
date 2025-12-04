import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import time

# --- Configuración de la Página ---
st.set_page_config(layout="wide")
st.title('Sistema de Control de Stock con Google Sheets')

# --- Conexión a Google Sheets ---
@st.cache_resource
def conectar_google_client():
    import json

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]

    creds = None

    if os.path.exists("service_account.json"):
        creds = service_account.Credentials.from_service_account_file(
            "service_account.json", scopes=SCOPES
        )
    elif "gcp_service_account" in st.secrets:
        service_info = json.loads(st.secrets["gcp_service_account"]["service_account_json"])
        creds = service_account.Credentials.from_service_account_info(
            service_info, scopes=SCOPES
        )
    else:
        st.error("❌ No se encontraron credenciales de cuenta de servicio.")
        st.stop()

    client = gspread.authorize(creds)
    st.success("Cliente Google Autorizado ✅ (Cuenta de Servicio)")
    return client

# --- Funciones de Datos ---
def cargar_y_procesar_datos(client):
    if client is None:
        return pd.DataFrame()

    try:
        sheet = client.open("Base de Datos Fábrica").sheet1
        records = sheet.get_all_records()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Error: No se encontró la hoja de cálculo 'Base de Datos Fábrica'.")
        st.stop()
    except Exception as e:
        st.warning(f"No se pudieron cargar los datos de GSheet: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    required_cols_db = ['fecha_hora', 'cantidad', 'material_codigo']
    if not df.empty and all(col in df.columns for col in required_cols_db):
        df['fecha_hora'] = df['fecha_hora'].astype(str).str.strip()
        formato_nuevo = pd.to_datetime(df['fecha_hora'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        formato_viejo = pd.to_datetime(df['fecha_hora'], errors='coerce')
        df['fecha_hora'] = formato_nuevo.fillna(formato_viejo)
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce')
        if 'planta' not in df.columns:
            df['planta'] = 'N/A'
        df.dropna(subset=['fecha_hora', 'cantidad', 'material_codigo'], inplace=True)
    elif not df.empty:
        st.warning(f"Datos cargados, pero podrían faltar columnas requeridas ({required_cols_db}) o tener formato inesperado.")
    return df

def guardar_dato_gsheet(client, nuevo_dato, rerun: bool = False):
    if client is None:
        st.error("Error de conexión, no se pudo guardar el dato.")
        return

    # --- Armar la cantidad ---
    cantidad = nuevo_dato.get("cantidad")

    # Si viene como lista desde el data_editor
    if isinstance(cantidad, list):
        if len(cantidad) > 0:
            cantidad = cantidad[0]
        else:
            st.error("Cantidad inválida (lista vacía)")
            return

    # Convertir a float seguro
    try:
        cantidad = float(cantidad)
    except Exception:
        st.error(f"Cantidad inválida: {cantidad}")
        return

    # Fila final para Google Sheets
    fila = [
        str(nuevo_dato.get('material_descripcion', '')),
        nuevo_dato.get('fecha_hora').strftime("%d/%m/%Y %H:%M:%S"),
        cantidad,
        str(nuevo_dato.get('planta', ''))
    ]

    try:
        sheet = client.open("Base de Datos Fábrica").sheet1
        sheet.append_row(fila)

        # Opcional: solo hacer rerun si se pide explícitamente
        if rerun:
            st.cache_resource.clear()
            time.sleep(1)
            st.rerun()

    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")


    def calcular_consumo_diario(df_historial):
        if len(df_historial) < 2:
            return 0
        df = df_historial.sort_values('fecha_hora').copy()
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce')
        df = df.dropna(subset=['cantidad'])
        if len(df) < 2: return 0
        df['Consumo'] = df['cantidad'].diff(-1) * -1
        df['Dias'] = df['fecha_hora'].diff(-1).dt.total_seconds().abs() / (24 * 3600)
        df_consumo = df[df['Consumo'] > 0]
        if df_consumo.empty or df_consumo['Dias'].sum() == 0:
            return 0
        return df_consumo['Consumo'].sum() / df_consumo['Dias'].sum()

# --- Catálogo Completo ---
materiales_catalogo = pd.DataFrame([
    # Insumos Combet 2
    {'codigo': 'PFD742-00/TD', 'descripcion': 'Diluyente', 'tipo': 'INSUMO', 'unidad': 'litros', 'planta': 'Combet 2'},
    {'codigo': 'Dowanol', 'descripcion': 'Dowanol', 'tipo': 'INSUMO', 'unidad': 'litros', 'planta': 'Combet 2'},
    {'codigo': '911114-C2', 'descripcion': 'Master Blanco', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '921020', 'descripcion': 'Master perlado', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '1401577-S', 'descripcion': 'Master Amarillo K', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '151410-S', 'descripcion': 'Master Rojo', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '961515-C2', 'descripcion': 'Master Azul', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '961150-C2', 'descripcion': 'Master Celeste', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '1303342-S-C2', 'descripcion': 'Master Amarillo', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': 'SL 342', 'descripcion': 'Adhesivo laminadora', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': 'R405', 'descripcion': 'Catalizador', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '901300', 'descripcion': 'Antibloking', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '901213', 'descripcion': 'Antiestatico', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '400700-ST', 'descripcion': 'Matif', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': 'FM-250375', 'descripcion': 'Carbonato', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '400998-S', 'descripcion': 'Hoslip 15', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 2'},
    {'codigo': '1260 MT cristal', 'descripcion': 'Hilo 1260', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': '2520 AT cristal', 'descripcion': 'Hilo 2500', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Hilo Poliester', 'descripcion': 'Hilo Poliester', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Crepp Blanco', 'descripcion': 'Crepp Blanco', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Crepp Rojo', 'descripcion': 'Crepp Rojo', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Crepp Negro', 'descripcion': 'Crepp Negro', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Crepp Verde', 'descripcion': 'Crepp Verde', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Streecht', 'descripcion': 'Streecht', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Flejes Manual', 'descripcion': 'Flejes Manual', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Flejes semi-automatico', 'descripcion': 'Flejes semi-automatico', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Hebillas', 'descripcion': 'Hebillas', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Gas', 'descripcion': 'Gas', 'tipo': 'INSUMO', 'unidad': 'litros', 'planta': 'Combet 2'},
    {'codigo': '5.3 EB', 'descripcion': 'Cinta Doble Faz', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Abrefácil', 'descripcion': 'Abrefácil', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Conos 3"', 'descripcion': 'Conos 3"', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Conos 4"', 'descripcion': 'Conos 4"', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Conos 6"', 'descripcion': 'Conos 6"', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Separadores (Cartón)', 'descripcion': 'Separadores (Cartón)', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Esquineros', 'descripcion': 'Esquineros', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Teflón Lamina s/ad 1m An', 'descripcion': 'Teflón Lamina s/ad 1m An', 'tipo': 'INSUMO', 'unidad': 'm', 'planta': 'Combet 2'},
    {'codigo': 'Teflón Cinta c/ad 5 cm', 'descripcion': 'Teflón Cinta c/ad 5 cm', 'tipo': 'INSUMO', 'unidad': 'm', 'planta': 'Combet 2'},
    {'codigo': 'Teflón Cinta c/ad 2,5 cm', 'descripcion': 'Teflón Cinta c/ad 2,5 cm', 'tipo': 'INSUMO', 'unidad': 'm', 'planta': 'Combet 2'},
    {'codigo': 'Teflón Cinta c/ad 1,5 cm', 'descripcion': 'Teflón Cinta c/ad 1,5 cm', 'tipo': 'INSUMO', 'unidad': 'm', 'planta': 'Combet 2'},
    {'codigo': 'Resistencias 5mm', 'descripcion': 'Resistencias 5mm', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Ø1/4x38mm', 'descripcion': 'Resistencias 150W Máq.3', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Ø3/8x100mm', 'descripcion': 'Resistencias 100W Máq.4', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'DRx2 / UY1973', 'descripcion': 'Agujas GROZ-BECKERT', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    {'codigo': 'Pallet 100x120', 'descripcion': 'Pallet 100x120', 'tipo': 'INSUMO', 'unidad': 'un', 'planta': 'Combet 2'},
    # Insumos Combet 1
    {'codigo': '911114-C1', 'descripcion': 'Master Blanco', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 1'},
    {'codigo': '961515-C1', 'descripcion': 'Master Azul', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 1'},
    {'codigo': '961150-C1', 'descripcion': 'Master Celeste', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 1'},
    {'codigo': '1303342-S-C1', 'descripcion': 'Master Amarillo', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 1'},
    {'codigo': '1504724-S', 'descripcion': 'Master Rojo', 'tipo': 'INSUMO', 'unidad': 'kg', 'planta': 'Combet 1'},
    # Materias Primas
    {'codigo': 'KYD 6200K', 'descripcion': 'KYD 6200K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LYD 6200K', 'descripcion': 'LYD 6200K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'KYD 6110K', 'descripcion': 'KYD 6110K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': '1102K', 'descripcion': '1102K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'SYMBIOS 3102', 'descripcion': 'SYMBIOS 3102', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'SYMBIOS 4102', 'descripcion': 'SYMBIOS 4102', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'HT ES RFD 6140K', 'descripcion': 'HT ES RFD 6140K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'HT ES RFD 6190K', 'descripcion': 'HT ES RFD 6190K', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'HT ES SP340', 'descripcion': 'HT ES SP340', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LLDPE 1630', 'descripcion': 'LLDPE 1630', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': '1102T', 'descripcion': '1102T', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'XSD 6200T', 'descripcion': 'XSD 6200T', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'AGILITY 7000', 'descripcion': 'AGILITY 7000', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'H103', 'descripcion': 'H103', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'H301', 'descripcion': 'H301', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'HE150', 'descripcion': 'HE150', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'H503', 'descripcion': 'H503', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LPD 230N', 'descripcion': 'LPD 230N', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'POLYETHYLENE 722', 'descripcion': 'POLYETHYLENE 722', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'POLIAMIDA 1030B', 'descripcion': 'POLIAMIDA 1030B', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LLDPE 1613.11', 'descripcion': 'LLDPE 1613.11', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LLDPE 1613/0', 'descripcion': 'LLDPE 1613/0', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LDPE 208M', 'descripcion': 'LDPE 208M', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LDPE 207M', 'descripcion': 'LDPE 207M', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LDPE 203M', 'descripcion': 'LDPE 203M', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'GM9450F 1666', 'descripcion': 'GM9450F 1666', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'ALC-30', 'descripcion': 'ALC-30', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'LLDPE 1630 C1', 'descripcion': 'LLDPE 1630 C1', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'HDPE 7000', 'descripcion': 'HDPE 7000', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'},
    {'codigo': 'EVAL H171B', 'descripcion': 'EVAL H171B', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg', 'planta': 'Materias Primas'}
])

# --- Interfaz ---
try:
    gspread_client = conectar_google_client()
    if gspread_client is None:
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Materias Primas",
        "Insumos",
        "🔧 Gestión de Materiales",
        "📋 Catálogo Actualizado"
    ])

    # Código completo corregido

    # --- TAB 1: MATERIA PRIMA ---

    def tab1_materia_prima(st, df_materia, save_to_sheet_materia):
        st.header("📦 Carga de Materia Prima")

        # --- Formulario para ingresar varias materias primas ---
        materias = []
        cantidad_items = st.number_input("Cantidad de materias primas a cargar", min_value=1, value=1, step=1)

        for i in range(cantidad_items):
            st.subheader(f"Materia Prima #{i+1}")
            nombre = st.text_input(f"Nombre MP #{i+1}")
            cantidad = st.number_input(f"Cantidad MP #{i+1}", min_value=0.0, step=0.01)
            unidad = st.selectbox(f"Unidad MP #{i+1}", ["kg", "litros", "unidades", "metros", "cm"], key=f"unidad_{i}")
            fecha = st.date_input(f"Fecha MP #{i+1}")

            materias.append({
                "Nombre": nombre,
                "Cantidad": cantidad,
                "Unidad": unidad,
                "Fecha": fecha.strftime("%d/%m/%Y")
            })

        # --- Botón Guardar ---
        if st.button("Guardar Materias Primas"):
            for item in materias:
                save_to_sheet_materia(item)
            st.success("Materia Prima guardada correctamente ✨")

        # --- Historial ---
        st.subheader("📜 Historial de Materias Primas")
        st.dataframe(df_materia)

        # --- Reporte Predictivo ---
        st.subheader("📈 Reporte Predictivo")
        if not df_materia.empty:
            df_materia['Cantidad'] = df_materia['Cantidad'].astype(float)
            resumen = df_materia.groupby('Nombre')['Cantidad'].sum().reset_index()
            st.bar_chart(resumen.set_index('Nombre'))
        else:
            st.info("Aún no hay datos para generar un reporte predictivo.")


    # --- TAB 2: INSUMOS ---

    def tab2_insumos(st, df_insumos, save_to_sheet_insumos):
        st.header("🛠️ Carga de Insumos")

        insumos = []
        cantidad_items = st.number_input("Cantidad de insumos a cargar", min_value=1, value=1, step=1, key="cant_insumos")

        for i in range(cantidad_items):
            st.subheader(f"Insumo #{i+1}")
            nombre = st.text_input(f"Nombre Insumo #{i+1}", key=f"nom_ins_{i}")
            cantidad = st.number_input(f"Cantidad Insumo #{i+1}", min_value=0.0, step=0.01, key=f"cant_ins_{i}")
            unidad = st.selectbox(f"Unidad Insumo #{i+1}", ["kg", "litros", "unidades", "metros", "cm"], key=f"unidad_ins_{i}")
            fecha = st.date_input(f"Fecha Insumo #{i+1}", key=f"fecha_ins_{i}")

            insumos.append({
                "Nombre": nombre,
                "Cantidad": cantidad,
                "Unidad": unidad,
                "Fecha": fecha.strftime("%d/%m/%Y")
            })

        if st.button("Guardar Insumos"):
            for item in insumos:
                save_to_sheet_insumos(item)
            st.success("Insumos guardados correctamente ✨")

        # --- Historial ---
        st.subheader("📜 Historial de Insumos")
        st.dataframe(df_insumos)

        # --- Reporte Predictivo ---
        st.subheader("📈 Reporte Predictivo")
        if not df_insumos.empty:
            df_insumos['Cantidad'] = df_insumos['Cantidad'].astype(float)
            resumen = df_insumos.groupby('Nombre')['Cantidad'].sum().reset_index()
            st.bar_chart(resumen.set_index('Nombre'))
        else:
            st.info("Aún no hay datos para generar un reporte.")


    # --- TAB 3: Gestión de Materiales ---
    with tab3:
        st.subheader("🔧 Agregar o Eliminar Materiales del Catálogo")
        st.markdown("### ➕ Agregar Nuevo Material")
        with st.form("form_agregar_material"):
            nuevo_codigo = st.text_input("Código del material")
            nueva_descripcion = st.text_input("Descripción")
            nuevo_tipo = st.selectbox("Tipo", ["MATERIA PRIMA", "INSUMO"])
            nueva_unidad = st.text_input("Unidad (kg, litros, un, etc.)")
            nueva_planta = st.selectbox("Planta", sorted(materiales_catalogo['planta'].unique()))
            submitted_agregar = st.form_submit_button("Agregar Material")
            if submitted_agregar:
                if nuevo_codigo and nueva_descripcion:
                    nuevo_material = {
                        'codigo': nuevo_codigo.strip(),
                        'descripcion': nueva_descripcion.strip(),
                        'tipo': nuevo_tipo,
                        'unidad': nueva_unidad.strip() if nueva_unidad else 'N/A',
                        'planta': nueva_planta
                    }
                    if nuevo_codigo in materiales_catalogo['codigo'].values:
                        st.warning("⚠️ Ya existe un material con ese código.")
                    else:
                        materiales_catalogo.loc[len(materiales_catalogo)] = nuevo_material
                        st.success(f"✅ Material '{nueva_descripcion}' agregado correctamente.")
                else:
                    st.error("❌ Completá al menos el código y la descripción del material.")

        st.markdown("---")
        st.markdown("### 🗑️ Eliminar Material del Catalogo (no elimina dato cargado)")
        lista_descripciones = sorted(materiales_catalogo['descripcion'].unique())
        material_a_borrar = st.selectbox("Seleccioná el material a eliminar", options=["(Seleccionar)"] + lista_descripciones)
        if material_a_borrar != "(Seleccionar)":
            st.warning(f"⚠️ Vas a eliminar el material: **{material_a_borrar}**. Esta acción no se puede deshacer.")
            confirmar = st.text_input("Escribí 'ELIMINAR' para confirmar la eliminación:")
            if st.button("Eliminar Material"):
                if confirmar.strip().upper() == "ELIMINAR":
                    materiales_catalogo = materiales_catalogo[materiales_catalogo['descripcion'] != material_a_borrar]
                    st.success(f"🗑️ Material '{material_a_borrar}' eliminado correctamente.")
                    st.rerun()
                else:
                    st.error("❌ Tenés que escribir 'ELIMINAR' para confirmar.")

    # --- TAB 4: Catálogo Actualizado ---
    with tab4:
        st.subheader("📋 Catálogo Actualizado de Materiales")
        st.dataframe(materiales_catalogo, use_container_width=True)

except Exception as e:
    st.error("Ocurrió un error.")
    st.error(f"Detalle: {e}")
