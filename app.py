import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import gspread
# Estas son las librerías clave para el nuevo método de autenticación
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

# --- Configuración de la Página ---
st.set_page_config(layout="wide")
st.title('Sistema de Control de Stock con Google Sheets')

# --- Conexión a Google Sheets con Autenticación de Usuario (OAuth 2.0) ---
# Esta función se ejecutará una sola vez gracias al decorador @st.cache_resource
@st.cache_resource
def conectar_gsheet():
    """Conecta con Google Sheets usando el flujo OAuth 2.0.
    La primera vez, pedirá al usuario que inicie sesión en el navegador.
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    
    # El archivo token.json almacena las credenciales del usuario de forma segura.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales válidas, permite que el usuario inicie sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Carga el secreto desde el archivo que descargaste de Google Cloud
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            # Esto abrirá el navegador para que autorices la aplicación
            creds = flow.run_local_server(port=0)
        
        # Guarda las credenciales para la próxima vez que ejecutes la app
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    client = gspread.authorize(creds)
    
    # --- IMPORTANTE ---
    # Reemplaza "Base de Datos Stock" con el nombre EXACTO de tu archivo en Google Sheets
    sheet = client.open("Base de Datos Stock").sheet1
    return sheet

# --- Funciones para leer y escribir en la hoja de cálculo ---
def cargar_datos_gsheet(sheet):
    """Carga todos los datos de la hoja y los convierte a un DataFrame."""
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def guardar_dato_gsheet(sheet, nuevo_dato):
    """Añade una nueva fila de datos al final de la hoja."""
    # Convierte el diccionario a una lista para que gspread lo pueda añadir
    fila = [str(nuevo_dato['material_codigo']), str(nuevo_dato['fecha_hora']), float(nuevo_dato['cantidad'])]
    sheet.append_row(fila)

# --- Catálogo de Materiales ---
# ¡AQUÍ DEBES PEGAR TU LISTA COMPLETA DE 77 ÍTEMS!
materiales_catalogo = pd.DataFrame([
    # Ejemplo:
    {'codigo': 'KYD 6200K', 'descripcion': 'Polipropileno', 'tipo': 'MATERIA PRIMA', 'unidad': 'kg'},
    {'codigo': 'PFD742-00-TD', 'descripcion': 'Diluyente', 'tipo': 'INSUMO', 'unidad': 'litros'},
    # ... (pega aquí la lista completa que te pasé antes) ...
])
materias_primas = materiales_catalogo[materiales_catalogo['tipo'] == 'MATERIA PRIMA']
insumos = materiales_catalogo[materiales_catalogo['tipo'] == 'INSUMO']


# --- Interfaz Gráfica de la Aplicación ---
try:
    # Intenta conectar al iniciar la app
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

except FileNotFoundError:
    st.error("Error: No se encontró el archivo 'client_secret.json'.")
    st.error("Asegúrate de que el archivo que descargaste de Google Cloud esté en la misma carpeta que 'app.py' y se llame exactamente 'client_secret.json'.")
except Exception as e:
    st.error(f"Ocurrió un error durante la autenticación o la conexión a Google Sheets.")
    st.error(f"Detalle del error: {e}")
    st.info("Posibles soluciones: Asegúrate de haber aceptado los permisos en el navegador. Revisa que el nombre de tu hoja de Google Sheet en el código sea correcto.")