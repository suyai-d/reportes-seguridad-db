import streamlit as st
import pandas as pd
import plotly.express as px
import time

# Configuración de la página
st.set_page_config(page_title="Seguimiento de Colaboradores", layout="wide", page_icon="📊")

st.title("📊 Tablero de Seguimiento de Colaboradores")
st.markdown("Monitoreo de actividad, accesos y uso de herramientas en base a los registros del repositorio.")

# 1. Carga de datos desde los URLs Raw de GitHub
URL_USUARIOS = "https://raw.githubusercontent.com/suyai-d/reportes-seguridad-db/main/usuarios_permitidos.csv"
URL_ACTIVIDAD = "https://raw.githubusercontent.com/suyai-d/reportes-seguridad-db/main/registro_actividad.csv"

# Mantenemos un caché intermedio, pero le sumamos dinámica anti-duplicados de GitHub
@st.cache_data(ttl=600)
def cargar_datos(timestamp_evita_cache):
    try:
        # El parámetro nocache obliga a GitHub a darnos el archivo más nuevo e ignorar su proxy
        url_u = f"{URL_USUARIOS}?nocache={timestamp_evita_cache}"
        url_a = f"{URL_ACTIVIDAD}?nocache={timestamp_evita_cache}"
        
        df_usuarios = pd.read_csv(url_u)
        df_actividad = pd.read_csv(url_a)
        
        # Convertir fecha a datetime
        df_actividad['fecha_hora'] = pd.to_datetime(df_actividad['fecha_hora'])
        
        # Cruzar los datos para tener los nombres reales de los colaboradores
        df_master = pd.merge(df_actividad, df_usuarios, left_on='usuario', right_on='usuarios', how='left')
        
        # Si algún usuario no está en la lista de permitidos, dejamos su código original
        df_master['nombre'] = df_master['nombre'].fillna(df_master['usuario'])
        
        return df_master
    except Exception as e:
        st.error(f"Error al conectar con las bases de datos de GitHub: {e}")
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
