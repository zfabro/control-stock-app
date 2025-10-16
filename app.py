import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import json

# --- Configuración de la Página ---
st.set_page_config(layout="wide")
st.title('Sistema de Control de Stock con Google Sheets')

# --- Conexión a Google Sheets con Lógica Dual (Local vs. Cloud) ---
@st.cache_resource
def conectar_gsheet():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    
    # --- LÓGICA DUAL (LA PARTE MÁS IMPORTANTE) ---
    # 1. Si está en Streamlit Cloud, lee los secrets que configuramos.
    if st.secrets.has_key("gcp_secret"):
        creds_dict = st.secrets["gcp_secret"]
        # El secret es de tipo "App de escritorio", por lo que usamos 'installed'
        if "installed" in creds_dict:
             creds_info = creds_dict["installed"]
        else: # O 'web' si se creó como app web
             creds_info = creds_dict["web"]

        creds = Credentials.from_authorized_user_info(info=creds_info, scopes=SCOPES)

    # 2. Si está en tu computadora (local), usa el flujo de siempre.
    else:
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    client = gspread.authorize(creds)
    # Reemplaza "Base de Datos Stock" con el nombre EXACTO de tu archivo en Google Sheets
    sheet = client.open("Base de Datos Stock").sheet1
    return sheet

# --- Funciones para leer y escribir en la hoja de cálculo ---
def cargar_datos_gsheet(sheet):
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def guardar_dato_gsheet(sheet, nuevo_dato):
    fila = [str(nuevo_dato['material_codigo']), str(nuevo_dato['fecha_hora']), float(nuevo_dato['cantidad'])]
    sheet.append_row(fila)

# --- Catálogo Completo de Materiales (77 ítems) ---
materiales_catalogo = pd.DataFrame([
    # Materias Primas (28)
    {'codigo': 'KYD 6200K', 'descripcion': 'Polipropileno', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LYD 6200K', 'descripcion': 'Polipropileno', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'KYD 6110K', 'descripcion': 'Homopolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': '1102K', 'descripcion': 'Homopolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'SYMBIOS 3102', 'descripcion': 'Terpolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'SYMBIOS 4102', 'descripcion': 'Terpolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'HT ES RFD 6140K', 'descripcion': 'Homopolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'HT ES RFD 6190K', 'descripcion': 'Homopolímero', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'HT ES SP340', 'descripcion': 'Random', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LLDPE 1630', 'descripcion': '1 - Hexeno', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': '1102T', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'XSD 6200T', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'AGILITY 7000', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'H103', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': '722', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'H301', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'HE150', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'H503', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LPD 230N', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'POLYETHYLENE 722', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'POLIAMIDA 1030B', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LLDPE 1613', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LDPE 208', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LDPE 207M', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LDPE 203M', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'RSGELHO66E 1666', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'ALC-30', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'LLDPE 1630 C1', 'descripcion': 'Materia Prima Genérica', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    # Insumos (49)
    {'codigo': 'PFD742-00/TD', 'descripcion': 'Diluyente', 'tipo': 'INSUMO', 'unidad': 'litros'},
    {'codigo': 'Dowanol', 'descripcion': 'Dowanol', 'tipo': 'INSUMO', 'unidad': 'litros'},
    {'codigo': '911114-C2', 'descripcion': 'Master Blanco', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '921020', 'descripcion': 'Master Perlado', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '1401577-S', 'descripcion': 'Master Amarillo K', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '151410-S', 'descripcion': 'Master Rojo', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '961515-C2', 'descripcion': 'Master Azul', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '961150-C2', 'descripcion': 'Master Celeste', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '1303342-S-C2', 'descripcion': 'Master Amarillo', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': 'SL 342', 'descripcion': 'Adhesivo laminadora', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': 'R405', 'descripcion': 'Catalizador', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '901300', 'descripcion': 'Antibloking', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '901213', 'descripcion': 'Antiestatico', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '400700-ST', 'descripcion': 'Matif', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': 'FM-250375', 'descripcion': 'Carbonato', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '400998-S', 'descripcion': 'Hoslip 15', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '1260 MT cristal', 'descripcion': 'Hilo 1260', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': '2520 AT cristal', 'descripcion': 'Hilo 2500', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Hilo Poliester', 'descripcion': 'Hilo Poliester', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Crepp Blanco', 'descripcion': 'Crepp Blanco', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Crepp Rojo', 'descripcion': 'Crepp Rojo', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Crepp Negro', 'descripcion': 'Crepp Negro', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Crepp Verde', 'descripcion': 'Crepp Verde', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Streecht', 'descripcion': 'Streecht', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Flejes Manual', 'descripcion': 'Flejes Manual', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Flejes semi-automatico', 'descripcion': 'Flejes semi-automatico', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Hebillas', 'descripcion': 'Hebillas', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Gas', 'descripcion': 'Gas', 'tipo': 'INSUMO', 'unidad': 'litros'},
    {'codigo': '5.3 EB', 'descripcion': 'Cinta Doble Faz', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Abrefácil', 'descripcion': 'Abrefácil', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Conos 3"', 'descripcion': 'Conos 3"', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Conos 4"', 'descripcion': 'Conos 4"', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Conos 6"', 'descripcion': 'Conos 6"', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Separadores (cartón)', 'descripcion': 'Separadores (cartón)', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Esquineros', 'descripcion': 'Esquineros', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Teflón Lamina s/ad 1m An', 'descripcion': 'Teflón Lamina s/ad 1m An', 'tipo': 'INSUMO', 'unidad': 'm'},
    {'codigo': 'Teflón Cinta c/ad 5 cm', 'descripcion': 'Teflón Cinta c/ad 5 cm', 'tipo': 'INSUMO', 'unidad': 'm'},
    {'codigo': 'Teflón Cinta c/ad 2,5 cm', 'descripcion': 'Teflón Cinta c/ad 2,5 cm', 'tipo': 'INSUMO', 'unidad': 'm'},
    {'codigo': 'Teflón Cinta c/ad 1,5 cm', 'descripcion': 'Teflón Cinta c/ad 1,5 cm', 'tipo': 'INSUMO', 'unidad': 'm'},
    {'codigo': '5m 4x0,15', 'descripcion': 'Resistencias 5mm Tarewa', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Ø1/4x38mm', 'descripcion': 'Resistencias 150W Máq.3', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Ø3/8x100mm', 'descripcion': 'Resistencias 100W Máq.4', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'DRx2 / UY1973', 'descripcion': 'Agujas GROZ-BECKERT', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': 'Pallet 100x120', 'descripcion': 'Pallet 100x120', 'tipo': 'INSUMO', 'unidad': 'un'},
    {'codigo': '911114-C1', 'descripcion': 'Master Blanco', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '961515-C1', 'descripcion': 'Master Azul', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '961150-C1', 'descripcion': 'Master Celeste', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '1303342-S-C1', 'descripcion': 'Master Amarillo', 'tipo': 'INSUMO', 'unidad': 'kg'},
    {'codigo': '1504724-S', 'descripcion': 'Master Rojo', 'tipo': 'INSUMO', 'unidad': 'kg'}
])
materias_primas = materiales_catalogo[materiales_catalogo['tipo'] == 'MATERIA PRIMA']
insumos = materiales_catalogo[materiales_catalogo['tipo'] == 'INSUMO']

# --- Interfaz Gráfica de la Aplicación ---
try:
    gsheet = conectar_gsheet()
    st.header('Cargar Nuevo Relevamiento de Stock')
    tab1, tab2 = st.tabs(["Materias Primas", "Insumos"])
    with tab1:
        st.subheader('Cargar Stock de Materia Prima')
        opciones_mp = [f"{row['codigo']} ({row['descripcion']})" for index, row in materias_primas.iterrows()]
        seleccion_mp = st.selectbox('Seleccione la Materia Prima:', options=opciones_mp, key='mp_select')
        cantidad_mp = st.number_input('Ingrese la Cantidad en kg:', min_value=0.0, format="%.2f", key='mp_kg')
        if st.button('Guardar Materia Prima', key='mp_save'):
            codigo = seleccion_mp.split(' ')[0]
            nuevo_relevamiento = {'material_codigo': codigo, 'fecha_hora': datetime.now(), 'cantidad': cantidad_mp}
            guardar_dato_gsheet(gsheet, nuevo_relevamiento)
            st.success(f'¡Guardado en Google Sheets! Stock de {cantidad_mp} kg para {codigo}.')
    with tab2:
        st.subheader('Cargar Stock de Insumo')
        opciones_in = [f"{row['codigo']} ({row['descripcion']})" for index, row in insumos.iterrows()]
        seleccion_in = st.selectbox('Seleccione el Insumo:', options=opciones_in, key='in_select')
        unidad_seleccionada = 'un'
        if seleccion_in:
            codigo_in = seleccion_in.split(' (')[0]
            unidad_df = insumos[insumos['codigo'] == codigo_in]
            if not unidad_df.empty:
                unidad_seleccionada = unidad_df.iloc[0]['unidad']
        cantidad_in = st.number_input(f'Ingrese la Cantidad en {unidad_seleccionada}:', min_value=0.0, format="%.2f", key='in_kg')
        if st.button('Guardar Insumo', key='in_save'):
            codigo = seleccion_in.split(' (')[0]
            nuevo_relevamiento = {'material_codigo': codigo, 'fecha_hora': datetime.now(), 'cantidad': cantidad_in}
            guardar_dato_gsheet(gsheet, nuevo_relevamiento)
            st.success(f'¡Guardado en Google Sheets! Stock de {cantidad_in} {unidad_seleccionada} para {codigo}.')
    st.divider()
    st.header('Reportes de Stock (desde Google Sheets)')
    df_stock_actual = cargar_datos_gsheet(gsheet)
    st.subheader("Datos Actuales en la Hoja de Cálculo")
    if not df_stock_actual.empty:
        st.dataframe(df_stock_actual)
    else:
        st.info("Aún no se han cargado datos en la hoja de cálculo.")
        st.info("La primera fila de tu Google Sheet debe tener los encabezados: material_codigo, fecha_hora, cantidad")
except Exception as e:
    st.error("Ocurrió un error al conectar con Google Sheets.")
    st.error(f"Detalle: {e}")
    st.info("Posibles causas: Revisa el formato de tus 'Secrets' en Streamlit Cloud, el nombre de tu Google Sheet en el código, o asegúrate de haber dado permisos en el navegador.")