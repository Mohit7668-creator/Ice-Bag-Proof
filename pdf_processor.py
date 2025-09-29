import streamlit as st
from pathlib import Path
from PIL import Image
import numpy as np
import io
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
from datetime import datetime
import re

# Initialize session state
if 'selected_template' not in st.session_state:
    st.session_state.selected_template = "8lb PLWK"
if 'text_input' not in st.session_state:
    st.session_state.text_input = ""

# App title and description
st.title("Ice Bag PDF Generator")
st.write("Select a template, enter text, and generate a PDF proof with a live preview.")

# Layout: Two columns
col1, col2 = st.columns([1, 1])

# Template options
template_options = [
    "8lb CT", "8lb DS", "8lb PLWK", "8lb WK",
    "10lb CT", "10lb DS", "10lb PLWK", "10lb WK",
    "20lb CT", "20lb DS", "20lb PLWK", "20lb WK"
]

# Function to load template file (mock paths for now, replace with actual paths)
def load_template(template_name):
    # Placeholder: Map template names to file paths
    # In production, store PDFs in a folder and map them here
    template_paths = {
        "8lb PLWK": "templates/8lb_PLWK.pdf"  # Only this template exists currently
        # Add other templates when available, e.g., "8lb CT": "templates/8lb_CT.pdf"
    }
    path = template_paths.get(template_name, "templates/8lb_PLWK.pdf")  # Fallback to PLWK
    try:
        with open(path, "rb") as f:
            return io.BytesIO(f.read())
    except FileNotFoundError:
        st.error(f"Template {template_name} not found. Using default template.")
        with open("templates/8lb_PLWK.pdf", "rb") as f:
            return io.BytesIO(f.read())

# Function to generate file name
def generate_filename(template, text):
    template_code = template.split()[-1]  # e.g., "PLWK" from "8lb PLWK"
    company = text.split("\n")[0].strip() if text.strip() else "Default"
    company = re.sub(r'[^\w\s#]', '', company).replace(" ", "_")  # e.g., "Bob’s Market #12" -> "Bobs_Market_12"
    date_str = datetime.now().strftime("%m%d%y")
    return f"{template.split()[0]}_FPI_{template_code}_{company}_{date_str}_Outline_BG.pdf"

# Function to register Arial font
def register_fonts():
    arial_paths = [
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    arial_bold_paths = [
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    
    have_arial = False
    have_arial_bold = False
    
    for p in arial_paths:
        p = Path(p)
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont("Arial", str(p)))
                have_arial = True
                break
            except Exception:
                continue
    
    for p in arial_bold_paths:
        p = Path(p)
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont("Arial-Bold", str(p)))
                have_arial_bold = True
                break
            except Exception:
                continue
    
    return have_arial, have_arial_bold

# Function to generate PDF with text outlines for Illustrator compatibility
def generate_pdf(template_buffer, lines, template_name):
    have_arial, have_arial_bold = register_fonts()
    font_regular = "Arial" if have_arial else "Helvetica"
    font_bold = "Arial-Bold" if have_arial_bold else "Helvetica-Bold"
    
    # Open template PDF
    doc = fitz.open(stream=template_buffer.read(), filetype="pdf")
    page = doc.load_page(0)
    
    # Detect red box
    zoom = 2
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    arr = np.array(img)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    red_mask = (r > 150) & (r > g + 60) & (r > b + 60)
    
    if red_mask.sum() < 50:
        red_mask = (r > 120) & (r > g + 40) & (r > b + 40)
    
    ys, xs = np.where(red_mask)
    page_rect = page.rect
    page_w_pts, page_h_pts = page_rect.width, page_rect.height
    
    if len(xs) == 0:
        # Fallback to central box
        box_w_pts = 4 * 72
        box_h_pts = 2 * 72
        x0 = (page_w_pts - box_w_pts) / 2
        y0 = (page_h_pts - box_h_pts) / 2
        x1 = x0 + box_w_pts
        y1 = y0 + box_h_pts
        detected = False
    else:
        detected = True
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
        img_w, img_h = img.size
        x0 = min_x * (page_w_pts / img_w)
        x1 = max_x * (page_w_pts / img_w)
        y0 = page_h_pts - (max_y * (page_h_pts / img_h))
        y1 = page_h_pts - (min_y * (page_h_pts / img_h))
    
    # Create overlay canvas
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_w_pts, page_h_pts))
    
    # Text placement (centered horizontally and vertically)
    padding = 6
    box_w = x1 - x0
    box_h = y1 - y0
    
    # Calculate total text height for vertical centering
    font_size = 24
    lines = [line.strip() for line in lines.split("\n") if line.strip()]
    while font_size > 6:
        total_height = len(lines) * font_size * 1.2
        max_line_width = max(pdfmetrics.stringWidth(ln, font_regular, font_size) for ln in lines)
        if total_height <= (box_h - 2 * padding) and max_line_width <= (box_w - 2 * padding):
            break
        font_size -= 1
    
    line_height = font_size * 1.2
    total_text_height = len(lines) * line_height
    y_cursor = y0 + (box_h - total_text_height) / 2 + (line_height - font_size)  # Vertical centering
    
    # Draw text with outlines
    for i, ln in enumerate(lines):
        line_width = pdfmetrics.stringWidth(ln, font_bold if i == 0 else font_regular, font_size)
        text_x = x0 + (box_w - line_width) / 2  # Horizontal centering
        c.setFont(font_bold if i == 0 else font_regular, font_size)
        # Convert text to outlines for Illustrator compatibility
        c.showText(ln, mode=4)  # mode=4 creates outlines
        c.drawString(text_x, y_cursor, ln)
        y_cursor -= line_height
    
    c.save()
    overlay_buffer.seek(0)
    
    # Merge PDFs
    new_pdf = PdfReader(overlay_buffer)
    template_buffer.seek(0)
    existing_pdf = PdfReader(template_buffer)
    writer = PdfWriter()
    
    page0 = existing_pdf.pages[0]
    try:
        page0.merge_page(new_pdf.pages[0])
    except Exception:
        pass
    
    writer.add_page(page0)
    for p in existing_pdf.pages[1:]:
        writer.add_page(p)
    
    final_buffer = io.BytesIO()
    writer.write(final_buffer)
    final_buffer.seek(0)
    
    return final_buffer, detected

# Function to generate live preview
def generate_preview(template_buffer, lines):
    doc = fitz.open(stream=template_buffer.read(), filetype="pdf")
    page = doc.load_page(0)
    pix = page.get_pixmap()
    preview_buffer = io.BytesIO(pix.tobytes("png"))
    preview_buffer.seek(0)
    return preview_buffer

with col1:
    # Template selection
    st.selectbox(
        "Select Size",
        options=template_options,
        index=template_options.index(st.session_state.selected_template),
        key="selected_template"
    )
    
    # Text input
    text_input = st.text_area(
        "Enter text lines (one per line, first line will be bold):",
        value=st.session_state.text_input,
        height=200,
        key="text_input"
    )
    
    # Download button
    if st.button("Download PDF") and text_input:
        template_buffer = load_template(st.session_state.selected_template)
        final_buffer, detected = generate_pdf(template_buffer, text_input, st.session_state.selected_template)
        filename = generate_filename(st.session_state.selected_template, text_input)
        st.download_button(
            label="Download PDF",
            data=final_buffer.getvalue(),
            file_name=filename,
            mime="application/pdf"
        )
        if not detected:
            st.warning("Red box not detected; used fallback position.")

with col2:
    # Live preview
    st.subheader("Live Preview")
    if st.session_state.text_input:
        template_buffer = load_template(st.session_state.selected_template)
        preview_buffer = generate_preview(template_buffer, st.session_state.text_input)
        st.image(preview_buffer, caption="Bag Proof Preview", use_column_width=True)
    else:
        st.info("Enter text to see the live preview.")

# Font warning
have_arial, have_arial_bold = register_fonts()
if not have_arial or not have_arial_bold:
    st.info("Arial font not found; using Helvetica as fallback.")

# Design question response
st.subheader("Design Question")
st.write(
    "A Figma design would be very helpful to align the UI with your branding (colors, typography, logo usage). "
    "It would streamline the process of styling the Streamlit app to match your vision. Please go ahead and create the Figma file, and share the link or details when ready."
)
