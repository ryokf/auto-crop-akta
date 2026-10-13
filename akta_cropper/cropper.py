import os
import cv2
import numpy as np
import pymupdf
from typing import Optional, Dict, Any, Union
from .detector import (
    get_ocr_engine,
    render_pdf_page,
    detect_and_orient_upright,
    find_buyer_bounding_box
)
from .parser import parse_buyer_info

def process_akta_pdf(
    pdf_input: Union[str, bytes],
    output_image_path: Optional[str] = None,
    annotated_output_path: Optional[str] = None,
    dpi: int = 150
) -> Dict[str, Any]:
    """
    Memproses file PDF akta dan memotong otomatis lokasi data pembeli.
    
    Args:
        pdf_input: Path file PDF atau bytes data PDF.
        output_image_path: Path tujuan untuk menyimpan gambar hasil crop (opsional).
        annotated_output_path: Path tujuan untuk menyimpan halaman penuh dengan kotak penanda (opsional).
        dpi: Resolusi render PDF (default: 150 DPI, ideal untuk akurasi dan kecepatan).
        
    Returns:
        Dictionary berisi status, halaman, koordinat bbox, gambar crop, teks, dan metadata terstruktur.
    """
    if isinstance(pdf_input, bytes):
        doc = pymupdf.open(stream=pdf_input, filetype="pdf")
    else:
        if not os.path.exists(pdf_input):
            return {
                "success": False,
                "error": f"File PDF tidak ditemukan: {pdf_input}"
            }
        doc = pymupdf.open(pdf_input)

    total_pages = len(doc)
    engine = get_ocr_engine()

    best_match = None

    # Iterasi setiap halaman PDF
    for pno in range(total_pages):
        page = doc[pno]
        raw_img = render_pdf_page(page, dpi=dpi)
        
        # 1. Pastikan orientasi halaman tegak (upright)
        upright_img, rotation_angle = detect_and_orient_upright(raw_img, engine)
        
        # 2. Jalankan OCR pada halaman tegak
        ocr_results, _ = engine(upright_img)
        if not ocr_results:
            continue
            
        # 3. Cari bagian data pembeli
        found = find_buyer_bounding_box(ocr_results, upright_img.shape, dpi=dpi)
        if found:
            x1, y1, x2, y2, raw_lines = found
            
            # Potong citra data pembeli
            crop_img = upright_img[y1:y2, x1:x2].copy()
            raw_text = "\n".join(raw_lines)
            buyer_info = parse_buyer_info(raw_text)
            
            # Buat citra halaman penuh beranotasi (highlight bounding box)
            annotated_page = upright_img.copy()
            cv2.rectangle(annotated_page, (x1, y1), (x2, y2), (0, 165, 255), 3) # Warna oranye tebal
            cv2.putText(
                annotated_page,
                "LOKASI DATA PEMBELI",
                (x1, max(30, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 140, 255),
                2,
                cv2.LINE_AA
            )

            # Simpan file jika path ditentukan
            if output_image_path:
                os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
                cv2.imwrite(output_image_path, crop_img)

            if annotated_output_path:
                os.makedirs(os.path.dirname(os.path.abspath(annotated_output_path)), exist_ok=True)
                cv2.imwrite(annotated_output_path, annotated_page)

            best_match = {
                "success": True,
                "page_number": pno + 1,
                "total_pages": total_pages,
                "rotation_applied": rotation_angle,
                "bbox": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": x2 - x1,
                    "height": y2 - y1
                },
                "cropped_image": crop_img,
                "annotated_page": annotated_page,
                "output_image_path": output_image_path,
                "annotated_output_path": annotated_output_path,
                "raw_text": raw_text,
                "buyer_info": buyer_info
            }
            break

    doc.close()

    if best_match:
        return best_match

    return {
        "success": False,
        "error": "Bagian data pembeli tidak ditemukan dalam dokumen akta.",
        "total_pages": total_pages
    }
