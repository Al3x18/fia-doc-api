import logging
import re
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
from playwright.sync_api import Error as PlaywrightError

# Configure logging
logger = logging.getLogger(__name__)

FIA_NAVIGATION_TIMEOUT_MS = 15_000
NEXT_SELECT_FIELD = {
    "Season": "Championship",
    "Championship": "Event",
}

def is_allowed_fia_url(url: str) -> bool:
    """Return True only for HTTPS URLs hosted by fia.com or one of its subdomains."""
    try:
        parsed_url = urlparse(url)
        hostname = (parsed_url.hostname or "").lower()
        return (
            parsed_url.scheme == "https"
            and (hostname == "fia.com" or hostname.endswith(".fia.com"))
        )
    except (TypeError, ValueError):
        return False

def normalize_season_format(season_input):
    """
    Normalize season input to FIA expected format.
    
    Args:
        season_input (str): Season in various formats (e.g., "2015", "SEASON 2015")
    
    Returns:
        str: Season in FIA format "SEASON YYYY"
    """
    if not season_input:
        return season_input
    
    # If already in correct format, return as is
    if season_input.upper().startswith("SEASON "):
        return season_input
    
    # If it's just a year (4 digits), add "SEASON " prefix
    if season_input.isdigit() and len(season_input) == 4:
        return f"SEASON {season_input}"
    
    # Otherwise return as is (might be a different format we don't know)
    return season_input

def _get_select_locator(*, page, select_field_name):
    """Locate a FIA select by the text of its placeholder option."""
    placeholder_text = re.compile(rf"^\s*{re.escape(select_field_name)}\s*$")
    placeholder = page.locator('option[value="0"]', has_text=placeholder_text)
    return page.locator(".select-field-wrapper").filter(has=placeholder).locator("select")

def _wait_for_page_after_selection(*, page, select_field_name) -> None:
    """Wait until the content required after a FIA selection is ready."""
    next_field_name = NEXT_SELECT_FIELD.get(select_field_name)
    if next_field_name:
        _get_select_locator(
            page=page,
            select_field_name=next_field_name
        ).wait_for(state="visible", timeout=FIA_NAVIGATION_TIMEOUT_MS)
        return

    # Event is the last selection; its destination must expose the event title.
    page.locator(".event-title.active").first.wait_for(
        state="visible",
        timeout=FIA_NAVIGATION_TIMEOUT_MS
    )

def select_option_by_type(*, page, select_field_name, option_text) -> bool:
    """
    Find and select from a specific select type on the FIA documents page.
    The page is updated after each selection.

    Args:
        page: Playwright page object
        select_field_name (str): Name of the select field to find ("Season", "Championship", "Event")
        option_text (str): Text of the option to select

    Returns:
        bool: True if selection was successful, False otherwise
    """
    select_locator = _get_select_locator(
        page=page,
        select_field_name=select_field_name
    )

    if select_locator.count() == 0:
        logger.warning(f"Select field {select_field_name} was not found")
        return False

    option_text_pattern = re.compile(rf"^\s*{re.escape(option_text)}\s*$")
    matching_option = select_locator.locator(
        "option",
        has_text=option_text_pattern
    )
    if matching_option.count() == 0:
        logger.warning(
            f"Option {option_text} was not found in {select_field_name}"
        )
        return False

    logger.info(f"Selecting {option_text} in {select_field_name}\n")

    try:
        selected_values = select_locator.select_option(label=option_text)
        if not selected_values or selected_values[0] == "0":
            logger.warning(f"Option {option_text} was not selected in {select_field_name}")
            return False

        expected_url = urljoin(page.url, selected_values[0])
        page.wait_for_url(
            expected_url,
            wait_until="domcontentloaded",
            timeout=FIA_NAVIGATION_TIMEOUT_MS
        )
        _wait_for_page_after_selection(
            page=page,
            select_field_name=select_field_name
        )
        return True
    except PlaywrightError as error:
        logger.warning(
            f"Failed to select {option_text} in {select_field_name}: {error}"
        )
        return False

def _is_navigation_context_error(error: PlaywrightError) -> bool:
    """Identify transient errors caused by a document being replaced."""
    message = str(error).lower()
    return (
        "execution context was destroyed" in message
        or "frame was detached" in message
    )

def get_select_options(*, page, select_field_name) -> list[str]:
    """
    Get all available options from a specific select field.
    
    Args:
        page: Playwright page object
        select_field_name (str): Name of the select field to find ("Season", "Championship", "Event")
    
    Returns:
        list[str]: List of available option texts (excluding the default option)
    """
    for attempt in range(2):
        try:
            select_locator = _get_select_locator(
                page=page,
                select_field_name=select_field_name
            )
            if select_locator.count() == 0:
                return []

            select_locator.wait_for(
                state="visible",
                timeout=FIA_NAVIGATION_TIMEOUT_MS
            )
            options = select_locator.locator('option:not([value="0"])')
            option_rows = options.evaluate_all(
                """elements => elements.map(option => ({
                    value: option.value,
                    text: (option.textContent || '').trim()
                }))"""
            )
            return [
                option["text"]
                for option in option_rows
                if option["value"] and option["text"]
            ]
        except PlaywrightError as error:
            if attempt == 1 or not _is_navigation_context_error(error):
                raise

            logger.info(
                f"DOM changed while reading {select_field_name}; retrying once"
            )
            page.wait_for_load_state(
                "domcontentloaded",
                timeout=FIA_NAVIGATION_TIMEOUT_MS
            )

    return []

def get_available_seasons(*, page) -> list[str]:
    """
    Get all available seasons from the FIA documents page.
    
    Args:
        page: Playwright page object
    
    Returns:
        list[str]: List of available seasons
    """
    return get_select_options(page=page, select_field_name="Season")

def get_available_championships(*, page, season=None) -> list[str]:
    """
    Get all available championships for a specific season.
    
    Args:
        page: Playwright page object
        season (str, optional): Season to select first. If None, uses default/current selection
    
    Returns:
        list[str]: List of available championships
    """
    # Select season first if provided
    if season:
        normalized_season = normalize_season_format(season)
        select_option_by_type(page=page, select_field_name="Season", option_text=normalized_season)
    
    return get_select_options(page=page, select_field_name="Championship")

def get_available_events(*, page, season=None) -> list[str]:
    """
    Get all available events/Grand Prix for a specific season.
    
    Args:
        page: Playwright page object
        season (str, optional): Season to select first. If None, uses default/current selection
    
    Returns:
        list[str]: List of available events/Grand Prix
    """
    # Select season first if provided
    if season:
        normalized_season = normalize_season_format(season)
        select_option_by_type(page=page, select_field_name="Season", option_text=normalized_season)
    
    return get_select_options(page=page, select_field_name="Event")

def get_docs(*, page) -> list[dict]:
    """
    Get all documents from the FIA documents page.

    Args:
        page: Playwright page object

    Returns:
        list: List with single object containing info and docs
    """

    # Locators are resolved against the current DOM and remain safe after navigation.
    gp_name = page.locator(".event-title.active").first.inner_text()

    season_text = (
        page.locator(".form-type-select")
        .nth(0)
        .locator("select option")
        .first
        .inner_text()
    )
    season_year = season_text.split(' ')[1]

    # Create the docs list for all documents
    docs_list = []

    # Find all document list items within ul.document-row-wrapper
    document_items = page.locator('ul.document-row-wrapper li')

    for index in range(document_items.count()):
        item = document_items.nth(index)
        # Get the href attribute from the link
        link_element = item.locator('a').first
        href = link_element.get_attribute('href') if link_element.count() else ""

        # Convert relative URL to absolute URL
        if href and href.startswith('/'):
            url = f"https://www.fia.com{href}"
        else:
            url = href

        # Get title from div with class 'title'
        title_element = item.locator('div.title').first
        title = title_element.inner_text().strip() if title_element.count() else ""

        # Get published date from div with class 'published'
        published_element = item.locator('div.published').first
        published_raw = (
            published_element.inner_text().strip()
            if published_element.count()
            else ""
        )

        # Convert to ISO format
        date = convert_fia_date_to_iso(date_text=published_raw)

        # Only add if we have at least a title
        if title:
            docs_list.append({
                'title': title,
                'published': published_raw,
                'date': date,
                'url': url
            })

    # Create the final structure with info and docs
    response = [{
        'info': {
            'season_year': season_year if season_year else "unknown",
            'gp_name': gp_name if gp_name else "unknown",
            'docs_count': len(docs_list)
        },
        'docs': docs_list
    }]

    return response


def download_file(*, url) -> tuple:
    """
    Get file content and metadata for streaming download.

    Args:
        url (str): The URL of the file to download

    Returns:
        tuple: (response_object, filename) or (None, None) if failed
    """

    if not is_allowed_fia_url(url):
        logger.warning("Rejected document download from a non-FIA URL")
        return None, None

    try:
        response = requests.get(url, stream=True, timeout=(10, 60))
        response.raise_for_status()

        # Requests follows redirects by default; validate the final destination too.
        if not is_allowed_fia_url(response.url):
            response.close()
            logger.warning("Rejected document download redirected outside fia.com")
            return None, None

        # Extract filename from URL
        parsed_url = urlparse(response.url)
        filename = parsed_url.path.split('/')[-1]
        if not filename:
            filename = "document.pdf"

        return response, filename

    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return None, None

def convert_fia_date_to_iso(*, date_text) -> str:
    """
    Convert FIA date format to ISO format.

    Args:
        date_text (str): Date in format "Published on 27.07.25 19:58 CET"

    Returns:
        str: Date in ISO format or original text if conversion fails
    """
    if not date_text or "Published on" not in date_text:
        return date_text

    try:
        # Extract date part after "Published on "
        date_part = date_text.replace("Published on ", "").replace(" CET", "")
        # Parse format "27.07.25 19:58"
        dt = datetime.strptime(date_part, "%d.%m.%y %H:%M")
        # Convert to ISO format string
        return dt.isoformat()
    except ValueError:
        return date_text  # Fallback to original if parsing fails
