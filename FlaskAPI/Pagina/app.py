from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import joblib
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

# Configura tu aplicación Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})

# Cargar modelo
model_path = "modelo_detecfraude.pkl"
model = joblib.load(model_path)

# Configura las credenciales de la API de Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = r"C:\Users\cande\Documents\No Country\Fraude_Cero\data\credenciales.json"

credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# ID de la carpeta compartida en Google Drive
DRIVE_FOLDER_ID = '1z1zWFPLl1fljwqDHH0bzcObOokD3mWCk'

# Ruta de columnas esperadas por el modelo
model_columns = [
    'step', 'amount', 'oldbalanceOrg', 'newbalanceOrig',
    'oldbalanceDest', 'newbalanceDest', 'type_CASH_IN',
    'type_CASH_OUT', 'type_DEBIT', 'type_PAYMENT', 'type_TRANSFER'
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No se recibió ningún archivo"}), 400

        file = request.files["file"]
        
        # Leer el archivo CSV
        try:
            data = pd.read_csv(file)
        except Exception as e:
            return jsonify({"error": f"Error al leer el archivo CSV: {str(e)}"}), 400

        required_columns = [
            'step', 'type', 'amount', 'oldbalanceOrg',
            'newbalanceOrig', 'oldbalanceDest', 'newbalanceDest'
        ]
        if not all(col in data.columns for col in required_columns):
            return jsonify({"error": "Faltan columnas en los datos ingresados"}), 400

        # Convertir la columna 'type' a variables dummy
        columns_to_encode = ['type']
        data_with_dummies = pd.get_dummies(data, columns=columns_to_encode, drop_first=False)
        
        # Asegurarse de que todas las columnas esperadas estén presentes
        data_transformed = data_with_dummies.reindex(columns=model_columns, fill_value=0)
        
        predictions = model.predict(data_transformed)
        data['predictions'] = predictions

        fraudulent_count = sum(predictions)
        total_transactions = len(data)
        
        # Guardar los datos procesados
        processed_file_path = os.path.join(os.getcwd(), 'archivo_procesado.csv')
        data.to_csv(processed_file_path, index=False)

        # Buscar si el archivo ya existe en la carpeta
        query = f"'{DRIVE_FOLDER_ID}' in parents and name='archivo_procesado.csv' and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        # Si el archivo existe, eliminarlo
        if files:
            for file in files:
                drive_service.files().delete(fileId=file['id']).execute()
                print(f"Archivo existente eliminado: {file['name']}")

        # Subir el nuevo archivo a Google Drive
        file_metadata = {
            'name': 'archivo_procesado.csv',
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(processed_file_path, mimetype='text/csv')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"Archivo subido correctamente: {file}")

        # URL del dashboard de Tableau
        dashboard_url = "https://public.tableau.com/views/Prueba_FraudeCero/Dashboard1?:embed=y&:display_count=yes"

        return jsonify({
            "message": f"Se detectaron {fraudulent_count} transacciones fraudulentas de {total_transactions} transacciones.",
            "file_id": file.get('id'),
            "show_dashboard": True,
            "dashboard_url": dashboard_url  # Añadir la URL del dashboard
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(port=5000, debug=True)