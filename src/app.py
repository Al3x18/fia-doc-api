from datetime import datetime
import logging
import os
import json
from flask import Flask, jsonify, render_template, Response
from playwright.sync_api import sync_playwright
from utils.playwright_utils import (
    select_option_by_type,
    get_docs,
    download_file,
    get_available_seasons,
    get_available_championships,
    get_available_events,
    normalize_season_format
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from flask import request, Response

app = Flask(__name__)

# Configuration constants
FIA_DOCUMENTS_URL = 'https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/'

@app.route('/', methods=['GET'])
def api_documentation():
    """
    API Documentation endpoint - renders HTML page
    """
    return render_template('documentation.html',
                         title="FIA Documents API",
                         version="1.0.1",
                         description="API for retrieving and downloading FIA Formula 1 documents",
                            base_url="http://localhost:4050/")

@app.route('/fia-documents', methods=['GET'])
def get_fia_documents():
    # Configuration constants
    SELECT_FIELD_SEASON_DEFAULT_VALUE = "Season"
    SELECT_FIELD_CHAMPIONSHIP_DEFAULT_VALUE = "Championship"
    SELECT_FIELD_EVENT_DEFAULT_VALUE = "Event"

    SEASON_FALLBACK_VALUE = f"SEASON {datetime.now().year}"
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

        page.goto(FIA_DOCUMENTS_URL, wait_until='networkidle')

        page.wait_for_selector('.select-field-wrapper')

        # Select options in order
        logger.info("STARTING SELECTIONS...\n")
        logger.info("SELECTED VALUES:")
        logger.info(f"Season: {season}")
        logger.info(f"Championship: {championship}")
        logger.info(f"Event: {event}\n")

        # The page will be updated every selection, this is managed in the select_option_by_type function
        if season:
            season_selected = select_option_by_type(page=page, select_field_name=SELECT_FIELD_SEASON_DEFAULT_VALUE, option_text=season)
            
            # If season selection failed (e.g. new season data not yet available), try with previous year as fallback
            if not season_selected:
                current_year = datetime.now().year
                previous_year = current_year - 1
                fallback_season = f"SEASON {previous_year}"
                logger.info(f"Season {season} not available, trying fallback: {fallback_season}\n")
                season_selected = select_option_by_type(page=page, select_field_name=SELECT_FIELD_SEASON_DEFAULT_VALUE, option_text=fallback_season)
                
                if season_selected:
                    season = fallback_season
                    logger.info(f"Successfully selected fallback season: {fallback_season}\n")
                    # Wait for page to stabilize after fallback selection (navigation may occur)
                    page.wait_for_selector('.select-field-wrapper', timeout=1000)
                    page.wait_for_timeout(500)  # Additional wait for page to be fully ready
                else:
                    logger.error(f"Failed to select both {season} and fallback {fallback_season}\n")

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

    response_data = {
        'message': 'FIA documents retrieved',
        'documents': documents
    }

    # Use Response + json.dumps instead of jsonify() to preserve field ordering
    # jsonify() may reorder dictionary keys during serialization, but json.dumps()
    # respects the insertion order of Python dictionaries (Python 3.7+)
    # This ensures 'message' appears before 'documents' and 'info' before 'docs'
    return Response(
        json.dumps(response_data, ensure_ascii=False, indent=2),
        mimetype='application/json'
    )

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

@app.route('/get-seasons-available', methods=['GET'])
def get_seasons_available():
    """
    Get all available seasons from FIA documents page
    """
    try:
        logger.info("STARTING SEASONS RETRIEVAL...\n")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info("NAVIGATING TO FIA DOCUMENTS PAGE...")
            page.goto(FIA_DOCUMENTS_URL, wait_until='networkidle')
            page.wait_for_selector('.select-field-wrapper')
            
            # Get available seasons
            logger.info("EXTRACTING AVAILABLE SEASONS...\n")
            seasons = get_available_seasons(page=page)
            
            logger.info(f"FOUND {len(seasons)} AVAILABLE SEASONS")
            for i, season in enumerate(seasons, 1):
                logger.info(f"  {i}. {season}")
            logger.info("")
            
            browser.close()
            
        response_data = {
            'message': 'Available seasons retrieved',
            'count': len(seasons),
            'seasons': seasons
        }
        
        logger.info("SEASONS RETRIEVAL COMPLETED SUCCESSFULLY\n")
        
        return Response(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error retrieving seasons: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-championships-available', methods=['GET'])
def get_championships_available():
    """
    Get all available championships for a season
    Optional parameter: season - if not provided, uses current default
    """
    # Get optional season parameter
    season = request.args.get('season')
    
    try:
        logger.info("STARTING CHAMPIONSHIPS RETRIEVAL...\n")
        logger.info("PARAMETERS:")
        logger.info(f"Season (original): {season if season else 'default'}")
        
        # Normalize season format if provided
        normalized_season = normalize_season_format(season) if season else None
        if season and normalized_season != season:
            logger.info(f"Season (normalized): {normalized_season}")
        logger.info("")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info("NAVIGATING TO FIA DOCUMENTS PAGE...")
            page.goto(FIA_DOCUMENTS_URL, wait_until='networkidle')
            page.wait_for_selector('.select-field-wrapper')
            
            # Select season if provided
            if season:
                logger.info(f"SELECTING SEASON: {normalized_season}")
            else:
                logger.info("USING DEFAULT SEASON SELECTION")
            
            # Get available championships (optionally for a specific season)
            logger.info("EXTRACTING AVAILABLE CHAMPIONSHIPS...\n")
            championships = get_available_championships(page=page, season=season)
            
            logger.info(f"FOUND {len(championships)} AVAILABLE CHAMPIONSHIPS")
            for i, championship in enumerate(championships, 1):
                logger.info(f"  {i}. {championship}")
            logger.info("")
            
            browser.close()
            
        response_data = {
            'message': 'Available championships retrieved',
            'season': season if season else 'default',
            'count': len(championships),
            'championships': championships
        }
        
        logger.info("CHAMPIONSHIPS RETRIEVAL COMPLETED SUCCESSFULLY\n")
        
        return Response(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error retrieving championships: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-gp-available', methods=['GET'])
def get_gp_available():
    """
    Get all available Grand Prix events for a season
    Optional parameter: season - if not provided, uses current default
    """
    # Get optional season parameter
    season = request.args.get('season')
    
    try:
        logger.info("STARTING GRAND PRIX EVENTS RETRIEVAL...\n")
        logger.info("PARAMETERS:")
        logger.info(f"Season (original): {season if season else 'default'}")
        
        # Normalize season format if provided
        normalized_season = normalize_season_format(season) if season else None
        if season and normalized_season != season:
            logger.info(f"Season (normalized): {normalized_season}")
        logger.info("")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info("NAVIGATING TO FIA DOCUMENTS PAGE...")
            page.goto(FIA_DOCUMENTS_URL, wait_until='networkidle')
            page.wait_for_selector('.select-field-wrapper')
            
            # Select season if provided
            if season:
                logger.info(f"SELECTING SEASON: {normalized_season}")
            else:
                logger.info("USING DEFAULT SEASON SELECTION")
            
            # Get available events/Grand Prix (optionally for a specific season)
            logger.info("EXTRACTING AVAILABLE GRAND PRIX EVENTS...\n")
            events = get_available_events(page=page, season=season)
            
            logger.info(f"FOUND {len(events)} AVAILABLE GRAND PRIX EVENTS")
            for i, event in enumerate(events, 1):
                logger.info(f"  {i}. {event}")
            logger.info("")
            
            browser.close()
            
        response_data = {
            'message': 'Available Grand Prix events retrieved',
            'season': season if season else 'default',
            'count': len(events),
            'events': events
        }
        
        logger.info("GRAND PRIX EVENTS RETRIEVAL COMPLETED SUCCESSFULLY\n")
        
        return Response(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error retrieving Grand Prix events: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4050))  # Use 4050 in local, otherwise the PORT of Railway
    app.run(host='0.0.0.0', port=port)