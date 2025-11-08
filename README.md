# PDF → Word Converter (Render-ready)

This repo runs a Flask service that converts PDFs to Word (.docx) by rendering each PDF page as an image and inserting pages into a Word document.

**Tuned for**: Render free tier, PDFs up to ~20 MB (use DPI <= 300).

## Files
- `server.py` — Flask app exposing `/convert` endpoint
- `requirements.txt`, `Dockerfile`, `.dockerignore`

## Deploy to Render (quick)
1. Push this repo to GitHub.
2. Create an account at https://render.com.
3. Select **New → Web Service → Connect a repository** and choose this repo.
4. Render will auto-detect Dockerfile and build. Use default service plan (Free).
5. After deployment, you get a URL: `https://<your-app>.onrender.com`

## Test locally with curl
```bash
curl -F "file=@your.pdf" -F "dpi=300" -F "fix_overlay=true" https://<your-app>.onrender.com/convert --output out.docx
