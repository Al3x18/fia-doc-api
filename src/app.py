from datetime import datetime
from functools import wraps
import logging
import os
import json
import secrets
from flask import Flask, jsonify, render_template, Response, request, send_file
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
from utils.track_assets_utils import normalize_track_name, get_track_assets_dirs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration constants
FIA_DOCUMENTS_URL = 'https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/'
BROWSER_LAUNCH_OPTIONS = {
    'headless': True,
    # Railway containers have a small /dev/shm allocation. Keeping Chromium's
    # shared-memory files under /tmp avoids renderer crashes on document pages.
    'args': ['--disable-dev-shm-usage']
}

def require_api_key(view_function):
    """Require the API key configured in the FIA_DOCS_API_KEY environment variable."""
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        configured_key = os.environ.get('FIA_DOCS_API_KEY', '')
        if not configured_key:
            logger.error('FIA_DOCS_API_KEY is not configured')
            return jsonify({'error': 'API key authentication is not configured'}), 503

        provided_key = request.headers.get('X-API-Key', '')
        if not provided_key:
            return jsonify({'error': 'X-API-Key header is required'}), 401

        if not secrets.compare_digest(provided_key, configured_key):
            return jsonify({'error': 'Invalid API key'}), 403

        return view_function(*args, **kwargs)

    return wrapped_view

def get_server_version() -> str:
    """
    Read server version from local JSON config.
    """
    project_root = os.path.abspath(os.path.join(app.root_path, '..'))
    version_file_path = os.path.join(project_root, 'server_info.json')

    try:
        with open(version_file_path, 'r', encoding='utf-8') as version_file:
            payload = json.load(version_file)
            version = payload.get('version')
            if isinstance(version, str) and version.strip():
                return version.strip()
    except Exception as e:
        logger.warning(f"Could not read server version from {version_file_path}: {e}")

    return 'unknown'

@app.route('/', methods=['GET'])
def api_documentation():
    """
    API Documentation endpoint - renders HTML page
    """
    return render_template('documentation.html',
                         title="FIA Documents API",
                         version=get_server_version(),
                         description="API for retrieving and downloading FIA Formula 1 documents",
                            base_url="http://localhost:4050/")

@app.route('/health', methods=['GET'])
def health_check():
    """Lightweight deployment health check; it intentionally does not start Chromium."""
    return jsonify({'status': 'ok'}), 200

@app.route('/fia-documents', methods=['GET'])
@require_api_key
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
        browser = p.chromium.launch(**BROWSER_LAUNCH_OPTIONS)
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
            
            # If season selection failed (e.g. new season data not yet available), reload page and try with previous year as fallback
            if not season_selected:
                current_year = datetime.now().year
                previous_year = current_year - 1
                fallback_season = f"SEASON {previous_year}"
                logger.info(f"Season {season} not available, reloading page and trying fallback: {fallback_season}\n")
                
                # Reload the page
                page.goto(FIA_DOCUMENTS_URL, wait_until='networkidle')
                page.wait_for_selector('.select-field-wrapper')
                
                # Try with previous year
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
@require_api_key
def download_document():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400

    try:
        response, filename = download_file(url=url)
        if response and filename:
            flask_response = Response(
                response.iter_content(chunk_size=8192),
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'application/pdf'
                }
            )
            flask_response.call_on_close(response.close)
            return flask_response
        else:
            return jsonify({'error': 'Only HTTPS documents hosted on fia.com are allowed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-seasons-available', methods=['GET'])
@require_api_key
def get_seasons_available():
    """
    Get all available seasons from FIA documents page
    """
    try:
        logger.info("STARTING SEASONS RETRIEVAL...\n")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(**BROWSER_LAUNCH_OPTIONS)
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
@require_api_key
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
            browser = p.chromium.launch(**BROWSER_LAUNCH_OPTIONS)
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
@require_api_key
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
            browser = p.chromium.launch(**BROWSER_LAUNCH_OPTIONS)
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


@app.route('/track-image', methods=['GET'])
def get_track_image():
    """
    Return track PNG image based on `track_name` query parameter.
    Example: /track-image?track_name=Bahrain%20International%20Circuit
    """
    track_name = request.args.get('track_name', '').strip()
    if not track_name:
        return jsonify({'error': 'track_name query parameter is required'}), 400

    requested = normalize_track_name(track_name)
    candidate_paths = []

    for assets_dir in get_track_assets_dirs(app_root_path=app.root_path):
        if not os.path.isdir(assets_dir):
            continue

        for entry in os.listdir(assets_dir):
            file_path = os.path.join(assets_dir, entry)
            if not os.path.isfile(file_path) or not entry.lower().endswith('.png'):
                continue

            base_name, _ = os.path.splitext(entry)
            if normalize_track_name(base_name) == requested:
                return send_file(file_path, mimetype='image/png')

            candidate_paths.append(file_path)

    if not candidate_paths:
        return jsonify({'error': 'f1Tracks directory not found or contains no PNG files'}), 404

    return jsonify({
        'error': f'No PNG found for track_name "{track_name}"'
    }), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4050))  # Use 4050 in local, otherwise the PORT of Railway
    app.run(host='0.0.0.0', port=port)
