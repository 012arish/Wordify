#!/usr/bin/env python3
"""
PDF -> Word conversion server (image-based exact replica).

Designed for Render (free tier). Handles PDFs up to ~20MB reliably when
DPI is set <= 300 and conversions are sequential.

Endpoint:
  POST /convert
    form field: file (PDF)
    optional form fields:
      - dpi (int, default 300)
      - fix_overlay (true/false, default true)

Returns: .docx file as attachment.
"""
import os
import io
import uuid
from flask import Flask, request, send_file, jsonify
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance
from docx import Document
from docx.shared import Inches
import numpy as np
import cv2

# Temporary directories in container (ephemeral)
UPLOAD_TMP = "/tmp/uploads"
OUT_TMP = "/tmp/out"
os.makedirs(UPLOAD_TMP, exist_ok=True)
os.makedirs(OUT_TMP, exist_ok=True)

app = Flask(__name__)
# Allow up to 25 MB uploads; Render may limit at infra level too
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))

def render_page_image(page, dpi=300):
    mat = fitz.Matrix(dpi/72.0, dpi/72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return img

def remove_black_overlays_pil(pil_img, dark_threshold=40, min_area_ratio=0.02):
    """Detect large dark rectangles and fill white to reveal underlying content."""
    img = np.array(pil_img)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((15,15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    removed = False
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_ratio * (w*h):
            continue
        x,y,ww,hh = cv2.boundingRect(cnt)
        if ww > 0.3*w or hh > 0.05*h or (hh > 0.15*h and ww > 0.15*w):
            cv2.rectangle(img, (x,y), (x+ww, y+hh), (255,255,255), thickness=-1)
            removed = True
    return Image.fromarray(img), removed

def images_to_docx(image_paths, out_docx_path, width_inches=6.0):
    doc = Document()
    for idx, p in enumerate(image_paths):
        doc.add_picture(p, width=Inches(width_inches))
        if idx < len(image_paths) - 1:
            doc.add_page_break()
    doc.save(out_docx_path)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok"})

@app.route("/convert", methods=["POST"])
def convert():
    """
    POST multipart/form-data:
      - file: PDF
      - dpi: optional (int)
      - fix_overlay: optional ("true"/"false")
    """
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error":"no file provided"}), 400

    # tiny validation
    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error":"only PDF allowed"}), 400

    dpi = int(request.form.get("dpi", 300))
    if dpi > 400:
        dpi = 400  # hard cap to avoid memory explosions
    fix_overlay = request.form.get("fix_overlay", "true").lower() != "false"

    uid = uuid.uuid4().hex
    in_pdf_path = os.path.join(UPLOAD_TMP, f"{uid}.pdf")
    uploaded.save(in_pdf_path)

    try:
        pdf = fitz.open(in_pdf_path)
    except Exception as e:
        # invalid PDF
        os.remove(in_pdf_path)
        return jsonify({"error":"failed opening pdf", "detail": str(e)}), 400

    temp_images = []
    try:
        for i, page in enumerate(pdf):
            img = render_page_image(page, dpi=dpi)

            if fix_overlay:
                img, removed = remove_black_overlays_pil(img)
                if removed:
                    img = ImageEnhance.Contrast(img).enhance(1.05)

            # Save optimized PNG
            img_path = os.path.join(OUT_TMP, f"{uid}_p{i+1}.png")
            img.save(img_path, format="PNG", optimize=True)
            temp_images.append(img_path)

        out_docx = os.path.join(OUT_TMP, f"{uid}.docx")
        images_to_docx(temp_images, out_docx, width_inches=6.0)

        # send file
        return send_file(out_docx, as_attachment=True,
                         download_name=f"{os.path.splitext(uploaded.filename)[0]}.docx")
    finally:
        # cleanup - remove uploaded pdf and temp images and docx if they exist
        try:
            if os.path.exists(in_pdf_path):
                os.remove(in_pdf_path)
            for p in temp_images:
                if os.path.exists(p):
                    os.remove(p)
            # don't remove docx until after send_file finishes in most cases; leaving short-lived is OK
        except Exception:
            pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
