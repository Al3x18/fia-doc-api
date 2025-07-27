# FIA Documents API

A Flask-based REST API that scrapes and provides access to official FIA Formula 1 documents from the FIA website. Get race classifications, stewards' decisions, technical documents, and more in a structured JSON format.

## 🏎️ Features

- **Real-time Web Scraping**: Automated extraction from the official FIA documents portal
- **Document Downloads**: Direct PDF downloads without server-side storage
- **Data Processing**: Automatic date formatting (ISO 8601) and URL conversion
- **Interactive Documentation**: Beautiful dark-themed API documentation with live testing
- **Flexible Filtering**: Filter by season, championship, and specific events
- **Multiple Document Types**: Race results, qualifying, practice, stewards' decisions, and technical docs

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/fia-doc-api.git
   cd fia-doc-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Run the application**
   ```bash
   python src/app.py
   ```

The API will be available at `http://localhost:4050`

## 📚 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Interactive API documentation |
| `GET` | `/fia-documents` | Retrieve FIA documents with optional filters |
| `GET` | `/download-fia-doc` | Download specific documents by URL |

### Example Usage

```bash
# Get latest documents
curl "http://localhost:4050/fia-documents"

# Get documents for specific event
curl "http://localhost:4050/fia-documents?event=Monaco%20Grand%20Prix"

# Get documents from previous season
curl "http://localhost:4050/fia-documents?season=SEASON%202024"

# Download a specific document
curl "http://localhost:4050/download-fia-doc?url=https://www.fia.com/sites/default/files/..."
```

### Response Format

```json
{
  "message": "FIA documents retrieved successfully",
  "count": 73,
  "documents": [
    {
      "gp_name": "AUSTRIAN GRAND PRIX",
      "season_year": "2024"
    },
    {
      "date": "2024-06-30T19:15:00",
      "published": "Published on 30.06.24 19:15 CET",
      "title": "Doc 75 - Championship Points",
      "url": "https://www.fia.com/sites/default/files/decision-document/..."
    }
  ]
}
```

## 🏗️ Project Structure

```
fia-doc-api/
├── src/
│   ├── app.py                 # Main Flask application
│   ├── static/css/style.css   # Dark-themed documentation styles
│   ├── templates/
│   │   └── documentation.html # Interactive API documentation
│   └── utils/
│       ├── __init__.py
│       └── playwright_utils.py # Web scraping utilities
├── requirements.txt           # Python dependencies
└── README.md
```

## 🛠️ Technologies Used

- **Backend**: Flask (Python web framework)
- **Web Scraping**: Playwright (headless browser automation)
- **HTTP Requests**: Requests library for file downloads
- **Frontend**: Vanilla HTML/CSS/JavaScript with dark theme
- **Date Processing**: Python datetime for ISO 8601 conversion

## 📋 Available Document Types

- **Race Results**: Final classifications, fastest laps, lap charts
- **Qualifying Results**: Qualifying classifications and session reports  
- **Practice Results**: Free practice session timings and reports
- **Stewards' Decisions**: Penalties, investigations, and official rulings
- **Technical Documents**: Scrutineering reports, technical regulations
- **Administrative**: Entry lists, schedule changes, official notices

## ⚠️ Important Notes

- **Response Time**: Web scraping requests typically take 3-8 seconds due to browser automation
- **Data Source**: Dependent on FIA website structure (may break if they change their HTML)
- **Rate Limiting**: No built-in rate limiting - please be respectful of the FIA website
- **Real-time Data**: All operations are performed in real-time without data storage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚖️ Legal Disclaimer

This project is for educational and personal use only. It scrapes publicly available data from the FIA website. Please respect the FIA's terms of service and use this tool responsibly. The authors are not affiliated with or endorsed by the FIA.
