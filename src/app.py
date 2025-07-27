import logging
from flask import Flask, jsonify, render_template
from playwright.sync_api import sync_playwright
from utils.playwright_utils import select_option_by_type, get_docs, download_file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from flask import request, Response

app = Flask(__name__)

@app.route('/', methods=['GET'])
def api_documentation():
    """
    API Documentation endpoint - renders HTML page
    """
    return render_template('documentation.html',
                         title="FIA Documents API",
                         version="1.0.0",
                         description="API for retrieving and downloading FIA Formula 1 documents",
                         base_url="http://localhost:4050")

@app.route('/fia-documents', methods=['GET'])
def get_fia_documents():
    # Configuration constants
    URL = 'https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/'

    SELECT_FIELD_SEASON_DEFAULT_VALUE = "Season"
    SELECT_FIELD_CHAMPIONSHIP_DEFAULT_VALUE = "Championship"
    SELECT_FIELD_EVENT_DEFAULT_VALUE = "Event"

    SEASON_FALLBACK_VALUE = "SEASON 2025"
    CHAMPIONSHIP_FALLBACK_VALUE = "FIA Formula One World Championship"
    EVENT_FALLBACK_VALUE = ""  # Leave empty to skip event selection

    # Get optional parameters with default values defined above
    season = request.args.get('season', SEASON_FALLBACK_VALUE)
    championship = request.args.get('championship', CHAMPIONSHIP_FALLBACK_VALUE)
    event = request.args.get('event', EVENT_FALLBACK_VALUE)

    documents = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until='networkidle')

        page.wait_for_selector('.select-field-wrapper')

        # Select options in order
        logger.info("STARTING SELECTIONS...\n")
        logger.info("SELECTED VALUES:")
        logger.info(f"Season: {season}")
        logger.info(f"Championship: {championship}")
        logger.info(f"Event: {event}\n")

        # The page will be updated every selection, this is managed in the select_option_by_type function
        if season:
            select_option_by_type(page=page, select_field_name=SELECT_FIELD_SEASON_DEFAULT_VALUE, option_text=season)

        if championship:
            select_option_by_type(page=page, select_field_name=SELECT_FIELD_CHAMPIONSHIP_DEFAULT_VALUE, option_text=championship)
        
        if event:
            select_option_by_type(page=page, select_field_name=SELECT_FIELD_EVENT_DEFAULT_VALUE, option_text=event)
        else:
            logger.info("SKIPPING EVENT SELECTION (event parameter EMPTY) GETTING DOCS FOR LAST EVENT\n")

        # Get documents after all selections are made
        logger.info("GETTING DOCUMENTS...\n")
        documents = get_docs(page=page)

        browser.close()

    return jsonify({
        'message': 'FIA documents retrieved successfully',
        'count': len(documents),
        'documents': documents
    })

@app.route('/download-fia-doc', methods=['GET'])
def download_document():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400

    try:
        response, filename = download_file(url=url)
        if response and filename:
            return Response(
                response.iter_content(chunk_size=8192),
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'application/pdf'
                }
            )
        else:
            return jsonify({'error': 'Failed to download file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4050, debug=False)
