import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Seguimiento de Colaboradores", layout="wide", page_icon="📊")

# Auto-refresh cada 30 segundos
st.fragment(run_every=30)(lambda: None)() # Esto fuerza un rerun silencioso de la app cada 30s

st.title("📊 Tablero de Seguimiento de Colaboradores")
st.markdown("Monitoreo de actividad, accesos y uso de herramientas en base a los registros del repositorio.")

# 1. Carga de datos desde los URLs Raw de GitHub
# Reemplazamos la ruta estándar por la de raw.githubusercontent
URL_USUARIOS = "https://raw.githubusercontent.com/suyai-d/reportes-seguridad-db/main/usuarios_permitidos.csv"
URL_ACTIVIDAD = "https://raw.githubusercontent.com/suyai-d/reportes-seguridad-db/main/registro_actividad.csv"

@st.cache_data(ttl=600)  # Se actualiza cada 10 minutos
def cargar_datos():
    try:
        df_usuarios = pd.read_csv(URL_USUARIOS)
        df_actividad = pd.read_csv(URL_ACTIVIDAD)
        
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

df = cargar_datos()

if df is not None:
    # 2. Filtros Laterales (Sidebar)
    st.sidebar.header("Filtros")
    
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

    # 3. Métricas Principales (KPIs)
    total_acciones = len(df_filtrado)
    usuarios_activos = df_filtrado['nombre'].nunique()
    exportaciones = len(df_filtrado[df_filtrado['accion'].str.contains('Exportó', na=False)])
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Interacciones", f"{total_acciones}")
    kpi2.metric("Colaboradores Activos", f"{usuarios_activos}")
    kpi3.metric("Reportes Generados (PDF)", f"{exportaciones}")
    
    st.markdown("---")
    
    # 4. Visualizaciones y Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📌 Actividad por Colaborador")
        # Contamos cuántas acciones hizo cada uno
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
    
    # 5. Evolución Temporal e Historial Detallado
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
    
    # 6. Tabla de datos crudos filtrada
    st.subheader("🔍 Historial de Actividad Reciente")
    # Formateamos la fecha para mostrarla más limpia
    df_mostrar = df_filtrado[['fecha_hora', 'nombre', 'accion', 'cliente']].sort_values(by='fecha_hora', ascending=False)
    df_mostrar['fecha_hora'] = df_mostrar['fecha_hora'].dt.strftime('%d/%m/%Y %H:%M:%S')
    
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

else:
    st.warning("Asegurate de que las bases de datos estén cargadas en la rama 'main' de tu repositorio público.")
