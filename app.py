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
import json

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Control de Stock")
st.title('Sistema de Control de Stock con Google Sheets')

# --- Conexión a Google Sheets ---
@st.cache_resource
def conectar_google_client():
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
    # st.success("Cliente Google Autorizado ✅") # Comentado para limpiar interfaz
    return client

def cargar_y_procesar_datos(client):
    if client is None:
        return pd.DataFrame()

    try:
        sheet = client.open("Base de Datos Fábrica").sheet1
        data = sheet.get_all_values()
        
        if not data:
            return pd.DataFrame()
            
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
    except Exception as e:
        st.warning(f"Error al leer Google Sheets: {e}")
        return pd.DataFrame()

    # Normalizamos columnas
    df.columns = [c.lower().strip() for c in df.columns]
    required_cols_db = ['fecha_hora', 'cantidad', 'material_codigo']
    
    if not df.empty and all(col in df.columns for col in required_cols_db):
        # Guardamos una copia para debug
        filas_totales = len(df)
        
        # 1. Limpieza de Fechas: Intentamos formato ISO primero, luego día/mes
        df['fecha_hora'] = pd.to_datetime(df['fecha_hora'], format='mixed', dayfirst=True, errors='coerce')
        
        # 2. Limpieza Cantidad
        df['cantidad'] = df['cantidad'].astype(str).str.replace(',', '.', regex=False)
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce')
        
        if 'planta' not in df.columns:
            df['planta'] = 'N/A'
            
        # 3. Eliminar nulos
        df_clean = df.dropna(subset=['fecha_hora', 'cantidad', 'material_codigo']).copy()
        
        # DEBUG: Si se borraron filas, avisar (puede ser útil verlo en consola)
        filas_borradas = filas_totales - len(df_clean)
        if filas_borradas > 0:
            print(f"⚠️ OJO: Se descartaron {filas_borradas} filas por formato incorrecto.")
            
        # 4. Ordenar
        df_clean = df_clean.sort_values(by='fecha_hora', ascending=True)
        return df_clean
        
    return df

def guardar_dato_gsheet(client, nuevo_dato):
    if client is None:
        return False

    try:
        sheet = client.open("Base de Datos Fábrica").sheet1
        
        # Verificar si faltan encabezados
        if not sheet.acell('A1').value:
            sheet.append_row(['material_codigo', 'fecha_hora', 'cantidad', 'planta'])
            time.sleep(1)

        # Sanitizar cantidad
        cant_raw = nuevo_dato['cantidad']
        if isinstance(cant_raw, list):
            cant_final = float(cant_raw[0])
        else:
            cant_final = float(cant_raw)
            
        # --- CAMBIO CLAVE: FORMATO ISO (Año-Mes-Día) ---
        # Esto evita que 10/12 se confunda con 12/10
        fecha_iso = nuevo_dato['fecha_hora'].strftime("%Y-%m-%d %H:%M:%S")
        
        fila = [
            str(nuevo_dato['material_descripcion']),
            fecha_iso, # Usamos formato universal
            cant_final,
            str(nuevo_dato['planta'])
        ]
        
        sheet.append_row(fila)
        return True
        
    except Exception as e:
        st.error(f"Error al guardar '{nuevo_dato['material_descripcion']}': {e}")
        return False

def calcular_consumo_diario(df_historial):
    if len(df_historial) < 2:
        return 0
    # Aseguramos orden cronológico para el cálculo
    df = df_historial.sort_values('fecha_hora').copy()
    df = df.dropna(subset=['cantidad'])
    
    if len(df) < 2: return 0
    
    df['Consumo'] = df['cantidad'].diff(-1) * -1
    df['Dias'] = df['fecha_hora'].diff(-1).dt.total_seconds().abs() / (24 * 3600)
    
    df_consumo = df[df['Consumo'] > 0]
    
    if df_consumo.empty or df_consumo['Dias'].sum() == 0:
        return 0
        
    return df_consumo['Consumo'].sum() / df_consumo['Dias'].sum()

# --- Catálogo Completo ---
# (Mantenemos tu catálogo original)
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

# --- Interfaz Principal ---
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

    # --- TAB 1: Materias Primas ---
    with tab1:
        st.subheader("Carga Masiva de Materias Primas")
        materias_primas_cat = materiales_catalogo[materiales_catalogo['tipo']=='MATERIA PRIMA']
        df_materias = materias_primas_cat[['descripcion','planta']].copy()
        df_materias['Cantidad (kg)'] = None

        # Editor con Configuración Numérica Estricta
        data_materias = st.data_editor(
            df_materias,
            num_rows="fixed",
            use_container_width=True,
            key="editor_materias",
            column_config={
                "Cantidad (kg)": st.column_config.NumberColumn(
                    "Cantidad (kg)",
                    help="Ingresá la cantidad en kg",
                    min_value=0,
                    step=0.1,
                    format="%.2f"
                )
            }
        )
        
        # Botón con Lógica de Espera (Loop Completo -> Rerun)
        if st.button("💾 Guardar todas las Materias Primas"):
            filas_guardadas = 0
            with st.spinner("Guardando en la nube..."):
                for _, fila in data_materias.iterrows():
                    if pd.isna(fila["Cantidad (kg)"]) or fila["Cantidad (kg)"] == "":
                        continue
                    
                    nuevo_dato = {
                        "material_descripcion": fila["descripcion"],
                        "cantidad": fila["Cantidad (kg)"],
                        "fecha_hora": datetime.now(),
                        "planta": fila["planta"]
                    }
                    if guardar_dato_gsheet(gspread_client, nuevo_dato):
                        filas_guardadas += 1
            
            if filas_guardadas > 0:
                st.success(f"✅ Se guardaron {filas_guardadas} movimientos.")
                st.cache_resource.clear()
                time.sleep(2)
                st.rerun()
            else:
                st.warning("No ingresaste cantidades para guardar.")

        # Reporte y Alertas
        st.markdown("---")
        st.subheader("📊 Reportes de Stock")
        df_stock = cargar_y_procesar_datos(gspread_client)
        
        if not df_stock.empty:
            reporte_mp = []
            for desc in materias_primas_cat['descripcion']:
                # Ordenar historial para asegurar que iloc[-1] sea el último real
                df_hist = df_stock[df_stock['material_codigo']==desc].sort_values('fecha_hora')
                
                ultimo_stock = df_hist['cantidad'].iloc[-1] if not df_hist.empty else 0
                consumo = calcular_consumo_diario(df_hist)
                dias_rest = ultimo_stock/consumo if consumo>0 else np.inf
                fecha_agot = (datetime.now()+timedelta(days=dias_rest)).strftime('%Y-%m-%d') if dias_rest!=np.inf else "Sin Consumo"
                row_cat = materias_primas_cat[materias_primas_cat['descripcion']==desc].iloc[0]
                reporte_mp.append({
                    'Código': row_cat['codigo'],
                    'Descripción': desc,
                    'Planta': row_cat['planta'],
                    'Último Stock': ultimo_stock,
                    'Unidad': row_cat['unidad'],
                    'Consumo Diario Prom.': round(consumo,2),
                    'Días Restantes': dias_rest,
                    'Fecha Agotamiento': fecha_agot
                })
            
            df_reporte_mp = pd.DataFrame(reporte_mp)
            
            # Display visual
            df_display = df_reporte_mp.copy()
            df_display['Días Restantes'] = df_display['Días Restantes'].apply(lambda x: "Sin Consumo" if x==np.inf else round(x,1))
            st.dataframe(df_display, use_container_width=True)

            # Alertas
            alertas_num = df_reporte_mp[df_reporte_mp['Días Restantes'] != np.inf].copy()
            alertas_num = alertas_num[alertas_num['Días Restantes'] <= 15]
            if not alertas_num.empty:
                st.warning("⚠️ Alertas de Stock Bajo (< 15 días)")
                st.dataframe(alertas_num[['Código','Descripción','Planta','Días Restantes','Unidad']])
        else:
            st.info("No hay datos cargados en el historial todavía.")

        st.subheader("📖 Historial Reciente")
        if not df_stock.empty:
            st.dataframe(df_stock[df_stock['material_codigo'].isin(materias_primas_cat['descripcion'])].sort_values('fecha_hora',ascending=False).head(50), use_container_width=True)

    # --- TAB 2: Insumos ---
    with tab2:
        st.subheader("Carga Masiva de Insumos")
        insumos_cat = materiales_catalogo[materiales_catalogo['tipo']=='INSUMO']
        df_insumos = insumos_cat[['descripcion','planta','unidad']].copy()
        df_insumos['Cantidad'] = None
        
        # Editor con Configuración Numérica Estricta
        data_insumos = st.data_editor(
            df_insumos, 
            num_rows="fixed", 
            use_container_width=True, 
            key="editor_insumos",
            column_config={
                "Cantidad": st.column_config.NumberColumn(
                    "Cantidad",
                    help="Ingresá la cantidad",
                    min_value=0,
                    step=1,
                    format="%d"
                )
            }
        )
        
        if st.button("💾 Guardar todos los Insumos"):
            filas_guardadas = 0
            with st.spinner("Guardando en la nube..."):
                for _, fila in data_insumos.iterrows():
                    if pd.isna(fila["Cantidad"]) or fila["Cantidad"] == "":
                        continue
                    nuevo_dato = {
                        "material_descripcion": fila["descripcion"],
                        "cantidad": fila["Cantidad"],
                        "fecha_hora": datetime.now(),
                        "planta": fila["planta"]
                    }
                    if guardar_dato_gsheet(gspread_client, nuevo_dato):
                        filas_guardadas += 1
            
            if filas_guardadas > 0:
                st.success(f"✅ Se guardaron {filas_guardadas} insumos.")
                st.cache_resource.clear()
                time.sleep(2)
                st.rerun()
            else:
                st.warning("No ingresaste cantidades.")

        # Reporte Insumos
        st.markdown("---")
        st.subheader("📊 Reportes de Stock")
        df_stock = cargar_y_procesar_datos(gspread_client) # Recargamos por seguridad
        if not df_stock.empty:
            reporte_ins = []
            for desc in insumos_cat['descripcion']:
                df_hist = df_stock[df_stock['material_codigo']==desc].sort_values('fecha_hora')
                ultimo_stock = df_hist['cantidad'].iloc[-1] if not df_hist.empty else 0
                consumo = calcular_consumo_diario(df_hist)
                dias_rest = ultimo_stock/consumo if consumo>0 else np.inf
                fecha_agot = (datetime.now()+timedelta(days=dias_rest)).strftime('%Y-%m-%d') if dias_rest!=np.inf else "Sin Consumo"
                row_cat = insumos_cat[insumos_cat['descripcion']==desc].iloc[0]
                reporte_ins.append({
                    'Código': row_cat['codigo'],
                    'Descripción': desc,
                    'Planta': row_cat['planta'],
                    'Último Stock': ultimo_stock,
                    'Unidad': row_cat['unidad'],
                    'Consumo Diario Prom.': round(consumo,2),
                    'Días Restantes': dias_rest,
                    'Fecha Agotamiento': fecha_agot
                })
            df_reporte_ins = pd.DataFrame(reporte_ins)
            
            df_display = df_reporte_ins.copy()
            df_display['Días Restantes'] = df_display['Días Restantes'].apply(lambda x: "Sin Consumo" if x==np.inf else round(x,1))
            st.dataframe(df_display, use_container_width=True)

            alertas_num = df_reporte_ins[df_reporte_ins['Días Restantes'] != np.inf].copy()
            alertas_num = alertas_num[alertas_num['Días Restantes'] <= 30]
            
            if not alertas_num.empty:
                st.warning("⚠️ Alertas de Stock Bajo (< 30 días)")
                st.dataframe(alertas_num[['Código','Descripción','Planta','Días Restantes','Unidad']])
        
        st.subheader("📖 Historial Reciente")
        if not df_stock.empty:
            st.dataframe(df_stock[df_stock['material_codigo'].isin(insumos_cat['descripcion'])].sort_values('fecha_hora',ascending=False).head(50), use_container_width=True)

    # --- TAB 3: Gestión ---
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
                        st.success(f"✅ Material '{nueva_descripcion}' agregado.")
                else:
                    st.error("❌ Completá al menos código y descripción.")

        st.markdown("---")
        st.markdown("### 🗑️ Eliminar Material del Catálogo (Local)")
        lista_descripciones = sorted(materiales_catalogo['descripcion'].unique())
        material_a_borrar = st.selectbox("Seleccioná el material a eliminar", options=["(Seleccionar)"] + lista_descripciones)
        if material_a_borrar != "(Seleccionar)":
            st.warning(f"⚠️ Vas a eliminar: **{material_a_borrar}**.")
            confirmar = st.text_input("Escribí 'ELIMINAR' para confirmar:")
            if st.button("Eliminar Material"):
                if confirmar.strip().upper() == "ELIMINAR":
                    materiales_catalogo = materiales_catalogo[materiales_catalogo['descripcion'] != material_a_borrar]
                    st.success(f"🗑️ Material eliminado.")
                    st.rerun()

    # --- TAB 4: Catálogo ---
    with tab4:
        st.subheader("📋 Catálogo Actualizado")
        st.dataframe(materiales_catalogo, use_container_width=True)

except Exception as e:
    st.error("Ocurrió un error inesperado en la aplicación.")
    st.error(f"Detalle: {e}")
    
    # --- ZONA DE DIAGNÓSTICO (Pegar esto al final del bloque try principal) ---
    st.markdown("---")
    with st.expander("🕵️ Inspector de Datos (Usar si no actualiza)"):
        col_debug_1, col_debug_2 = st.columns([1, 4])
        with col_debug_1:
            if st.button("🔄 Forzar Recarga"):
                st.cache_resource.clear()
                st.rerun()
        with col_debug_2:
            st.info("Si los datos no se actualizan, apretá el botón 'Forzar Recarga'.")
            
        st.write("### Datos Crudos en Google Sheets (Últimas 5 filas):")
        # Leemos directo sin procesar para ver si el dato llegó
        try:
            raw_sheet = gspread_client.open("Base de Datos Fábrica").sheet1
            raw_data = raw_sheet.get_all_values()
            st.table(raw_data[-5:] if len(raw_data) > 5 else raw_data)
        except:
            st.write("No se pudo conectar para ver datos crudos.")