import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import time # Importamos time para la pausa

# --- Configuración de la Página ---
st.set_page_config(layout="wide")
st.title('Sistema de Control de Stock con Google Sheets')

# --- Conexión a Google Sheets (con caché para la conexión) ---
@st.cache_resource
def conectar_gsheet():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    if os.path.exists('client_secret.json'): # Lógica para tu PC
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
                # Forzar la aprobación del usuario cada vez puede ayudar con tokens corruptos
                creds = flow.run_local_server(port=0, prompt='consent')
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    else: # Lógica para la nube (Streamlit Cloud)
        creds_dict = st.secrets["gcp_secret"]
        # Usar la estructura correcta del secret (installed o web)
        creds_key = "installed" if "installed" in creds_dict else "web"
        if creds_key in creds_dict:
             creds = Credentials.from_authorized_user_info(info=creds_dict[creds_key], scopes=SCOPES)
        else:
             try:
                 creds = Credentials.from_authorized_user_info(info=creds_dict, scopes=SCOPES)
             except KeyError as e:
                  st.error(f"Error al leer secrets: Falta la clave {e}. Asegúrate de que el formato TOML sea correcto.")
                  st.stop()

    if creds is None:
        st.error("No se pudieron obtener las credenciales de Google.")
        st.stop()

    client = gspread.authorize(creds)
    try:
        sheet = client.open("Base de Datos Fábrica").sheet1
        print("Conexión a Google Sheets establecida.") # Mensaje para depuración
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Error: No se encontró la hoja de cálculo 'Base de Datos Fábrica'. Verifica el nombre.")
        st.stop() # Detiene la ejecución si no encuentra la hoja
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets o abrir la hoja: {e}")
        st.stop() # Detiene si hay otro error de conexión


# --- Funciones de Datos ---
# --- FUNCIÓN CORREGIDA PARA LEER FECHAS MIXTAS ---
def cargar_y_procesar_datos(_sheet):
    """Carga y procesa datos, manejando múltiples formatos de fecha."""
    if _sheet is None:
        return pd.DataFrame()

    print("Cargando datos frescos desde Google Sheets...")
    try:
        _sheet = _sheet.spreadsheet.get_worksheet(0)
        records = _sheet.get_all_records()
    except Exception as e:
        st.warning(f"No se pudieron cargar los datos de GSheet: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    required_cols_db = ['fecha_hora', 'cantidad', 'material_codigo']
    
    if not df.empty and all(col in df.columns for col in required_cols_db):
        
        # --- CAMBIO CLAVE: LEEMOS AMBOS FORMATOS ---
        df['fecha_hora'] = df['fecha_hora'].astype(str).str.strip()
        
        # 1. Intentar leer el formato nuevo (DD/MM/YYYY HH:MM:SS)
        formato_nuevo = pd.to_datetime(df['fecha_hora'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        
        # 2. Intentar leer el formato viejo (auto-detectar YYYY-MM-DD HH:MM:SS)
        formato_viejo = pd.to_datetime(df['fecha_hora'], errors='coerce')
        
        # 3. Combinar los resultados. Donde falló el formato nuevo, usa el viejo.
        df['fecha_hora'] = formato_nuevo.fillna(formato_viejo)
        # --- FIN DEL CAMBIO ---

        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce')
        if 'planta' not in df.columns:
            df['planta'] = 'N/A'
        
        # 4. Eliminar solo las filas donde la fecha falló en AMBOS formatos
        df.dropna(subset=['fecha_hora', 'cantidad', 'material_codigo'], inplace=True)
        
        print(f"✅ {len(df)} registros cargados (Última fecha leída: {df['fecha_hora'].max()})")
    elif not df.empty:
         st.warning("Faltan columnas requeridas en la base de datos.")
    
    return df


def guardar_dato_gsheet(sheet, nuevo_dato):
    """Guarda el dato y fuerza la recarga."""
    if sheet is None:
        st.error("Error de conexión, no se pudo guardar el dato.")
        return

    fila = [
        str(nuevo_dato['material_descripcion']),
        nuevo_dato['fecha_hora'].strftime("%d/%m/%Y %H:%M:%S"), # Formato DD/MM/AAAA HH:MM:SS
        float(nuevo_dato['cantidad']),
        str(nuevo_dato['planta'])
    ]
    try:
        sheet.append_row(fila)
        st.success(f"¡Guardado! Actualizando vista...")
        st.cache_data.clear()
        st.cache_resource.clear()
        if 'df_stock_completo' in st.session_state:
            del st.session_state['df_stock_completo']
        if 'df_stock_historial' in st.session_state:
             del st.session_state['df_stock_historial']
        time.sleep(2)
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
    dias_totales = df_consumo['Dias'].sum()
    if dias_totales == 0:
        return 0
    return df_consumo['Consumo'].sum() / dias_totales

# --- Catálogo Completo y Corregido (Basado en tu última lista) ---
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

# --- Interfaz Gráfica de la Aplicación ---
try:
    gsheet_connection = conectar_gsheet() 

    if gsheet_connection is None:
        st.stop() 

    st.header('Cargar Nuevo Relevamiento de Stock')
    materias_primas_cat = materiales_catalogo[materiales_catalogo['tipo'] == 'MATERIA PRIMA']
    insumos_cat = materiales_catalogo[materiales_catalogo['tipo'] == 'INSUMO']

    tab1, tab2 = st.tabs(["Materias Primas", "Insumos"])
    with tab1:
        st.subheader('Cargar Stock de Materia Prima')
        opciones_mp = materias_primas_cat['descripcion'].unique().tolist()
        seleccion_mp = st.selectbox('Seleccione la Materia Prima:', options=opciones_mp, key='mp_select')
        cantidad_mp = st.number_input('Ingrese la Cantidad en kg:', min_value=0.0, format="%.2f", key='mp_kg')
        if st.button('Guardar Materia Prima', key='mp_save'):
            planta_seleccionada = materias_primas_cat[materias_primas_cat['descripcion'] == seleccion_mp].iloc[0]['planta']
            nuevo_relevamiento = {'material_descripcion': seleccion_mp, 'fecha_hora': datetime.now(), 'cantidad': cantidad_mp, 'planta': planta_seleccionada}
            guardar_dato_gsheet(gsheet_connection, nuevo_relevamiento) 
    with tab2:
        st.subheader('Cargar Stock de Insumo')
        opciones_in = insumos_cat['descripcion'].unique().tolist()
        seleccion_in = st.selectbox('Seleccione el Insumo:', options=opciones_in, key='in_select')
        
        unidad_seleccionada = 'un'
        planta_seleccionada_in = 'N/A'
        if seleccion_in:
            info_df = insumos_cat[insumos_cat['descripcion'] == seleccion_in]
            if not info_df.empty:
                unidad_seleccionada = info_df.iloc[0]['unidad']
                planta_seleccionada_in = info_df.iloc[0]['planta']
        cantidad_in = st.number_input(f'Ingrese la Cantidad en {unidad_seleccionada}:', min_value=0.0, format="%.2f", key='in_kg')
        if st.button('Guardar Insumo', key='in_save'):
            nuevo_relevamiento = {'material_descripcion': seleccion_in, 'fecha_hora': datetime.now(), 'cantidad': cantidad_in, 'planta': planta_seleccionada_in}
            guardar_dato_gsheet(gsheet_connection, nuevo_relevamiento)

    st.divider()
    st.header('Análisis y Reportes de Stock')
    
    # --- Leemos los datos UNA VEZ para los reportes predictivos ---
    df_stock_para_reportes = cargar_y_procesar_datos(gsheet_connection)

    def generar_reporte_predictivo(catalogo_df, df_historico):
        reporte_data = []
        if 'material_codigo' not in df_historico.columns and not df_historico.empty:
             st.error("Error: La columna 'material_codigo' no se encontró en los datos cargados.")
             return pd.DataFrame() 

        for desc in catalogo_df['descripcion'].unique():
            row_cat = catalogo_df[catalogo_df['descripcion'] == desc].iloc[0]
            df_material_hist = df_historico[df_historico['material_codigo'] == desc] if not df_historico.empty else pd.DataFrame()

            ultimo_stock = 0
            consumo_diario = 0
            dias_restantes = np.inf
            fecha_agotamiento = 'N/A'

            if not df_material_hist.empty:
                df_material_hist_sorted = df_material_hist.sort_values('fecha_hora')
                ultimo_stock = df_material_hist_sorted.iloc[-1]['cantidad']
                consumo_diario = calcular_consumo_diario(df_material_hist_sorted)
                dias_restantes = ultimo_stock / consumo_diario if consumo_diario > 0 else np.inf
                if dias_restantes > 0 and dias_restantes != np.inf and pd.notna(dias_restantes):
                    fecha_dt = datetime.now() + timedelta(days=dias_restantes)
                    fecha_agotamiento = fecha_dt.strftime('%Y-%m-%d')
                elif dias_restantes == np.inf:
                    fecha_agotamiento = "Sin Consumo" # Corregido

            reporte_data.append({
                'Código': row_cat['codigo'],
                'Descripción': desc,
                'Planta': row_cat['planta'],
                'Último Stock': ultimo_stock,
                'Unidad': row_cat['unidad'],
                'Consumo Diario Prom.': round(consumo_diario, 2),
                'Días Restantes': dias_restantes, # Mantenemos el valor numérico
                'Fecha Agotamiento': fecha_agotamiento
            })
        return pd.DataFrame(reporte_data)

    st.subheader('📊 Reportes Predictivos')
    
    lista_plantas = ['Mostrar Todo'] + sorted(list(materiales_catalogo['planta'].unique()))
    planta_seleccionada = st.selectbox('Filtrar por Planta:', options=lista_plantas)

    if planta_seleccionada == 'Mostrar Todo':
        catalogo_filtrado = materiales_catalogo
    else:
        catalogo_filtrado = materiales_catalogo[materiales_catalogo['planta'] == planta_seleccionada]

    df_reporte = generar_reporte_predictivo(catalogo_filtrado, df_stock_para_reportes) 
    
    if not df_reporte.empty:
        df_display = df_reporte.copy()
        def format_dias_restantes_str(value):
            if pd.isna(value): return "" 
            elif value == np.inf: return "Sin Consumo"
            elif isinstance(value, (int, float)): return str(round(value, 1))
            else: return str(value) 
        if 'Días Restantes' in df_display.columns:
            # --- CORRECCIÓN CLAVE ---
            # Forzamos toda la columna a ser de tipo 'object' (mixto) ANTES de aplicar
            df_display['Días Restantes'] = df_display['Días Restantes'].astype(object).apply(format_dias_restantes_str)

        st.dataframe(df_display)

        if 'Días Restantes' in df_reporte.columns:
            df_reporte['Días Restantes Num'] = pd.to_numeric(df_reporte['Días Restantes'], errors='coerce') 
            alertas = df_reporte[df_reporte['Días Restantes Num'].notna() &
                ( ((df_reporte['Planta'] == 'Materias Primas') & (df_reporte['Días Restantes Num'] <= 15)) |
                  ((df_reporte['Planta'] != 'Materias Primas') & (df_reporte['Días Restantes Num'] <= 30)) )
            ]
        else:
             alertas = pd.DataFrame() 
        
        if not alertas.empty:
            st.write('**⚠️ Alertas de Stock Bajo**')
            alertas_display = alertas.copy()
            alertas_display['Días Restantes'] = alertas_display['Días Restantes Num'].apply(lambda x: round(x, 1)) 
            st.dataframe(alertas_display[['Código', 'Descripción', 'Planta', 'Días Restantes', 'Unidad']])

    st.divider()

    st.subheader("📖 Historial Completo de la Base de Datos")
    # --- CAMBIO CLAVE: Volvemos a leer los datos justo antes de mostrar ---
    df_stock_historial = cargar_y_procesar_datos(gsheet_connection) 
    if not df_stock_historial.empty:
        st.dataframe(df_stock_historial.sort_values('fecha_hora', ascending=False))
    else:
        st.info("Aún no se han cargado datos en la hoja de cálculo.")

except Exception as e:
    st.error("Ocurrió un error.")
    st.error(f"Detalle: {e}")