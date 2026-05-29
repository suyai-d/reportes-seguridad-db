import streamlit as st
import pandas as pd
import plotly.express as px
import time

# Configuración de la página
st.set_page_config(page_title="Seguimiento de Colaboradores", layout="wide", page_icon="📊")

st.title("📊 Tablero de Seguimiento de Colaboradores")
st.markdown("Monitoreo de actividad, accesos y uso de herramientas en base a los registros del repositorio.")

# 1. Carga de datos usando la API de GitHub optimizada para datos Raw instantáneos
USER = "suyai-d"
REPO = "reportes-seguridad-db"
BRANCH = "main"

@st.cache_data(ttl=600)
def cargar_datos(timestamp_evita_cache):
    try:
        # Mantenemos las URLs de la API de contenidos para evitar la CDN de GitHub
        url_u = f"https://api.github.com/repos/{USER}/{REPO}/contents/usuarios_permitidos.csv?ref={BRANCH}"
        url_a = f"https://api.github.com/repos/{USER}/{REPO}/contents/registro_actividad.csv?ref={BRANCH}"
        
        # CRUCIAL: 'application/vnd.github.v3.raw' le dice a la API que devuelva el archivo plano (CSV)
        # en lugar del JSON con metadatos que rompía Pandas.
        headers = {
            "User-Agent": "Streamlit-App",
            "Accept": "application/vnd.github.v3.raw",
            "Cache-Control": "no-cache"
        }
        
        # Leemos los CSVs usando las cabeceras HTTP correctas
        df_usuarios = pd.read_csv(url_u, storage_options={"headers": headers})
        df_actividad = pd.read_csv(url_a, storage_options={"headers": headers})
        
        # Convertir fecha a datetime
        df_actividad['fecha_hora'] = pd.to_datetime(df_actividad['fecha_hora'])
        
        # Cruzar los datos para tener los nombres reales de los colaboradores 
        df_master = pd.merge(df_actividad, df_usuarios, left_on='usuario', right_on='usuarios', how='left') [cite: 1, 2]
        df_master['nombre'] = df_master['nombre'].fillna(df_master['usuario']) [cite: 1, 2]
        
        return df_master
    except Exception as e:
        st.error(f"Error al conectar con la API de GitHub: {e}")
        # Si la API falla o excede el límite de cuota, usamos el plan B (el método tradicional con timestamp)
        try:
            url_raw_u = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/usuarios_permitidos.csv?nocache={timestamp_evita_cache}"
            url_raw_a = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/registro_actividad.csv?nocache={timestamp_evita_cache}"
            df_usuarios = pd.read_csv(url_raw_u)
            df_actividad = pd.read_csv(url_raw_a)
            df_actividad['fecha_hora'] = pd.to_datetime(df_actividad['fecha_hora'])
            df_master = pd.merge(df_actividad, df_usuarios, left_on='usuario', right_on='usuarios', how='left')
            df_master['nombre'] = df_master['nombre'].fillna(df_master['usuario'])
            return df_master
        except:
            return None

# 2. Control de datos y botón en la barra lateral
st.sidebar.header("🔄 Control de Datos")

# Botón para limpiar el caché manualmente
if st.sidebar.button("🔄 Actualizar Datos Ahora", use_container_width=True):
    st.cache_data.clear()  # Borra el caché de Streamlit
    st.rerun()             # Fuerza el recargo inmediato

# Le pasamos el tiempo actual truncado al minuto como argumento para manejar la actualización de red
df = cargar_datos(int(time.time() / 60))

if df is not None:
    # 3. Filtros Laterales (Sidebar)
    st.sidebar.markdown("---")
    st.sidebar.header("Filtros de Análisis")
    
    # Filtro de Fecha
    min_fecha = df['fecha_hora'].min().date()
    max_fecha = df['fecha_hora'].max().date()
    f_inicio, f_final = st.sidebar.date_input("Rango de fechas", [min_fecha, max_fecha], min_value=min_fecha, max_value=max_fecha)
    
    # Filtro de Usuarios
    usuarios_disponibles = sorted(df['nombre'].unique())
    usuarios_seleccionados = st.sidebar.multiselect("Seleccionar Colaboradores", usuarios_disponibles, default=usuarios_disponibles)
    
    # Filtrar el dataframe principal
    df_filtrado = df[
        (df['fecha_hora'].dt.date >= f_inicio) & 
        (df['fecha_hora'].dt.date <= f_final) & 
        (df['nombre'].isin(usuarios_seleccionados))
    ]

    # 4. Métricas Principales (KPIs)
    total_acciones = len(df_filtrado)
    usuarios_activos = df_filtrado['nombre'].nunique()
    # Buscamos de forma general cualquier interacción de exportación
    exportaciones = len(df_filtrado[df_filtrado['accion'].str.contains('Exportó|PDF', na=False, case=False)])
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Interacciones", f"{total_acciones}")
    kpi2.metric("Colaboradores Activos", f"{usuarios_activos}")
    kpi3.metric("Reportes Generados (PDF)", f"{exportaciones}")
    
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
        st.subheader("⚙️ Tipos de Acciones Más Frecuentes")
        acciones_count = df_filtrado['accion'].value_counts().reset_index()
        acciones_count.columns = ['Acción', 'Frecuencia']
        
        fig_pie = px.pie(
            acciones_count, 
            values='Frecuencia', 
            names='Acción', 
            hole=0.4,
            template='plotly_white'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    
    # 6. Evolución Temporal
    st.subheader("📈 Evolución de Accesos en el Tiempo")
    df_filtrado['fecha'] = df_filtrado['fecha_hora'].dt.date
    evolucion = df_filtrado.groupby('fecha').size().reset_index(name='Cantidad')
    
    fig_line = px.line(
        evolucion, 
        x='fecha', 
        y='Cantidad', 
        markers=True,
        line_shape='spline',
        template='plotly_white'
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # 7. Sección de Clasificación de Reportes Exportados
    st.markdown("---")
    st.subheader("📋 Análisis de Reportes Exportados por Tipo")
    
    df_exportaciones = df_filtrado[df_filtrado['accion'].str.contains('Exportó|PDF', na=False, case=False)].copy()
    
    if not df_exportaciones.empty:
        def clasificar_reporte(accion):
            accion_lower = str(accion).lower()
            if 'checklist' in accion_lower:
                return 'Checklist'
            elif 'cosecha' in accion_lower:
                return 'Reporte Cosecha'
            else:
                return 'General / Otros'
        
        df_exportaciones['Tipo de Reporte'] = df_exportaciones['accion'].apply(clasificar_reporte)
        
        reportes_tipo = df_exportaciones.groupby('Tipo de Reporte').size().reset_index(name='Cantidad Exportada')
        reportes_tipo = reportes_tipo.sort_values(by='Cantidad Exportada', ascending=False)
        
        col_tabla, col_grafico = st.columns([2, 3])
        
        with col_tabla:
            st.markdown("#### 🔢 Resumen en Tabla")
            st.dataframe(
                reportes_tipo, 
                use_container_width=True, 
                hide_index=True
            )
            top_reporte = reportes_tipo.iloc[0]['Tipo de Reporte']
            st.success(f"💡 El reporte más solicitado es: **{top_reporte}**")
            
        with col_grafico:
            st.markdown("#### 📊 Distribución Visual")
            fig_reportes = px.bar(
                reportes_tipo,
                x='Cantidad Exportada',
                y='Tipo de Reporte',
                orientation='h',
                color='Tipo de Reporte',
                color_discrete_sequence=px.colors.qualitative.Prism,
                template='plotly_white'
            )
            fig_reportes.update_layout(
                showlegend=False,
                xaxis_title="Cantidad de PDFs Generados",
                yaxis_title="",
                yaxis={'categoryorder':'total ascending'}
            )
            st.plotly_chart(fig_reportes, use_container_width=True)
            
    else:
        st.info("No se registraron exportaciones de reportes en el rango de fechas seleccionado.")
    
    # 8. Tabla de datos crudos filtrada (Al final para un mejor cierre visual)
    st.markdown("---")
    st.subheader("🔍 Historial de Actividad Reciente")
    
    # Protegemos el render en caso de que la columna 'cliente' no venga en alguna fila
    columnas_mostrar = ['fecha_hora', 'nombre', 'accion']
    if 'cliente' in df_filtrado.columns:
        columnas_mostrar.append('cliente')
        
    df_mostrar = df_filtrado[columnas_mostrar].sort_values(by='fecha_hora', ascending=False).copy()
    df_mostrar['fecha_hora'] = df_mostrar['fecha_hora'].dt.strftime('%d/%m/%Y %H:%M:%S')
    
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

else:
    st.warning("Asegurate de que las bases de datos estén cargadas en la rama 'main' de tu repositorio público.")
