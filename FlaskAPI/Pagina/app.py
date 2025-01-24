
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import pandas as pd
import joblib
from io import BytesIO

app = Flask(__name__)

# Configurar CORS para permitir solicitudes desde http://127.0.0.1:5500
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})

# Cargar el modelo usando joblib
model_path = "modelo_detecfraude.pkl"
model = joblib.load(model_path)

# Asegúrate de incluir todas las columnas que el modelo espera
model_columns = [
    'step', 'amount', 'oldbalanceOrg', 'newbalanceOrig',
    'oldbalanceDest', 'newbalanceDest', 'type_CASH_IN',
    'type_CASH_OUT', 'type_DEBIT', 'type_PAYMENT', 'type_TRANSFER'
]

@app.route('/')
def index():
    return render_template('upload.html')

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
        
        data_transformed = data_with_dummies.reindex(columns=model_columns, fill_value=0)
        
        predictions = model.predict(data_transformed)
        fraudulent_count = sum(predictions)
        total_transactions = len(data)

        return jsonify({
            "message": f"Se detectaron {fraudulent_count} transacciones fraudulentas de {total_transactions} transacciones."
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)
