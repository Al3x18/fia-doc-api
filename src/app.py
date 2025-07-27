from flask import Flask, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

@app.route('/fia-documents', methods=['GET'])
def get_fia_documents():
    return jsonify({'message': 'FIA documents enpoint'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4050, debug=True)
