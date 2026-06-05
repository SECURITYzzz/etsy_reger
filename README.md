  # Etsy Account Creator

Automated registration of Etsy accounts with email confirmation, proxy rotation, fingerprint emulation, and captcha solving.

[Русская версия](README.ru.md)

## Features

- Multi-threaded registration with configurable concurrency
- Proxy support (HTTP) with automatic rotation and blacklisting of dead proxies
- Email ordering and confirmation via Anymessage API
- reCAPTCHA Enterprise solving via 2Captcha
- Full browser fingerprint emulation (WebGL, canvas, fonts, etc.)
- DataDome bypass via external Go TLS client (tls_client_app.exe)
- Session persistence: cookies and headers saved for each account
- Detailed logging to console and file

## Project Structure

```
├── main.py               # Entry point, environment setup, process management
├── manager.py            # Registration orchestration, email and proxy management
├── worker.py             # Low-level Etsy interaction, session handling
├── fingerprint.py        # Browser fingerprint generator
├── functions.py          # Utilities (password generation, path helpers)
├── headers.py            # Static HTTP headers templates
├── names.py              # First name pool for registration
├── tls_client_app.exe    # External Go binary
├── config/
│   ├── settings.env      # API keys and settings (ignored by git)
│   ├── proxies.txt       # List of HTTP proxies (ignored by git)
│   └── recaptcha_tokens.json
├── output/               # Created accounts in JSON format
├── output_json/          # Cookies in JSON format (Playwright-compatible)
└── requirements.txt      # Python dependencies
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/etsy-reger.git
cd etsy-reger
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

3. Create configuration files:
   - config/settings.env with API keys
   - config/proxies.txt with one HTTP proxy per line (ip:port or user:pass@ip:port)

## Usage

Run the main script:

```bash
python main.py
```

Press Ctrl+C to gracefully stop all workers and shut down the Go server.

## Configuration

Create config/settings.env with the following keys:

- ANYMESSAGE=your_anymessage_token
- RUCAPTCHA=your_2captcha_key
- THREADS_NUM=10

## Notes

- The Go TLS client performs TLS handshake spoofing to mimic Chrome's JA3/JA4 fingerprint and bypass Etsy's TLS inspection.
- All created accounts are stored in output/ with full cookies and headers.

## License

This project is intended for educational purposes only.
