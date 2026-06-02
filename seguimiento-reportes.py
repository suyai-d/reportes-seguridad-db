import streamlit as st
import pandas as pd
import plotly.express as px
import time
import requests
import json
import base64
from io import StringIO
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Seguimiento de Colaboradores", layout="wide", page_icon="📊")

st.title("📊 Tablero de Seguimiento de Colaboradores")
st.markdown("Monitoreo de actividad, accesos y uso de herramientas en base a los registros del repositorio.")

# Credenciales del repositorio
USER = "suyai-d"
REPO = "reportes-seguridad-db"
BRANCH = "main"

# Verificar si existe un Token en los secretos para persistencia remota (Streamlit Cloud)
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)

# --- FUNCIONES DE CARGA Y ESCRITURA ---

@st.cache_data(ttl=600)
def cargar_datos_csv(nombre_archivo, timestamp_evita_cache):
    """Descarga de manera directa y optimizada los archivos CSV desde la API de contenidos de GitHub"""
    url = f"https://api.github.com/repos/{USER}/{REPO}/contents/{nombre_archivo}?ref={BRANCH}"
    headers = {
        "User-Agent": "Streamlit-App",
        "Accept": "application/vnd.github.v3.raw",
        "Cache-Control": "no-cache"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return pd.read_csv(StringIO(res.text), on_bad_lines='skip')
        else:
            raise Exception()
    except:
        # PLAN B: Canal tradicional por URL RAW si falla la API
        try:
            url_raw = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{nombre_archivo}?nocache={timestamp_evita_cache}"
            return pd.read_csv(url_raw, on_bad_lines='skip')
        except:
            return pd.DataFrame()

def guardar_registro_manual(nueva_fila_df, nombre_archivo, timestamp_cache):
    """Guarda el nuevo registro manual. Soporta escritura local y remota vía API de GitHub"""
    if GITHUB_TOKEN:
        url_api = f"https://api.github.com/repos/{USER}/{REPO}/contents/{nombre_archivo}"
        headers_json = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        res = requests.get(url_api, headers=headers_json)
        sha = None
        df_existente = pd.DataFrame()
        
        if res.status_code == 200:
            datos_archivo = res.json()
            sha = datos_archivo['sha']
            contenido_crudo = base64.b64decode(datos_archivo['content']).decode('utf-8')
            df_existente = pd.read_csv(StringIO(contenido_crudo), on_bad_lines='skip')
        
        df_total = pd.concat([df_existente, nueva_fila_df], ignore_index=True)
        csv_string = df_total.to_csv(index=False)
        contenido_base64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": f"🤖 Registro personalizado de campo - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "content": contenido_base64,
            "branch": BRANCH
        }
        if sha:
            payload["sha"] = sha
            
        res_put = requests.put(url_api, headers=headers_json, data=json.dumps(payload))
        return res_put.status_code in [200, 201]
    else:
        try:
            df_existente = pd.read_csv(nombre_archivo, on_bad_lines='skip')
        except:
            df_existente = pd.DataFrame(columns=nueva_fila_df.columns)
            
        df_total = pd.concat([df_existente, nueva_fila_df], ignore_index=True)
        df_total.to_csv(nombre_archivo, index=False)
        return True

# Control de tiempo para evitar cache persistente en actualizaciones
reloader = int(time.time() / 60)

# Carga de catálogos e información estructural
df_usuarios = cargar_datos_csv("usuarios_permitidos.csv", reloader)
df_orgs = cargar_datos_csv("Orgs CONCI.csv", reloader)

# --- CONFIGURACIÓN DE PESTAÑAS ---
tab1, tab2 = st.tabs(["📝 Registro Personalizado", "📊 Tablero de Control y Seguimiento"])

# ==========================================
# PESTAÑA 1: REGISTRO MANUAL DE CAMPO
# ==========================================
with tab1:
    st.header("📝 Ingreso de Registros Personalizados")
    st.markdown("Asentá las actividades, ensayos y visitas presenciales que realizás con las cuentas de forma externa a los reportes automáticos.")
    
    if not df_orgs.empty and 'Organización' in df_orgs.columns:
        lista_clientes = sorted(df_orgs['Organización'].dropna().unique().tolist())
    else:
        lista_clientes = ["ADJ SRL", "DE GIORGIO SA", "H&H Outfitters SA", "Schiaroli Horacio Ramon"]
        
    if not df_usuarios.empty and 'usuarios' in df_usuarios.columns:
        lista_usuarios_x = sorted(df_usuarios['usuarios'].dropna().unique().tolist())
    else:
        lista_usuarios_x = ["X225841", "X090165", "X635152"]

    st.markdown("---")
    
    with st.form("formulario_registro_manual", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            fecha_sel = st.date_input("Fecha de la Actividad", datetime.now().date())
            cliente_sel = st.selectbox("Razón Social del Cliente (Catálogo Conci)", lista_clientes)
            usuario_sel = st.selectbox("Identificador del Colaborador (Usuario X)", lista_usuarios_x)
            
        with col_f2:
            tipo_registro_sel = st.selectbox(
                "Tipo de Registro / Actividad",
                ["Visita / Ensayo AA", "Reporte 360", "Reporte personalizado", "Reunión / Capacitación individual"]
            )
            observaciones_sel = st.text_area("Observaciones del Registro", placeholder="Escribí los detalles del acuerdo, novedades de la visita o estado de la máquina...")
            
        st.markdown(" ")
        boton_guardar = st.form_submit_button("💾 Guardar Registro de Actividad", use_container_width=True)
        
        if boton_guardar:
            nueva_actividad = pd.DataFrame([{
                "fecha": fecha_sel.strftime("%d/%m/%Y"),
                "razon_social": cliente_sel,
                "usuario_x": usuario_sel,
                "registro": tipo_registro_sel,
                "tiempo": 1.0,
                "observaciones": observaciones_sel if observaciones_sel else "Sin observaciones"
            }])
            
            with st.spinner("Guardando información en la base de datos centralizada..."):
                if guardar_registro_manual(nueva_actividad, "registro_personalizado.csv", reloader):
                    st.success("🎉 ¡Registro almacenado correctamente! Podés visualizarlo ingresando a la pestaña del Tablero.")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Hubo un problema al procesar el archivo. Verificá los accesos a tu repositorio.")

# ==========================================
# PESTAÑA 2: TABLERO DE CONTROL UNIFICADO
# ==========================================
with tab2:
    st.sidebar.header("🔄 Control de Datos")
    if st.sidebar.button("🔄 Actualizar Datos Ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    df_auto_crudo = cargar_datos_csv("registro_actividad.csv", reloader)
    df_manual_crudo = cargar_datos_csv("registro_personalizado.csv", reloader)

    if not df_auto_crudo.empty and not df_usuarios.empty:
        # --- PROCESAMIENTO CANAL AUTOMÁTICO ---
        df_auto_crudo['fecha_hora'] = pd.to_datetime(df_auto_crudo['fecha_hora'], errors='coerce')
        df_auto_crudo = df_auto_crudo.dropna(subset=['fecha_hora'])
        
        df_auto_m = pd.merge(df_auto_crudo, df_usuarios, left_on='usuario', right_on='usuarios', how='left')
        df_auto_m['nombre'] = df_auto_m['nombre'].fillna(df_auto_m['usuario'])
        df_auto_m['Origen'] = 'Automático (Uso de Apps)'
        
        df_auto_unificado = df_auto_m[['fecha_hora', 'nombre', 'accion', 'cliente', 'Origen']].copy()
        
        # --- PROCESAMIENTO CANAL MANUAL ---
        if not df_manual_crudo.empty and len(df_manual_crudo) > 0:
            df_manual_crudo['fecha_hora'] = pd.to_datetime(df_manual_crudo['fecha'], format="%d/%m/%Y", errors='coerce')
            df_manual_crudo = df_manual_crudo.dropna(subset=['fecha_hora'])
            
            df_manual_m = pd.merge(df_manual_crudo, df_usuarios, left_on='usuario_x', right_on='usuarios', how='left')
            df_manual_m['nombre'] = df_manual_m['nombre'].fillna(df_manual_m['usuario_x'])
            
            df_manual_m = df_manual_m.rename(columns={
                'registro': 'accion',
                'razon_social': 'cliente'
            })
            df_manual_m['Origen'] = 'Manual (Registros Campo)'
            df_manual_unificado = df_manual_m[['fecha_hora', 'nombre', 'accion', 'cliente', 'Origen']].copy()
            
            df = pd.concat([df_auto_unificado, df_manual_unificado], ignore_index=True)
        else:
            df = df_auto_unificado

        # --- BLINDAJE ULTRA-ESTRICTO DE LA COLUMNA CLIENTE ---
        # Convertimos todo a string y limpiamos nulos ANTES de llamar a sorted()
        df['cliente'] = df['cliente'].fillna('No especificado').astype(str).str.strip()
        df['cliente'] = df['cliente'].replace(['', 'nan', 'N/A', 'None'], 'No especificado')

        # --- FILTROS DE LA SEGUNDA PESTAÑA ---
        st.sidebar.markdown("---")
        st.sidebar.header("Filtros de Análisis")
        
        min_fecha = df['fecha_hora'].min().date()
        max_fecha = df['fecha_hora'].max().date()
        f_inicio, f_final = st.sidebar.date_input("Rango de fechas", [min_fecha, max_fecha], min_value=min_fecha, max_value=max_fecha)
        
        usuarios_disponibles = sorted(df['nombre'].unique())
        usuarios_seleccionados = st.sidebar.multiselect("Seleccionar Colaboradores", usuarios_disponibles, default=usuarios_disponibles)
        
        clientes_disponibles = sorted(df['cliente'].unique())
        clientes_seleccionados = st.sidebar.multiselect("Seleccionar Clientes", clientes_disponibles, default=clientes_disponibles)
        
        origenes_disponibles = sorted(df['Origen'].unique())
        origenes_seleccionados = st.sidebar.multiselect("Origen de la Actividad", origenes_disponibles, default=origenes_disponibles)

        # Filtrado del dataframe combinado
        df_filtrado = df[
            (df['fecha_hora'].dt.date >= f_inicio) & 
            (df['fecha_hora'].dt.date <= f_final) & 
            (df['nombre'].isin(usuarios_seleccionados)) &
            (df['cliente'].isin(clientes_seleccionados)) &
            (df['Origen'].isin(origenes_seleccionados))
        ]

        # 4. Métricas Principales (KPIs)
        total_acciones = len(df_filtrado)
        usuarios_activos = df_filtrado['nombre'].nunique()
        exportaciones = len(df_filtrado[df_filtrado['accion'].str.contains('Exportó|PDF|Reporte|Visita|Reunión', na=False, case=False)])
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Interacciones", f"{total_acciones}")
        kpi2.metric("Colaboradores Activos", f"{usuarios_activos}")
        kpi3.metric("Entregas y Gestiones Realizadas", f"{exportaciones}")
        
        st.markdown("---")
        
        # 5. Visualizaciones y Gráficos Generales
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📌 Actividad por Colaborador")
            actividad_usuario = df_filtrado['nombre'].value_counts().reset_index()
            actividad_usuario.columns = ['Colaborador', 'Cantidad de Acciones']
            
            fig_bar = px.bar(
                actividad_usuario, 
                x='Cantidad de Acciones', 
                y='Colaborador', 
                orientation='h',
                color='Cantidad de Acciones',
                color_continuous_scale='Blugrn',
                template='plotly_white'
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.subheader("⚙️ Segmentación por Origen de Datos")
            origen_count = df_filtrado['Origen'].value_counts().reset_index()
            origen_count.columns = ['Origen', 'Frecuencia']
            
            fig_pie = px.pie(
                origen_count, 
                values='Frecuencia', 
                names='Origen', 
                hole=0.4,
                color_discrete_sequence=['#1f77b4', '#2ca02c'],
                template='plotly_white'
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        
        # 6. Evolución Temporal Combinada
        st.subheader("📈 Evolución de Gestiones en el Tiempo")
        df_filtrado['fecha'] = df_filtrado['fecha_hora'].dt.date
        evolucion = df_filtrado.groupby(['fecha', 'Origen']).size().reset_index(name='Cantidad')
        
        fig_line = px.line(
            evolucion, 
            x='fecha', 
            y='Cantidad', 
            color='Origen',
            markers=True,
            line_shape='spline',
            color_discrete_map={'Manual (Registros Campo)': '#2ca02c', 'Automático (Uso de Apps)': '#1f77b4'},
            template='plotly_white'
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # 7. Sección de Clasificación de Reportes y Tareas de Campo
        st.markdown("---")
        st.subheader("📋 Análisis de Reportes y Tareas de Campo por Tipo")
        
        df_exportaciones = df_filtrado[df_filtrado['accion'].str.contains('Exportó|PDF|Reporte|Visita|Reunión|Capacitación', na=False, case=False)].copy()
        
        if not df_exportaciones.empty:
            def clasificar_reporte(accion):
                accion_lower = str(accion).lower()
                if 'checklist' in accion_lower: return 'Checklist'
                elif 'cierre' in accion_lower: return 'Cierre Cosecha'
                elif 'auditoría' in accion_lower: return 'Auditoría Cosecha'
                elif 'visita' in accion_lower or 'ensayo' in accion_lower: return 'Visita / Ensayo AA'
                elif '360' in accion_lower: return 'Reporte 360'
                elif 'capacitación' in accion_lower or 'reunión' in accion_lower: return 'Capacitación / Reunión'
                else: return 'General / Otros'
            
            df_exportaciones['Tipo de Tarea'] = df_exportaciones['accion'].apply(clasificar_reporte)
            reportes_tipo = df_exportaciones.groupby(['Tipo de Tarea', 'Origen']).size().reset_index(name='Cantidad')
            reportes_tipo = reportes_tipo.sort_values(by='Cantidad', ascending=False)
            
            col_tabla, col_grafico = st.columns([2, 3])
            
            with col_tabla:
                st.markdown("#### 🔢 Resumen en Tabla")
                st.dataframe(reportes_tipo, use_container_width=True, hide_index=True)
                if not reportes_tipo.empty:
                    top_reporte = reportes_tipo.iloc[0]['Tipo de Tarea']
                    st.success(f"💡 La tarea dominante actual es: **{top_reporte}**")
                
            with col_grafico:
                st.markdown("#### 📊 Distribución Visual Unificada")
                fig_reportes = px.bar(
                    reportes_tipo,
                    x='Cantidad',
                    y='Tipo de Tarea',
                    color='Origen',
                    orientation='h',
                    barmode='stack',
                    color_discrete_map={'Manual (Registros Campo)': '#2ca02c', 'Automático (Uso de Apps)': '#1f77b4'},
                    template='plotly_white'
                )
                fig_reportes.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_reportes, use_container_width=True)
                
        else:
            st.info("No se registraron tareas ni exportaciones en los filtros seleccionados.")
        
        # 8. Tabla de datos unificada final
        st.markdown("---")
        st.subheader("🔍 Historial Unificado de Actividad Reciente")
        
        columnas_mostrar = ['fecha_hora', 'nombre', 'accion', 'cliente', 'Origen']
        df_mostrar = df_filtrado[columnas_mostrar].sort_values(by='fecha_hora', ascending=False).copy()
        df_mostrar['fecha_hora'] = df_mostrar['fecha_hora'].dt.strftime('%d/%m/%Y %H:%M:%S')
        
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    else:
        st.warning("Asegurate de que las bases de datos estén cargadas en la rama 'main' de tu repositorio público.")
