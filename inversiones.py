import json
import operator
import os
import sqlite3
from datetime import datetime
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import matplotlib.pyplot as plt
import yfinance as yf
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def obtener_precio(ticker_symbol: str, mexicano: bool = False) -> float:
    """
    Obtiene el último precio disponible usando fast_info.
    Si mexicano=True, añade automáticamente '.MX' al ticker para buscarlo en pesos.
    """
    # Si se solicita mercado mexicano y no tiene la extensión, se la agregamos
    if mexicano and not ticker_symbol.endswith('.MX'):
        ticker_symbol = f"{ticker_symbol}.MX"

    try:
        ticker = yf.Ticker(ticker_symbol)
        precio = ticker.fast_info.last_price
        
        if str(precio) == 'nan' or precio is None:
            return 0.0
        return float(precio)
    except Exception as e:
        print(f"Advertencia: No se encontraron datos para {ticker_symbol}: {e}")
        return 0.0

def revisar_plata(cur, onzas: float = 0) -> float:
    """Obtiene el valor total de las onzas de plata físicas y papel."""
    cur.execute('SELECT onza FROM Plata')
    filas = cur.fetchall()
    for fila in filas:
        for valor in fila:
            onzas += valor
            
    # mxn y plata_usd se buscan de forma internacional tal cual (retornan USD)
    mxn = obtener_precio('MXN=X')
    plata_usd = obtener_precio('SI=F')
    
    plata_mxn = plata_usd * mxn
    plata_fisica = round(onzas * plata_mxn, 2)
    
    # SLV se busca en el mercado mexicano pasándole mexicano=True (buscará SLV.MX)
    precio_slv = obtener_precio('SLV', mexicano=True)
    plata_papel = precio_slv * 3
    
    valor_plata = plata_fisica + plata_papel
    return round(valor_plata, 2)

def revisar_criptomonedas(cur, diccionario: dict = None, simbolos: str = '') -> list:
    """Consulta los balances de criptomonedas y obtiene sus precios actuales vía CoinMarketCap API."""
    if diccionario is None:
        diccionario = {}
        
    ejecutar = 'SELECT Criptomonedas.Nombre, Cantidades_en_criptomonedas.Monto FROM Criptomonedas JOIN Cantidades_en_criptomonedas ON Cantidades_en_criptomonedas.Cripto_id = Criptomonedas.id'
    for x in cur.execute(ejecutar):
        if x[0] in diccionario.keys():
            diccionario[x[0]] += x[1]
        else:
            diccionario[x[0]] = x[1]

    for moneda in diccionario.keys():
        if simbolos == '':
            simbolos = simbolos + moneda
        else:
            simbolos = simbolos + ',' + moneda
    
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    parameters = {
        'symbol': simbolos,
        'convert': 'MXN',
    }
    
    api_key = os.getenv('CMC_API_KEY')
    if not api_key:
        print("\n[Error] No se encontró la API Key de CoinMarketCap en las variables de entorno.")
        return []

    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key,
    }
    session = Session()
    session.headers.update(headers)
    
    try:
        response = session.get(url, params=parameters)
        ejecutar = json.loads(response.text)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(f"Error de conexión con CoinMarketCap: {e}")
        return []
    
    criptomonedas_dic = dict()
    for moneda in diccionario.keys():
        try:
            precio = ejecutar['data'][moneda]['quote']['MXN']['price']
            precio = precio * diccionario.get(moneda)
            criptomonedas_dic[moneda] = round(precio, 2)
        except KeyError:
            print(f"Error: No se pudieron obtener datos para la criptomoneda {moneda}.")
            criptomonedas_dic[moneda] = 0.0
            
    for x in criptomonedas_dic.keys():
        if x in ["BTC", "ETH", "LTC"]:
            print('En', x, 'tienes $', round(criptomonedas_dic[x], 2))
            
    return sorted(criptomonedas_dic.items(), key=operator.itemgetter(1), reverse=True)

def revisar_bolsa_partes(cur, donde: str, bolsa: dict, acciones: dict) -> list:
    """Consulta la composición de las acciones o FIBRAS y actualiza sus precios."""
    diccionario = {}
    ejecutar = f'SELECT Simbolo, acciones FROM {donde}'
    cur.execute(ejecutar)
    filas = cur.fetchall()
    for x in filas:
        diccionario[x[0]] = x[1]
    
    bolsa_dic = dict()
    for llave in diccionario.keys():
        # Parche especial para el deslistado de América Móvil
        if llave == 'AMX':
            ticker_a_buscar = 'AMXB'
        else:
            ticker_a_buscar = llave

        # Determinamos si queremos el precio en pesos mexicanos (.MX)
        es_mexicano = (donde in ['FIBRAS', 'En_desarrollo'])

        # Obtenemos el precio usando nuestra función inteligente
        precio_unitario = obtener_precio(ticker_a_buscar, mexicano=es_mexicano)

        # Si por alguna razón una FIBRA sin '.MX' falla, hacemos un intento de rescate internacional
        if precio_unitario == 0.0 and donde == 'FIBRAS':
            precio_unitario = obtener_precio(ticker_a_buscar, mexicano=False)

        precio_total = precio_unitario * diccionario.get(llave)
        bolsa_dic[llave] = round(precio_total, 2)
    
    bolsa.update(bolsa_dic)
    if donde != 'FIBRAS':
        acciones.update(bolsa_dic)
    
    return sorted(bolsa_dic.items(), key=operator.itemgetter(1), reverse=True)

def sacar_valor(lista: list) -> float:
    """Suma los montos totales de una lista de tuplas."""
    valor = 0.0
    for x in lista:
        valor += x[1]
    return round(valor, 2)

def graficar(valor_total, valor_cripto, valor_acciones, valor_fibras, plata, cetes, 
             valor_eua, valor_en_desarrollo, valor_desarrollados, criptomonedas, eua, en_desarrollo, fibras, total,
             x=None, cripto=None, bolsa_lst=None, platalst=None, totalst=None, 
             depositoBolsa=None, depositoCripto=None, depositoTotal=None):
    """Genera las visualizaciones gráficas del portafolio histórico y actual."""
    x = [] if x is None else x
    cripto = [] if cripto is None else cripto
    bolsa_lst = [] if bolsa_lst is None else bolsa_lst
    platalst = [] if platalst is None else platalst
    totalst = [] if totalst is None else totalst
    depositoBolsa = [] if depositoBolsa is None else depositoBolsa
    depositoCripto = [] if depositoCripto is None else depositoCripto
    depositoTotal = [] if depositoTotal is None else depositoTotal

    with sqlite3.connect('portafolio.db') as con:
        cur = con.cursor()
        ejecutar = 'SELECT Activos.Activo, Monto_de_activos.Monto, Monto_de_activos.Fecha FROM Activos JOIN Monto_de_activos ON Monto_de_activos.Activo_id = Activos.id'
        
        for y in cur.execute(ejecutar):
            if y[0] == 'Criptomonedas':
                cripto.append(y[1])
            elif y[0] == 'Bolsa':
                bolsa_lst.append(y[1])
            elif y[0] == 'Plata':
                platalst.append(y[1])
            elif y[0] == 'Total':
                totalst.append(y[1])
            elif y[0] == 'DepositoBolsa':
                depositoBolsa.append(y[1])
            elif y[0] == 'DepositoCripto':
                depositoCripto.append(y[1])
            elif y[0] == 'DepositoTotal':
                depositoTotal.append(y[1])
        
        for fecha in cur.execute(ejecutar):
            if fecha[2] not in x:
                x.append(fecha[2])
    
    fig = plt.figure()
    ax1 = fig.add_subplot(1,2,1)
    ax2 = fig.add_subplot(4,4,3)
    ax3 = fig.add_subplot(4,4,7)
    ax4 = fig.add_subplot(4,4,11)
    ax5 = fig.add_subplot(4,4,15)
    ax6 = fig.add_subplot(4,4,4)
    ax7 = fig.add_subplot(4,4,8)
    ax8 = fig.add_subplot(4,4,12)

    ax1.plot(x, cripto, marker='o', color='orange', label='Criptomonedas')
    ax1.plot(x, bolsa_lst, marker='o', color='blue', label='Bolsa')
    ax1.plot(x, platalst, marker='o', color='gray', label='Plata')
    ax1.plot(x, totalst, marker='o', color='red', label='Total')
    ax1.plot(x, depositoBolsa, marker='o', color='blue', label='Depósito Bolsa', linestyle='dashed')
    ax1.plot(x, depositoCripto, marker='o', color='orange', label='Depósito Criptomonedas', linestyle='dashed')
    ax1.plot(x, depositoTotal, marker='o', color='red', label='Depósito Total', linestyle='dashed')
    ax1.set_xlabel('Fecha')
    ax1.set_ylabel('Monto')
    ax1.legend()
    ax1.grid()

    v_total = valor_total if valor_total > 0 else 1
    c = (valor_cripto * 100) / v_total
    a = (valor_acciones * 100) / v_total
    f = (valor_fibras * 100) / v_total
    p = (plata * 100) / v_total
    ct = (cetes * 100) / v_total
    
    tamaño = [c, a, f, p, ct]
    tamaño = [0.0 if (str(v) == 'nan' or v is None) else v for v in tamaño]
    cinta = ['Criptomonedas', 'Acciones', 'Fibras', 'Plata', 'Cetes']
    if sum(tamaño) > 0:
        ax2.pie(tamaño, labels=cinta, colors=['orange', 'blue', 'red', 'gray', 'green'], autopct='%1.1f%%')
    else:
        ax2.pie([1], labels=['Sin Activos'], colors=['#d3d3d3'])

    tamañoCripto = []
    cintaCripto = []
    v_cripto = valor_cripto if valor_cripto > 0 else 1
    for s in criptomonedas:
        tamañoCripto.append((s[1] * 100) / v_cripto)
        cintaCripto.append(s[0])
    if sum(tamañoCripto) > 0:
        ax3.pie(tamañoCripto, labels=cintaCripto, autopct='%1.1f%%')
    else:
        ax3.pie([1], labels=['Sin Criptos'], colors=['#d3d3d3'])

    v_acciones = valor_acciones if valor_acciones > 0 else 1
    america = (valor_eua * 100) / v_acciones
    viasDesarrollo = (valor_en_desarrollo * 100) / v_acciones
    primerMundo = (valor_desarrollados * 100) / v_acciones
    tamañoAc = [america, viasDesarrollo, primerMundo]
    cintaAc = ['E.U.A.', 'En desarrollo', 'Desarrollados']
    if sum(tamañoAc) > 0:
        ax4.pie(tamañoAc, labels=cintaAc, autopct='%1.1f%%')  
    else:
        ax4.pie([1], labels=['Sin Acciones'], colors=['#d3d3d3'])

    tamañoEUA = []
    cintaEUA = []
    v_eua = valor_eua if valor_eua > 0 else 1
    for s in eua:
        tamañoEUA.append((s[1] * 100) / v_eua)
        cintaEUA.append(s[0])
    if sum(tamañoEUA) > 0:
        ax5.pie(tamañoEUA, labels=cintaEUA, autopct='%1.1f%%')
    else:
        ax5.pie([1], labels=['Sin EUA'], colors=['#d3d3d3'])

    tamañoDesarrollo = []
    cintaDesarrollo = []
    v_desarrollo = valor_en_desarrollo if valor_en_desarrollo > 0 else 1
    for s in en_desarrollo:
        tamañoDesarrollo.append((s[1] * 100) / v_desarrollo)
        cintaDesarrollo.append(s[0])
    if sum(tamañoDesarrollo) > 0:
        ax6.pie(tamañoDesarrollo, labels=cintaDesarrollo, autopct='%1.1f%%')
    else:
        ax6.pie([1], labels=['Sin Emergentes'], colors=['#d3d3d3'])

    tamañoFibras = []
    cintaFibras = []
    v_fibras = valor_fibras if valor_fibras > 0 else 1
    for s in fibras:
        tamañoFibras.append((s[1] * 100) / v_fibras)
        cintaFibras.append(s[0])
    if sum(tamañoFibras) > 0:
        ax7.pie(tamañoFibras, labels=cintaFibras, autopct='%1.1f%%')
    else:
        ax7.pie([1], labels=['Sin FIBRAs'], colors=['#d3d3d3'])

    tamañoTotal = []
    cintaTotal = []
    for s in total:
        tamañoTotal.append((s[1] * 100) / v_total)
        cintaTotal.append(s[0])
    if sum(tamañoTotal) > 0:
        ax8.pie(tamañoTotal, labels=cintaTotal, autopct='%1.1f%%')
    else:
        ax8.pie([1], labels=['Sin Activos'], colors=['#d3d3d3'])

    plt.show()

def main():
    with sqlite3.connect('portafolio.db') as con:
        cur = con.cursor()

        bolsa = {}
        acciones = {}
        valores = {}

        # 1. Criptomonedas
        criptomonedas = revisar_criptomonedas(cur)
        valor_cripto = sacar_valor(criptomonedas)
        valores[1] = round(valor_cripto, 2)

        # 2. Bolsa
        eua = revisar_bolsa_partes(cur, 'EUA', bolsa, acciones)
        valor_eua = sacar_valor(eua)

        desarrollados = revisar_bolsa_partes(cur, 'Desarrollados', bolsa, acciones)
        valor_desarrollados = sacar_valor(desarrollados)

        en_desarrollo = revisar_bolsa_partes(cur, 'En_desarrollo', bolsa, acciones)
        valor_en_desarrollo = sacar_valor(en_desarrollo)

        # CORREGIDO: Pasamos "acciones" de forma posicional para evitar el error de "actions"
        fibras = revisar_bolsa_partes(cur, 'FIBRAS', bolsa, acciones)
        valor_fibras = sacar_valor(fibras)

        bolsa_ordenada = sorted(bolsa.items(), key=operator.itemgetter(1), reverse=True)
        valor_bolsa = sacar_valor(bolsa_ordenada)
        valores[2] = round(valor_bolsa, 2)

        acciones_ordenadas = sorted(acciones.items(), key=operator.itemgetter(1), reverse=True)
        valor_acciones = sacar_valor(acciones_ordenadas)

        # 3. Plata
        plata = revisar_plata(cur)
        valores[3] = plata

        # 4. Cetes
        cetes = 1450 + 380

        # Totales
        total = bolsa_ordenada + criptomonedas
        total.sort(key=lambda x: x[1], reverse=True)
        
        valor_total = valor_cripto + valor_bolsa + plata + cetes
        valores[4] = round(valor_total,2)

        # Depósitos
        valores[5] = 9135.35 + 1500 + 2000 + 1600 + 1550 + 2550
        valores[6] = 46220.03 + 950 + 510 + 1500
        valores[7] = valores[5] + valores[6]

        # Guardar histórico
        ahora = datetime.now()
        fecha = ahora.strftime('%Y-%m-%d %H:%M')
        for x in valores:
            datos = x, fecha, valores[x]
            cur.execute('INSERT INTO Monto_de_activos(Activo_id,Fecha,Monto) VALUES(?,?,?)', datos)

    # --- Salidas en consola ---
    print('\nTienes $', valor_cripto, 'en Criptomonedas')
    print('\nTienes $', valor_eua, 'en acciones de EUA.')
    print('Tienes $', valor_desarrollados, 'en acciones de economías desarrolladas.')
    print('Tienes $', valor_en_desarrollo, 'en acciones de economías en vías de desarrollo.')
    print('Es decir, tienes $', valor_acciones, 'en acciones.')
    print('Y tienes $', valor_fibras, 'en FIBRAS.')
    print('Por lo tanto, en bolsa tienes $', valor_bolsa, 'en la Bolsa.')
    print('\nTienes $', plata, 'invertido en Plata.')
    print('\nY tienes $', cetes, 'en Cetes.')
    print('\nPor lo que tienes $', valor_total, 'invertido.')

    rendimiento_cripto = ((valores[1] * 100) / valores[6]) - 100
    print('\nTienes un rendimiento en criptomonedas de', round(rendimiento_cripto, 2), '%')
    rendimiento_bolsa = ((valores[2] * 100) / valores[5]) - 100
    print('Tienes un rendimiento en bolsa de', round(rendimiento_bolsa, 2), '%')
    rendimiento_total = ((valores[4] * 100) / valores[7]) - 100
    print('Y tienes un rendimiento total de', round(rendimiento_total, 2), '%')

    # Graficar
    graficar(
        valor_total=valor_total, valor_cripto=valor_cripto, valor_acciones=valor_acciones, 
        valor_fibras=valor_fibras, plata=plata, cetes=cetes, valor_eua=valor_eua, 
        valor_en_desarrollo=valor_en_desarrollo, valor_desarrollados=valor_desarrollados, 
        criptomonedas=criptomonedas, eua=eua, en_desarrollo=en_desarrollo, fibras=fibras, total=total
    )

    input('\nPresione Enter para cerrar.')

if __name__ == "__main__":
    main()