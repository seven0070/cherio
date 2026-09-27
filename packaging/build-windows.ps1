$ErrorActionPreference = 'Stop'
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller pywebview
Push-Location frontend
npm ci
npm run build
Pop-Location
python -m unittest discover -s tests -v
python -m PyInstaller --onedir --name Cheerio --paths . --collect-submodules cheerio --collect-all smolagents --collect-all wikipediaapi --collect-all duckduckgo_search packaging/cheerio_launcher.py
python -m PyInstaller --noconsole --onedir --name BellaDesktop --paths . --collect-submodules bella --collect-submodules cheerio --collect-all smolagents --collect-all wikipediaapi --collect-all duckduckgo_search --collect-all webview --add-data "frontend/dist;bella_frontend" packaging/bella_desktop_launcher.py
Write-Host 'Candidate in dist\Cheerio\; manual Windows/Ollama/MCP/Cognee testing still required before release.'
