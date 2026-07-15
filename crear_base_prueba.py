import sqlite3
from datetime import datetime

def inicializar_base_prueba():
    # Se conecta (y crea si no existe) a portafolio.db
    con = sqlite3.connect('portafolio.db')
    cur = con.cursor()

    print("Creando tablas estructurales...")
    
    # 1. Tabla Plata
    cur.execute('DROP TABLE IF EXISTS Plata')
    cur.execute('CREATE TABLE Plata (onza REAL)')
    
    # 2. Tablas de Criptomonedas
    cur.execute('DROP TABLE IF EXISTS Criptomonedas')
    cur.execute('CREATE TABLE Criptomonedas (id INTEGER PRIMARY KEY AUTOINCREMENT, Nombre TEXT)')
    
    cur.execute('DROP TABLE IF EXISTS Cantidades_en_criptomonedas')
    cur.execute('CREATE TABLE Cantidades_en_criptomonedas (Cripto_id INTEGER, Monto REAL)')
    
    # 3. Tablas de Bolsa (GBM)
    cur.execute('DROP TABLE IF EXISTS EUA')
    cur.execute('CREATE TABLE EUA (Simbolo TEXT, acciones REAL)')
    
    cur.execute('DROP TABLE IF EXISTS Desarrollados')
    cur.execute('CREATE TABLE Desarrollados (Simbolo TEXT, acciones REAL)')
    
    cur.execute('DROP TABLE IF EXISTS En_desarrollo')
    cur.execute('CREATE TABLE En_desarrollo (Simbolo TEXT, acciones REAL)')
    
    cur.execute('DROP TABLE IF EXISTS FIBRAS')
    cur.execute('CREATE TABLE FIBRAS (Simbolo TEXT, acciones REAL)')
    
    # 4. Tablas de Historial y Catálogos
    cur.execute('DROP TABLE IF EXISTS Activos')
    cur.execute('CREATE TABLE Activos (id INTEGER PRIMARY KEY, Activo TEXT)')
    
    cur.execute('DROP TABLE IF EXISTS Monto_de_activos')
    cur.execute('''
        CREATE TABLE Monto_de_activos (
            Activo_id INTEGER, 
            Fecha TEXT, 
            Monto REAL
        )
    ''')

    print("Insertando datos de prueba balanceados...")
    
    # Insertar Onzas de Plata
    cur.execute('INSERT INTO Plata (onza) VALUES (?)', (5.0,))
    
    # Insertar Criptomonedas de prueba (Mapeo por ID)
    cur.executemany('INSERT INTO Criptomonedas (id, Nombre) VALUES (?,?)', [(1, 'BTC'), (2, 'ETH'), (3, 'LTC')])
    cur.executemany('INSERT INTO Cantidades_en_criptomonedas (Cripto_id, Monto) VALUES (?,?)', [(1, 0.02), (2, 0.15), (3, 0.5)])
    
    # Insertar Activos de Bolsa internacionales y locales
    cur.executemany('INSERT INTO EUA (Simbolo, acciones) VALUES (?,?)', [('AAPL', 10), ('MSFT', 5)])
    cur.executemany('INSERT INTO Desarrollados (Simbolo, acciones) VALUES (?,?)', [('EZU', 20)])
    
    # Cambiamos el activo vacío por ALSEA de la Bolsa Mexicana de Valores (BMV)
    cur.executemany('INSERT INTO En_desarrollo (Simbolo, acciones) VALUES (?,?)', [('ALSEA', 50)])
    
    # FIBRAS (Formato original compatible con yfinance al añadirle .MX directamente)
    cur.executemany('INSERT INTO FIBRAS (Simbolo, acciones) VALUES (?,?)', [('FMTY14', 300), ('FIHO12', 200)])

    # Insertar IDs de Activos fijos (Requeridos por la lógica de lectura y graficación)
    activos_id = [
        (1, 'Criptomonedas'),
        (2, 'Bolsa'),
        (3, 'Plata'),
        (4, 'Total'),
        (5, 'DepositoBolsa'),
        (6, 'DepositoCripto'),
        (7, 'DepositoTotal')
    ]
    cur.executemany('INSERT INTO Activos (id, Activo) VALUES (?,?)', activos_id)

    # Insertar un registro histórico base previo para evitar listas vacías en las líneas de Matplotlib
    fecha_antigua = "2026-06-14 09:00"
    historico_prueba = [
        (1, fecha_antigua, 12000.0),  # Criptomonedas anterior
        (2, fecha_antigua, 25000.0),  # Bolsa anterior
        (3, fecha_antigua, 4000.0),   # Plata anterior
        (4, fecha_antigua, 42000.0),  # Total anterior
        (5, fecha_antigua, 18000.0),  # Depósito Bolsa anterior
        (6, fecha_antigua, 30000.0),  # Depósito Cripto anterior
        (7, fecha_antigua, 48000.0)   # Depósito Total anterior
    ]
    cur.executemany('INSERT INTO Monto_de_activos (Activo_id, Fecha, Monto) VALUES (?,?,?)', historico_prueba)

    con.commit()
    con.close()
    print("¡Base de datos 'portafolio.db' generada e inicializada con éxito!")

if __name__ == "__main__":
    inicializar_base_prueba()