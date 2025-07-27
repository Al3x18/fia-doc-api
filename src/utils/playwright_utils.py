import logging
import requests
from urllib.parse import urlparse
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

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

    select_wrappers = page.query_selector_all('.select-field-wrapper')

    for wrapper in select_wrappers:
        select_element = wrapper.query_selector('select')

        if select_element:
            # Get the first option text to identify which select this is
            first_option = select_element.query_selector('option[value="0"]')
            current_select_type = first_option.inner_text() if first_option else ""

            if current_select_type == select_field_name:
                logger.info(f"Selecting {option_text} in {select_field_name}\n")
                select_element.select_option(label=option_text)
                page.wait_for_timeout(1500)  # Wait for page to be ready
                return True
    return False

def get_docs(*, page) -> list[dict]:
    """
    Get all documents from the FIA documents page.

    Args:
        page: Playwright page object

    Returns:
        list: List of document objects
    """

    documents: list[dict] = []

    #Get Gp Name from event-title CSS selector
    gp_name = page.query_selector(".event-title")

    #Get Season Year from form-type-select CSS selector
    season_year = page.query_selector_all(".form-type-select")[0].query_selector("select option").inner_text().split(' ')[1]

    # Add season year to document (if season_year is None add "unknown")
    # Add gp_name in document with name of gp (if gp_name is None add "unknown")
    documents.append({
        'season_year': season_year if season_year else "unknown",
        'gp_name': gp_name.inner_text() if gp_name else "unknown"
    })

    # Find all document list items within ul.document-row-wrapper
    document_items = page.query_selector_all('ul.document-row-wrapper li')

    for item in document_items:
        # Get the href attribute from the link
        link_element = item.query_selector('a')
        href = link_element.get_attribute('href') if link_element else ""

        # Convert relative URL to absolute URL
        if href and href.startswith('/'):
            url = f"https://www.fia.com{href}"
        else:
            url = href

        # Get title from div with class 'title'
        title_element = item.query_selector('div.title')
        title = title_element.inner_text().strip() if title_element else ""

        # Get published date from div with class 'published'
        published_element = item.query_selector('div.published')
        published_raw = published_element.inner_text().strip() if published_element else ""

        # Convert to ISO format
        date = convert_fia_date_to_iso(date_text=published_raw)

        # Only add if we have at least a title
        if title:
            documents.append({
                'title': title,
                'published': published_raw,
                'date': date,
                'url': url
            })

    return documents


def download_file(*, url) -> tuple:
    """
    Get file content and metadata for streaming download.

    Args:
        url (str): The URL of the file to download

    Returns:
        tuple: (response_object, filename) or (None, None) if failed
    """

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Extract filename from URL
        parsed_url = urlparse(url)
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
