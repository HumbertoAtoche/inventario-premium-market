"""Plan de compras inteligente (demanda y reposición)."""
import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import re
import streamlit as st
from inventario.contexto import cfg, moneda_fmt, simbolo, tabla
from inventario.nucleo import permisos, tiempo
from inventario.servicios import _leer_reporte_excel, cargar_inventario, cargar_ventas, preparar_ventas, registrar_auditoria
from inventario.ui.componentes import header
from inventario.utilidades import formato_soles
from scipy.stats import norm


_P_COLORS = {'red':'#EC3237','green':'#00A959','blue':'#2777BC','navy':'#1D2A44','muted':'#7787A0','gray':'#F4F6F9'}


def _p_plot(fig, height=350):
    # Etiquetas legibles sin necesidad de hover.
    fig.update_layout(uniformtext_minsize=10, uniformtext_mode='show')
    fig.update_layout(template='plotly_white', height=height, margin=dict(l=12,r=12,t=30,b=15),
        paper_bgcolor='white', plot_bgcolor='white', font=dict(color='#334155',size=12,family='Montserrat, sans-serif'),
        hovermode='x unified', legend=dict(orientation='h',y=-0.22),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#E3E6EC'))
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, use_container_width=True, config={'displaylogo':False,'scrollZoom':False,'toImageButtonOptions':{'format':'png','scale':2}})


def _p_inventory(inv):
    d=inv.copy()
    d['Clave']=d['CodigoBarras'].fillna('').astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    d['Clave']=d['Clave'].mask(d['Clave'].eq(''), d['CodigoProducto'].fillna('').astype(str).str.strip())
    for c in ['StockSistema','CostoUnitario']:
        d[c]=pd.to_numeric(d[c],errors='coerce').fillna(0)
    d['CostoStock']=d['StockSistema'].clip(lower=0)*d['CostoUnitario']
    g=d.groupby('Clave',as_index=False).agg(Stock=('StockSistema','sum'),Capital=('CostoStock','sum'),ProductoInv=('Producto','first'))
    g['CostoUnitario']=np.where(g['Stock']>0,g['Capital']/g['Stock'],0)
    # Para existencias cero, conservar el costo registrado si existe.
    fallback=d.groupby('Clave')['CostoUnitario'].mean()
    g['CostoUnitario']=np.where(g['CostoUnitario']>0,g['CostoUnitario'],g['Clave'].map(fallback).fillna(0))
    return g


def _p_daily(ventas, days=None):
    d=ventas.loc[ventas['CantidadValida']].copy()
    if d.empty: return d, pd.DatetimeIndex([]), pd.DataFrame()
    d['Clave']=d['Clave'].astype(str).str.strip().str.replace(r'\.0$','',regex=True)
    d=d[d['Clave'].ne('')]
    last=d['Dia'].max()
    first=d['Dia'].min()
    if days: first=max(first,last-pd.Timedelta(days=days-1))
    d=d[d['Dia']>=first]
    calendar=pd.date_range(first,last,freq='D')
    grouped=d.groupby(['Clave','Dia'],as_index=False)['Cantidad'].sum()
    return d,calendar,grouped


def _p_forecast_candidates(series, horizon, allow_advanced=True):
    """Validación temporal holdout: no barajar fechas ni entrenar con el futuro."""
    y=np.asarray(series,dtype=float)
    n=len(y)
    hold=max(3,min(21,n//5)) if n>=21 else 0
    def forecast(name, train, steps):
        train=np.asarray(train,dtype=float)
        steps=int(steps)
        if name=='Media móvil 7d':
            return np.full(steps,max(0,float(np.mean(train[-min(7,len(train)):]))))
        if name=='Media ponderada 28d':
            s=train[-min(28,len(train)):]
            w=np.arange(1,len(s)+1,dtype=float)
            return np.full(steps,max(0,float(np.dot(s,w)/w.sum())))
        if name=='Estacional semanal':
            if len(train)<21: return np.full(steps,float(np.mean(train)))
            return np.maximum(0,np.array([np.mean(train[max(0,len(train)-28):][np.arange(max(0,len(train)-28),len(train))%7==(len(train)+i)%7]) for i in range(steps)]))
        if name=='Suavizamiento ETS':
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            seasonal='add' if len(train)>=42 else None
            fit=ExponentialSmoothing(train,trend=None,seasonal=seasonal,seasonal_periods=7 if seasonal else None,
                 initialization_method='estimated').fit(optimized=True)
            return np.maximum(0,np.asarray(fit.forecast(steps),dtype=float))
        if name=='StatsForecast AutoTheta':
            from statsforecast import StatsForecast
            from statsforecast.models import AutoTheta
            df_sf=pd.DataFrame({'unique_id':'producto','ds':pd.date_range('2024-01-01',periods=len(train),freq='D'),'y':train})
            model=StatsForecast(models=[AutoTheta(season_length=7)],freq='D',n_jobs=1)
            out=model.forecast(df=df_sf,h=steps)
            return np.maximum(0,out['AutoTheta'].to_numpy(dtype=float))
        if name=='LightGBM':
            import lightgbm as lgb
            if len(train)<70: raise ValueError('historial insuficiente')
            # Predicción recursiva: las características de rezago se generan exclusivamente
            # con datos pasados y pronósticos ya generados.
            def feats(arr,t):
                return [arr[t-1],arr[t-7],np.mean(arr[t-7:t]),np.mean(arr[t-14:t]),
                    np.std(arr[t-14:t]), t%7]
            X=np.array([feats(train,t) for t in range(14,len(train))]); Y=train[14:]
            m=lgb.LGBMRegressor(n_estimators=90,max_depth=3,num_leaves=7,learning_rate=.055,
                 min_child_samples=12,verbosity=-1,random_state=42,n_jobs=1)
            m.fit(X,Y)
            history=list(train); out=[]
            for _ in range(steps):
                pred=max(0,float(m.predict(np.array(feats(np.asarray(history),len(history))).reshape(1,-1))[0]))
                out.append(pred); history.append(pred)
            return np.array(out)
        raise ValueError(name)
    candidates=['Media móvil 7d','Media ponderada 28d']
    if n>=21: candidates.append('Estacional semanal')
    if allow_advanced and n>=28: candidates.append('Suavizamiento ETS')
    if allow_advanced and n>=42: candidates.append('StatsForecast AutoTheta')
    if allow_advanced and n>=90: candidates.append('LightGBM')
    scores=[]
    for name in candidates:
        try:
            if hold:
                pred=forecast(name,y[:-hold],hold)
                mae=float(np.mean(np.abs(y[-hold:]-pred)))
                bias=float(np.mean(pred-y[-hold:]))
            else:
                mae=np.nan; bias=np.nan
            scores.append((name,mae,bias))
        except Exception:
            continue
    if not scores: scores=[('Media móvil 7d',np.nan,np.nan)]
    winner=min(scores,key=lambda v:v[1] if np.isfinite(v[1]) else 1e20)[0]
    try: pred=forecast(winner,y,horizon)
    except Exception: pred=np.full(horizon,float(np.mean(y[-min(7,n):])))
    # Incertidumbre: aproximación empírica basada en error de validación temporal
    # y dispersión diaria. No equivale a un intervalo calibrado de demanda.
    best_mae=next((r[1] for r in scores if r[0]==winner),np.nan)
    sigma=max(float(np.std(y[-min(n,56):])),float(best_mae)*1.253 if np.isfinite(best_mae) else 0,0.25)
    widening=np.sqrt(1+np.arange(horizon)/7)
    low=np.maximum(0,pred-1.645*sigma*widening)
    high=np.maximum(pred,pred+1.645*sigma*widening)
    return {'modelo':winner,'pronostico':pred,'inferior':low,'superior':high,'sigma':sigma,
            'scores':pd.DataFrame(scores,columns=['Modelo','MAE validación','Sesgo validación']), 'holdout':hold}


def _p_metrics(ventas, inv, window, lead, review, service, budget, min_history):
    d,dates,grouped=_p_daily(ventas,window)
    if d.empty: return pd.DataFrame(),dates,grouped
    n=len(dates)
    z=float(norm.ppf(service/100))
    agg=d.groupby('Clave',as_index=False).agg(Producto=('PRODUCTO','first'),Categoria=('CATEGORÍA','first'),
        Unidades=('Cantidad','sum'),Venta=('VentaTotal','sum'),CostoVenta=('CostoTotal','sum'),
        UltimaVenta=('Dia','max'),DiasConVenta=('Dia','nunique'))
    sums=grouped.groupby('Clave')['Cantidad'].agg(lambda x:float(np.sum(np.asarray(x,dtype=float)**2)))
    agg['Demanda']=agg['Unidades']/max(1,n)
    agg['Sigma']=np.sqrt((agg['Clave'].map(sums).fillna(0)/max(1,n)-agg['Demanda']**2).clip(lower=0))
    agg['Margen']=agg['Venta']-agg['CostoVenta']
    agg['MargenPct']=np.where(agg['Venta']>0,agg['Margen']/agg['Venta']*100,0)
    agg=agg.merge(_p_inventory(inv),on='Clave',how='outer',indicator=True)
    agg['Vinculado']=agg['_merge'].ne('left_only') & agg['Stock'].notna()
    agg['Producto']=agg['Producto'].fillna(agg['ProductoInv']).fillna('Sin nombre')
    for col in ['Unidades','Venta','CostoVenta','Margen','MargenPct','Demanda','Sigma','Stock','Capital','CostoUnitario','DiasConVenta']:
        agg[col]=pd.to_numeric(agg[col],errors='coerce').fillna(0)
    agg['UltimaVenta']=pd.to_datetime(agg['UltimaVenta'])
    agg['DiasSinVenta']=(dates[-1]-agg['UltimaVenta']).dt.days if len(dates) else np.nan
    agg['Cobertura']=np.where(agg['Demanda']>0,agg['Stock']/agg['Demanda'],np.nan)
    agg['Seguridad']=np.ceil(z*agg['Sigma']*np.sqrt(max(1,lead)))
    agg['PuntoPedido']=np.ceil(agg['Demanda']*lead+agg['Seguridad'])
    agg['Objetivo']=np.ceil(agg['Demanda']*(lead+review)+agg['Seguridad'])
    agg['Sugerencia']=np.maximum(0,agg['Objetivo']-agg['Stock']).astype(int)
    agg.loc[(agg['Stock']>agg['PuntoPedido']) | (~agg['Vinculado']) | (agg['Demanda']<=0),'Sugerencia']=0
    agg['Inversion']=agg['Sugerencia']*agg['CostoUnitario']
    agg['Riesgo']=np.select([~agg['Vinculado'],(agg['Stock']<=0)&(agg['Demanda']>0),
       (agg['Cobertura']<=lead)&(agg['Demanda']>0),agg['Stock']<=agg['PuntoPedido'],
       agg['Cobertura']>60,(agg['Demanda']==0)&(agg['Stock']>0)],
       ['Sin vínculo','Agotado','Quiebre probable','Reponer','Sobrestock','Sin ventas'],default='Adecuado')
    agg['CapitalLento']=np.where(agg['Riesgo'].isin(['Sobrestock','Sin ventas']),agg['Capital'],0)
    agg['Prioridad']=np.where(agg['Riesgo'].eq('Agotado'),5,np.where(agg['Riesgo'].eq('Quiebre probable'),4,
       np.where(agg['Riesgo'].eq('Reponer'),3,0)))
    agg['Prioridad']=agg['Prioridad']*(1+np.maximum(agg['MargenPct'],0)/100)
    agg['Calidad']=np.where(n<min_history,'Historial corto',np.where(agg['DiasConVenta']<3,'Ventas esporádicas','Orientativa'))
    return agg,dates,grouped


def _p_scenario_plot(stock,forecast,lower,upper,dates,lead,point):
    f=np.asarray(forecast)
    expected=np.maximum(0,stock-np.cumsum(f))
    optimistic=np.maximum(0,stock-np.cumsum(lower))
    pessimistic=np.maximum(0,stock-np.cumsum(upper))
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=list(dates)+list(dates[::-1]),y=list(optimistic)+list(pessimistic[::-1]),
         fill='toself',fillcolor='rgba(39,119,188,.12)',line=dict(color='rgba(0,0,0,0)'),name='Escenarios bajo/alto'))
    fig.add_trace(go.Scatter(x=dates,y=expected,name='Stock esperado',mode='lines+markers+text',text=[f'{v:.1f}' for v in expected],textposition='top center',textfont=dict(size=10,color=_P_COLORS['blue']),cliponaxis=False,line=dict(color=_P_COLORS['blue'],width=3)))
    fig.add_hline(y=point,line_dash='dot',line_color=_P_COLORS['red'],annotation_text='Punto de pedido')
    if lead<len(dates): fig.add_vline(x=dates[lead].timestamp()*1000,line_dash='dash',line_color=_P_COLORS['green'])
    _p_plot(fig,390)


def _p_excel(sheets):
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine='openpyxl') as writer:
        for name,data in sheets.items():
            safe=data.copy().replace([np.inf,-np.inf],np.nan)
            for c in safe.columns:
                if pd.api.types.is_datetime64_any_dtype(safe[c]):
                    safe[c]=safe[c].dt.tz_localize(None) if getattr(safe[c].dt,'tz',None) else safe[c]
            safe.to_excel(writer,sheet_name=name[:31],index=False)
    return output.getvalue()


def _psi_manager_purchase_view(summary, dates, grouped, ventas, lead, service):
    """Vista gerencial: propuesta de compra para 14 días desde recepción."""
    from zoneinfo import ZoneInfo
    st.markdown('### Plan de compra · 14 días desde la recepción')
    st.caption('Responde tres preguntas: ¿qué se está vendiendo?, ¿cuánto pedir? y ¿cuánto dinero comprometer?')
    today=pd.Timestamp(tiempo.ahora()).normalize()
    saturday=today+pd.Timedelta(days=(5-today.weekday())%7)
    a,b,c=st.columns([1,1,1])
    with a: arrival=st.date_input('Fecha estimada de llegada',value=saturday.date(),key='psi_mgr_arrival')
    with b: duration=st.number_input('Días que debe durar el pedido',min_value=1,max_value=90,value=14,key='psi_mgr_duration')
    with c: reserve=st.selectbox('Protección ante ventas mayores a lo normal',[90,95,97,99],index=1,key='psi_mgr_service')
    st.caption('La cobertura empieza al recibir la mercadería, no al realizar el pedido. Se considera el stock disponible proyectado a la llegada.')
    st.markdown('**¿Qué productos deseas abastecer?**')
    scope=st.radio('Selección', ['Cervezas y licores','Todas las categorías','Buscar productos'],horizontal=True,key='psi_mgr_scope')
    x=summary.copy()
    x=x[x['Unidades'].gt(0) & x['Vinculado']].copy()
    alcohol_terms=r'cerveza|licor|whisk|vodka|ron\b|pisco|vino\b|espumante|gin\b|tequila|brandy|aguardiente|champagne|sidra|anisado|alcoh[oó]lic'
    if scope=='Cervezas y licores':
        x=x[x['Categoria'].fillna('').str.contains(alcohol_terms,case=False,regex=True)|x['Producto'].fillna('').str.contains(alcohol_terms,case=False,regex=True)]
        st.info('Selección basada en categoría y nombre del producto. Revisa la lista: la clasificación automática puede omitir artículos o incluir otros por coincidencia de palabras.')
    elif scope=='Buscar productos':
        q=st.text_input('Buscar por producto o código',key='psi_mgr_query')
        if q: x=x[x['Producto'].str.contains(re.escape(q),case=False,na=False)|x['Clave'].str.contains(re.escape(q),case=False,na=False)]
    if x.empty:
        st.warning('No hay productos con ventas históricas vinculados al inventario para esta selección. No se generan compras sin evidencia de demanda.')
        return
    days_until=max(0,(pd.Timestamp(arrival)-today).days)
    if pd.Timestamp(arrival)<today: st.warning('La llegada elegida ya pasó; se asume recepción inmediata para el cálculo.')
    if (pd.Timestamp(arrival)-today).days>30: st.info('Plazo largo: confirma disponibilidad del proveedor y la vigencia de las estimaciones.')
    last_date=dates[-1]
    if (today-last_date).days>2:
        st.warning(f'Últimas ventas registradas: {last_date:%d/%m/%Y}. Si faltan días de carga, la demanda puede estar subestimada.')
    from scipy.stats import norm as _norm
    z=float(_norm.ppf(int(reserve)/100))
    rows=[]
    for r in x.itertuples(index=False):
        key=str(r.Clave)
        hist=grouped[grouped['Clave'].eq(key)].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0).to_numpy(dtype=float)
        if len(hist)==0: continue
        # Pronóstico estable para operación: combina promedio reciente y patrón semanal
        recent=hist[-min(56,len(hist)):]
        mean=float(recent.mean())
        if len(hist)>=28:
            weekday=np.array([np.mean(hist[-28:][np.arange(len(hist)-28,len(hist))%7==j]) for j in range(7)])
            # Suavizado para evitar sobreajuste de apenas 4 observaciones por día.
            weekday=.55*weekday+.45*float(np.mean(hist[-28:]))
        else: weekday=np.full(7,mean)
        n_total=days_until+int(duration)
        future=pd.date_range(today+pd.Timedelta(days=1),periods=max(n_total,1),freq='D')
        forecast=np.maximum(0,np.array([weekday[(d-dates[0]).days%7] if len(hist)>=28 else mean for d in future]))
        before=float(forecast[:days_until].sum())
        after=float(forecast[days_until:days_until+int(duration)].sum())
        # Reserva estadística orientativa: dispersión diaria * sqrt(horizonte)
        sigma=float(np.std(recent,ddof=1)) if len(recent)>1 else 0
        safety=int(np.ceil(z*sigma*np.sqrt(int(duration))))
        stock=float(r.Stock)
        arrival_stock=max(0,stock-before)
        need=max(0,int(np.ceil(after+safety-arrival_stock)))
        cost=float(r.CostoUnitario)
        rows.append({'Producto':r.Producto,'Código':key,'Categoría':r.Categoria,
                     'Stock hoy':round(stock,1),'Venta diaria':round(mean,2),
                     'Venta estimada 14d':round(after,1),'Reserva':safety,
                     'Stock al recibir':round(arrival_stock,1),'Comprar (und)':need,
                     'Costo unitario':round(cost,2),'Inversión':round(need*cost,2),
                     'Días sin venta':int(r.DiasSinVenta) if pd.notna(r.DiasSinVenta) else None,
                     'Cobertura hoy':round(stock/mean,1) if mean>0 else None,
                     'Riesgo previo a entrega':'Sin stock' if stock<=0 else ('Puede agotarse' if before>=stock else 'Con cobertura'),
                     '_demanda':after,'_before':before})
    plan=pd.DataFrame(rows)
    if plan.empty: st.info('No se pudieron estimar cantidades.');return
    plan=plan.sort_values(['Comprar (und)','Inversión'],ascending=False)
    total=int(plan['Comprar (und)'].sum()); investment=float(plan['Inversión'].sum())
    no_stock=int((plan['Stock hoy']<=0).sum()); at_risk=int(plan['Riesgo previo a entrega'].ne('Con cobertura').sum())
    m=st.columns(4)
    m[0].metric('Productos a comprar',f"{int((plan['Comprar (und)']>0).sum()):,}")
    m[1].metric('Unidades sugeridas',f'{total:,}')
    m[2].metric('Inversión estimada',formato_soles(investment))
    m[3].metric('Sin stock hoy',str(no_stock))
    st.markdown(f'**Lectura para gerencia:** para cubrir **{int(duration)} días desde el {pd.Timestamp(arrival):%d/%m/%Y}**, se estiman **{total:,} unidades** por **{formato_soles(investment)}**, incluyendo una reserva de servicio del **{reserve}%**. Hay **{at_risk} referencias** agotadas o con riesgo de agotarse antes de recibir el pedido.')
    if no_stock:
        st.warning(f'{no_stock} productos tienen stock registrado cero. Sus ventas recientes podrían subestimar la demanda real si llevan días agotados; revisa el pedido antes de confirmarlo.')
    st.markdown('#### Prioridades de compra')
    st.caption('Comprar (und) = ventas esperadas durante el periodo + reserva − stock estimado al recibir. Las cantidades son orientativas, no pedidos automáticos.')
    show=plan[['Producto','Stock hoy','Venta diaria','Venta estimada 14d','Reserva','Stock al recibir','Comprar (und)','Inversión','Riesgo previo a entrega']]
    st.dataframe(show,hide_index=True,use_container_width=True,height=390)
    left,right=st.columns([1.35,1])
    with left:
        st.markdown('**¿Qué productos concentran la compra?**')
        top=plan.nlargest(12,'Inversión').sort_values('Inversión')
        fig=go.Figure(go.Bar(x=top['Inversión'],y=top['Producto'].str.slice(0,42),orientation='h',marker_color='#00A959',text=[f'{simbolo()} {v:,.0f}' for v in top['Inversión']],textposition='outside',cliponaxis=False))
        fig.update_xaxes(title=f'Inversión sugerida ({simbolo()})')
        _p_plot(fig,400)
    with right:
        st.markdown('**Cómo se calcula**')
        st.markdown('**1.** Se estiman las unidades que se venderían hasta la llegada.\n\n**2.** Se proyecta cuánto stock quedará al recibir.\n\n**3.** Se estima la venta de los siguientes 14 días.\n\n**4.** Se añade una reserva por variabilidad y se resta el stock disponible.')
        st.caption('Se usa un promedio reciente con patrón semanal suavizado cuando hay al menos 28 días. Es una estimación inicial; no sustituye la validación temporal de modelos ni corrige automáticamente ventas perdidas por quiebres.')
    st.download_button('📥 Descargar propuesta de compra (Excel)',_p_excel({'Plan de compra':plan.drop(columns=['_demanda','_before'])}),file_name='Premium_Plan_Compra_14_Dias.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='psi_mgr_export')
    st.caption('No incluye pedidos en tránsito, mínimos de compra, múltiplos por caja, vencimientos ni condiciones de proveedor. Costo unitario cero significa que la inversión puede estar incompleta.')


def pantalla_stock_intelligence():
    """Una sola pantalla de decisión: qué comprar, cuánto y por qué."""
    from zoneinfo import ZoneInfo
    header(f'Plan de Compras | {cfg().nombre}', 'Decisiones de abastecimiento basadas en stock disponible y comportamiento de ventas')
    if not permisos.tiene(st.session_state.usuario, 'compras_ia'):
        st.error('Acceso exclusivo para administración.'); return
    try:
        ventas=preparar_ventas(cargar_ventas())
        inventario=cargar_inventario()
    except Exception as exc:
        st.error(f'No se pudieron cargar las ventas o el inventario: {exc}'); return
    if ventas.empty:
        st.info('Todavía no hay ventas cargadas. Abre «Actualizar ventas» al final de la página.')
    elif (~ventas['CantidadValida']).any():
        st.error(f"Hay {int((~ventas['CantidadValida']).sum())} filas con CANTIDAD inválida. Revisa las ventas antes de generar compras.")
    else:
        today=pd.Timestamp(tiempo.ahora()).normalize()
        last=ventas['Dia'].max()
        default_arrival=today+pd.Timedelta(days=(5-today.weekday())%7)
        st.markdown('<div class="psi-section"><span class="psi-index">01</span> Configura el abastecimiento</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns([1.1,1,1])
        with c1: arrival=st.date_input('¿Cuándo llegará?',value=default_arrival.date(),min_value=today.date(),key='psi_simple_arrival')
        with c2: duration=st.selectbox('¿Para cuántos días?',options=[7,14,21,30],index=1,format_func=lambda x:f'{x} días desde la llegada',key='psi_simple_days')
        with c3: service=st.selectbox('Reserva de seguridad',options=[90,95,97,99],index=1,format_func=lambda x:f'{x}% de protección',key='psi_simple_service')
        col1,col2=st.columns([1,1.6])
        with col1: window=st.selectbox('Historial para estimar ventas',[30,60,90,180,365],index=2,format_func=lambda x:f'Últimos {x} días',key='psi_simple_window')
        with col2: search=st.text_input('Filtrar productos o categoría',placeholder='Ej.: cerveza, Coca-Cola, snacks, código de barras',key='psi_simple_search')
        summary,dates,grouped=_p_metrics(ventas,inventario,int(window),3,7,int(service),0,28)
        if summary.empty:
            st.info('No hay datos suficientes para calcular un pedido.'); return
        x=summary[(summary['Unidades']>0)&(summary['Vinculado'])].copy()
        if search.strip():
            pattern=re.escape(search.strip())
            x=x[x['Producto'].str.contains(pattern,case=False,na=False)|x['Categoria'].fillna('').str.contains(pattern,case=False,na=False)|x['Clave'].str.contains(pattern,case=False,na=False)]
        if x.empty:
            st.info('No hay productos con ventas históricas vinculados al inventario para este filtro.');
        else:
            days_until=max(0,(pd.Timestamp(arrival)-today).days)
            z=float(norm.ppf(int(service)/100))
            future=pd.date_range(today+pd.Timedelta(days=1),periods=max(1,days_until+duration),freq='D')
            rows=[]
            for r in x.itertuples(index=False):
                hist=grouped[grouped['Clave'].eq(str(r.Clave))].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0).to_numpy(dtype=float)
                if not len(hist): continue
                recent=hist[-min(56,len(hist)):]
                avg=float(recent.mean())
                if len(hist)>=28:
                    tail=hist[-28:]
                    weekly=np.array([tail[np.arange(len(tail))%7==j].mean() for j in range(7)])
                    weekly=.55*weekly+.45*float(tail.mean())
                    # Alinear los días de la semana con la fecha del último registro.
                    start_weekday=(dates[-28].weekday() if len(dates)>=28 else dates[0].weekday())
                    demand=np.maximum(0,np.array([weekly[(d.weekday()-start_weekday)%7] for d in future]))
                else:
                    demand=np.full(len(future),avg)
                before=float(demand[:days_until].sum())
                after=float(demand[days_until:days_until+duration].sum())
                sigma=float(np.std(recent,ddof=1)) if len(recent)>1 else 0
                reserve=int(np.ceil(z*sigma*np.sqrt(duration)))
                stock=max(0,float(r.Stock))
                arrival_stock=max(0,stock-before)
                qty=max(0,int(np.ceil(after+reserve-arrival_stock)))
                cost=max(0,float(r.CostoUnitario))
                risk='Agotado' if stock<=0 else ('Puede agotarse antes de recibir' if stock<=before else 'Con stock hasta entrega')
                if qty==0: status='No comprar'
                elif risk!='Con stock hasta entrega': status='Urgente'
                else: status='Programar'
                explanation=(f'Vende aprox. {avg:.1f} und/día; al recibir quedarían {arrival_stock:.0f} und. '
                             f'Se estiman {after:.0f} und para {duration} días y {reserve} und de reserva.')
                rows.append({'Producto':r.Producto,'Código':str(r.Clave),'Categoría':r.Categoria,
                             'Stock actual':int(round(stock)),'Venta diaria':round(avg,2),
                             'Stock al recibir':round(arrival_stock,1),'Venta esperada':round(after,1),
                             'Reserva':reserve,'Comprar':qty,'Costo unitario':round(cost,2),
                             'Inversión':round(qty*cost,2),'Prioridad':status,'Motivo':explanation,
                             'Riesgo':risk,'Cobertura (días)':round(stock/avg,1) if avg>0 else None})
            plan=pd.DataFrame(rows)
            if not plan.empty:
                order={'Urgente':0,'Programar':1,'No comprar':2}
                plan['_orden']=plan['Prioridad'].map(order)
                plan=plan.sort_values(['_orden','Comprar'],ascending=[True,False]).drop(columns='_orden')
                buy=plan[plan['Comprar']>0]
                st.markdown('<div class="psi-section"><span class="psi-index">02</span> Resumen ejecutivo</div>',unsafe_allow_html=True)
                k1,k2,k3=st.columns(3)
                k1.metric('Productos a comprar',f'{len(buy):,}')
                k2.metric('Unidades a pedir',f"{int(buy['Comprar'].sum()):,}")
                k3.metric('Inversión estimada',formato_soles(buy['Inversión'].sum()))
                urgent=int((plan['Prioridad']=='Urgente').sum())
                from html import escape as _psi_escape
                no_buy=int((plan['Prioridad']=='No comprar').sum())
                total_cost=float(buy['Inversión'].sum())
                text_summary=(f'Para cubrir {duration} días desde la llegada del {pd.Timestamp(arrival):%d/%m/%Y}, '
                              f'se propone adquirir {int(buy["Comprar"].sum()):,} unidades de {len(buy)} productos '
                              f'con una inversión estimada de {formato_soles(total_cost)}. '
                              f'{urgent} productos requieren atención urgente y {no_buy} no necesitan compra en este escenario.')
                st.markdown(f'<div class="psi-executive"><h3>Decisión recomendada</h3><p>{_psi_escape(text_summary)}</p></div>',unsafe_allow_html=True)
                b1,b2,b3=st.columns(3)
                b1.metric('Atención urgente',f'{urgent} productos')
                b2.metric('Compra programada',f'{int((plan["Prioridad"]=="Programar").sum())} productos')
                b3.metric('No comprar',f'{no_buy} productos')
                if (today-last).days>2:
                    st.warning(f'Última venta cargada: {last:%d/%m/%Y}. Faltan días recientes; las compras sugeridas podrían estar subestimadas.')
                if len(dates)<28:
                    st.warning('Historial corto: las recomendaciones son preliminares.')
                if (plan['Costo unitario'].eq(0)&plan['Comprar'].gt(0)).any():
                    st.warning('Hay productos sin costo válido. La inversión total puede estar incompleta.')
                st.caption('Stock actual = hoja Inventario. La recomendación NO incluye pedidos en tránsito ni reconstruye ventas perdidas durante quiebres de stock.')
                st.markdown('<div class="psi-section"><span class="psi-index">03</span> Prioridades de compra</div>',unsafe_allow_html=True)
                view=st.radio('Mostrar',['Solo comprar','Todos los productos','Urgentes'],horizontal=True,key='psi_simple_filter')
                visible=buy if view=='Solo comprar' else (plan[plan['Prioridad']=='Urgente'] if view=='Urgentes' else plan)
                st.caption('Ordenado por prioridad. Selecciona «Todos los productos» para revisar también los que no necesitan reposición.')
                view_cols=['Producto','Stock actual','Venta diaria','Cobertura (días)','Comprar','Inversión','Prioridad','Motivo']
                st.dataframe(visible[view_cols],hide_index=True,use_container_width=True,height=min(500,max(180,55+len(visible)*36)),column_config={
                    'Producto':st.column_config.TextColumn('Producto',width='large'),
                    'Stock actual':st.column_config.NumberColumn('Stock',format='%d und'),
                    'Venta diaria':st.column_config.NumberColumn('Venta/día',format='%.2f'),
                    'Cobertura (días)':st.column_config.NumberColumn('Días restantes',format='%.1f'),
                    'Comprar':st.column_config.NumberColumn('Pedir',format='%d und'),
                    'Inversión':st.column_config.NumberColumn('Inversión',format=moneda_fmt()),
                    'Prioridad':st.column_config.TextColumn('Decisión',width='small'),
                    'Motivo':st.column_config.TextColumn('Fundamento',width='large')})
                if len(buy)>0:
                    import plotly.graph_objects as _psi_go
                    st.markdown('**¿Dónde se concentra la inversión?**')
                    chart=buy.nlargest(8,'Inversión').sort_values('Inversión')
                    fig_inv=_psi_go.Figure(_psi_go.Bar(x=chart['Inversión'],y=chart['Producto'].str.slice(0,34),orientation='h',marker_color='#00A959',text=[f'{simbolo()} {v:,.0f}' for v in chart['Inversión']],textposition='outside',cliponaxis=False))
                    fig_inv.update_layout(margin=dict(l=10,r=55,t=12,b=18),height=max(220,40*len(chart)+75),paper_bgcolor='white',plot_bgcolor='white',showlegend=False,font=dict(color='#42536b',size=12),xaxis=dict(title=f'Inversión sugerida ({simbolo()})',showgrid=True,gridcolor='#eef1f5'),yaxis=dict(title=''))
                    st.plotly_chart(fig_inv,use_container_width=True,config={'displayModeBar':False})
                st.download_button('📥 Descargar lista de compra (Excel)',data=_p_excel({'Compra recomendada':plan}),file_name='TiendasPremium_Plan_de_Compras.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='psi_simple_export')
                st.markdown('<div class="psi-section"><span class="psi-index">04</span> Explicación de un producto</div>',unsafe_allow_html=True)
                product_names=[f"{r.Producto} · {r.Código}" for r in plan.itertuples(index=False)]
                chosen=st.selectbox('Producto para revisar',options=range(len(plan)),format_func=lambda i:product_names[i],key='psi_simple_selected')
                item=plan.iloc[chosen]
                st.markdown(f'<div class="psi-executive"><h3>{_psi_escape(str(item["Producto"]))} · {_psi_escape(str(item["Prioridad"]))}</h3><p>{_psi_escape(str(item["Motivo"]))}</p></div>',unsafe_allow_html=True)
                c1,c2,c3=st.columns(3)
                c1.metric('Stock actual',f"{item['Stock actual']} und")
                c2.metric('Cobertura estimada',f"{item['Cobertura (días)']} días" if pd.notna(item['Cobertura (días)']) else 'Sin demanda')
                c3.metric('Comprar',f"{item['Comprar']} und")
                key=item['Código']
                historical=grouped[grouped['Clave'].eq(key)].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0)
                daily=historical.tail(14)
                fig=go.Figure(go.Bar(x=daily.index,y=daily.values,marker_color='#00A959',text=[f'{v:.0f}' for v in daily.values],textposition='outside',cliponaxis=False,name='Unidades'))
                fig.update_layout(title='Ventas de los últimos 14 días',showlegend=False,yaxis_title='Unidades')
                _p_plot(fig,290)
                st.caption('Unidades vendidas por día. Un cero solo equivale a ausencia de ventas si el registro de ese día está completo.')
                if float(item['Venta diaria'])>0:
                    days=int(max(1,round(float(item['Cobertura (días)'])))) if pd.notna(item['Cobertura (días)']) else 0
                    if days and days<=7:
                        st.warning(f'Con el stock registrado, este producto podría agotarse en unos {days} días si continúa su ritmo de ventas.')
                else:
                    st.info('No hay demanda observada suficiente para calcular días de cobertura. Revisar disponibilidad e historial.')
                with st.expander('Ver cálculo y limitaciones',expanded=False):
                    st.write(f"Stock al recibir: {item['Stock al recibir']} und · Ventas previstas: {item['Venta esperada']} und · Reserva: {item['Reserva']} und")
                    st.write('Compra = máximo entre 0 y (ventas previstas durante el periodo + reserva − stock estimado al recibir), redondeado hacia arriba.')
                    st.write('Las cantidades son estimaciones y requieren revisión antes de realizar un pedido. Sin historial de disponibilidad, las ventas observadas pueden subestimar la demanda cuando hubo quiebres.')
    with st.expander('📥 Actualizar ventas desde Excel',expanded=False):
        st.caption('Importa el Excel con los 25 encabezados originales. Se conservan las filas existentes.')
        archivo=st.file_uploader('Archivo de ventas (.xlsx)',type=['xlsx'],key='psi_simple_upload')
        if archivo is not None:
            try:
                nuevo=_leer_reporte_excel(archivo)
                st.write(f'Registros detectados: {len(nuevo):,}')
                st.dataframe(nuevo.head(5),hide_index=True,use_container_width=True)
                if st.button('Agregar ventas nuevas',key='psi_simple_import',type='primary'):
                    ws=tabla("ventas"); existing=cargar_ventas()
                    cols=['FECHA/HORA','COMPROBANTE','CÓDIGO DE BARRA','PRODUCTO','SKU','COSTO*','PRECIO PROMEDIO','CANTIDAD','TOTAL']
                    def occurrences(frame):
                        if frame.empty: return []
                        b=frame[cols].fillna('').astype(str).apply(lambda r:'\x1f'.join(r),axis=1)
                        return list(zip(b,b.groupby(b).cumcount()))
                    seen=set(occurrences(existing)); keys=occurrences(nuevo)
                    rows=[list(r) for i,r in enumerate(nuevo.itertuples(index=False,name=None)) if keys[i] not in seen]
                    if rows: ws.append_rows(rows,value_input_option='RAW')
                    cargar_ventas.clear()
                    registrar_auditoria('IMPORTACION_VENTAS',f'{len(rows)} filas; {archivo.name}')
                    st.success(f'{len(rows)} filas agregadas; {len(nuevo)-len(rows)} ya existentes.')
            except Exception as exc:
                st.error(f'No se pudo procesar el Excel: {exc}')
