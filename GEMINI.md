# Workspace Instructions & Project Rules

## 1. File Persistence & Integrity
- Standard editor file tools are used; ensure files are never left in a truncated or 0-byte state.

## 2. Environment Variables & Security
- Keep `.env` ignored in `.gitignore` to prevent leaking API credentials.
- Keep `.env.example` up-to-date as a reference template for required environment variables.
- Use `python-dotenv` (`load_dotenv()`) in `config.py` for seamless local testing.

## 3. Dependency Management (Windows)
- Maintain `requirements.txt` with compatible packages for Windows (e.g. `pycryptodome` for Pyrogram crypto operations without requiring MSVC C++ Build Tools).
