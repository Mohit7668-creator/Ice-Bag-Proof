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
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import inch

# App title and description
st.title("PDF Text Overlay Generator")
st.write("Upload a PDF template with a red box, provide text lines, and generate a proof with overlaid text.")

# File uploader for the template PDF
uploaded_file = st.file_uploader("Choose a PDF template file", type="pdf")

# Text input for lines (multi-line)
lines_input = st.text_area("Enter text lines (one per line, first line will be bold):", 
                           value="Test Line 1\nTest Line 2\nTest Line 3", height=100)
lines = [line.strip() for line in lines_input.split("\n") if line.strip()]

# Process button
if st.button("Generate PDF Proof") and uploaded_file is not None and lines:
    with st.spinner("Processing PDF..."):
        try:
            # Read uploaded file as BytesIO
            file_content = uploaded_file.read()
            template_buffer = io.BytesIO(file_content)
            
            # Ensure the buffer is at the start
            template_buffer.seek(0)
            
            # Try to open PDF and rasterize the first page to detect red box
            doc = fitz.open(stream=template_buffer.read(), filetype="pdf")
            page = doc.load_page(0)
            # Render at zoom for better resolution
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Save preview image (in memory for display)
            preview_buffer = io.BytesIO()
            img.save(preview_buffer, format="PNG")
            preview_buffer.seek(0)
            
            # Display preview
            st.image(preview_buffer, caption="Template Preview", use_column_width=True)

            # Convert to numpy for color detection
            arr = np.array(img)

            # Detect red pixels
            r = arr[..., 0].astype(int)
            g = arr[..., 1].astype(int)
            b = arr[..., 2].astype(int)
            red_mask = (r > 150) & (r > g + 60) & (r > b + 60)

            if red_mask.sum() < 50:
                red_mask = (r > 120) & (r > g + 40) & (r > b + 40)

            ys, xs = np.where(red_mask)
            if len(xs) == 0:
                # Fallback to central box
                page_rect = page.rect
                w_pts = page_rect.width
                h_pts = page_rect.height
                box_w_pts = 4 * 72
                box_h_pts = 2 * 72
                x0 = (w_pts - box_w_pts) / 2
                y0 = (h_pts - box_h_pts) / 2
                x1 = x0 + box_w_pts
                y1 = y0 + box_h_pts
                detected = False
            else:
                detected = True
                min_x, max_x = xs.min(), xs.max()
                min_y, max_y = ys.min(), ys.max()
                img_w, img_h = img.size
                page_rect = page.rect
                page_w_pts = page_rect.width
                page_h_pts = page_rect.height
                x0 = min_x * (page_w_pts / img_w)
                x1 = max_x * (page_w_pts / img_w)
                y0 = page_h_pts - (max_y * (page_h_pts / img_h))
                y1 = page_h_pts - (min_y * (page_h_pts / img_h))

            # Font registration (try common paths, fallback to Helvetica)
            def try_register(font_name, paths):
                for p in paths:
                    p = Path(p)
                    if p.exists():
                        try:
                            pdfmetrics.registerFont(TTFont(font_name, str(p)))
                            return True
                        except Exception:
                            continue
                return False

            # Paths for Arial (cross-platform)
            arial_paths = [
                "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/Arial.ttf",
                "C:/Windows/Fonts/arial.ttf",  # For local Windows testing
            ]
            arial_bold_paths = [
                "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]

            have_arial = try_register("Arial", arial_paths)
            have_arial_bold = try_register("Arial-Bold", arial_bold_paths)

            font_regular = "Arial" if have_arial else "Helvetica"
            font_bold = "Arial-Bold" if have_arial_bold else "Helvetica-Bold"

            # Create overlay canvas
            overlay_buffer = io.BytesIO()
            c = canvas.Canvas(overlay_buffer, pagesize=(page_rect.width, page_rect.height))

            # Optional: Draw red border for debugging
            c.setLineWidth(1)
            c.setStrokeColorRGB(1, 0, 0)
            c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)

            # Text placement (centered horizontally)
            padding = 6
            text_top = y1 - padding
            box_w = x1 - x0
            box_h = y1 - y0

            # Dynamic font sizing
            font_size = 24
            while font_size > 6:
                total_height = len(lines) * font_size * 1.2
                max_line_width = max(stringWidth(ln, font_regular, font_size) for ln in lines)
                if total_height <= (box_h - 2 * padding) and max_line_width <= (box_w - 2 * padding):
                    break
                font_size -= 1

            line_height = font_size * 1.2
            y_cursor = text_top - font_size

            # Center text horizontally, only first line bold
            for i, ln in enumerate(lines):
                line_width = stringWidth(ln, font_regular, font_size)
                text_x = x0 + (box_w - line_width) / 2  # Center the text within the box

                if i == 0:
                    c.setFont(font_bold, font_size)
                else:
                    c.setFont(font_regular, font_size)
                c.drawString(text_x, y_cursor, ln)
                y_cursor -= line_height

            c.save()
            overlay_buffer.seek(0)

            # Merge PDFs
            new_pdf = PdfReader(overlay_buffer)
            template_buffer.seek(0)  # Reset for re-reading
            existing_pdf = PdfReader(template_buffer)
            writer = PdfWriter()

            page0 = existing_pdf.pages[0]
            try:
                page0.merge_page(new_pdf.pages[0])
            except Exception:
                pass  # Fallback if merge fails

            writer.add_page(page0)
            for p in existing_pdf.pages[1:]:
                writer.add_page(p)

            # Output final PDF buffer
            final_buffer = io.BytesIO()
            writer.write(final_buffer)
            final_buffer.seek(0)

            # Generate PNG preview of first page
            merged_doc = fitz.open(stream=final_buffer.read(), filetype="pdf")
            merged_page = merged_doc.load_page(0)
            merged_pix = merged_page.get_pixmap()
            png_buffer = io.BytesIO(merged_pix.tobytes("png"))
            png_buffer.seek(0)

            # Display results
            st.success("PDF generated successfully!")
            st.write(f"Red box detected: {'Yes' if detected else 'No (used fallback)'}")
            st.write(f"Fonts used: Regular={font_regular}, Bold={font_bold}")

            # Download buttons
            st.download_button(
                label="Download Merged PDF",
                data=final_buffer.getvalue(),
                file_name="merged_proof.pdf",
                mime="application/pdf"
            )
            st.download_button(
                label="Download PNG Preview",
                data=png_buffer.getvalue(),
                file_name="proof_preview.png",
                mime="image/png"
            )

            # Notes
            if not have_arial:
                st.info("Arial not found; using Helvetica fallback.")

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.info("Ensure the uploaded file is a valid PDF with a detectable red box.")

elif uploaded_file is None:
    st.warning("Please upload a PDF template.")
elif not lines:
    st.warning("Please enter at least one text line.")
