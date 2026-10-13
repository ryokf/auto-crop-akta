import json
from akta_cropper import process_akta_pdf

def test_pipeline():
    result = process_akta_pdf(
        pdf_input="sample_input.pdf",
        output_image_path="hasil_crop.png",
        annotated_output_path="hasil_annotated.png",
        dpi=150
    )
    
    assert result["success"] is True, f"Processing failed: {result.get('error')}"
    print("[SUCCESS] PDF processed successfully!")
    print(f"Halaman yang terpotong: {result['page_number']} dari {result['total_pages']}")
    print(f"Rotasi yang diterapkan: {result['rotation_applied']} derajat")
    print(f"Bounding Box: {result['bbox']}")
    print("\n--- DATA PEMBELI TERSTRUKTUR ---")
    print(json.dumps(result["buyer_info"], indent=2, ensure_ascii=False))
    print("\n--- RAW TEKS HASIL OCR ---")
    print(result["raw_text"])

if __name__ == "__main__":
    test_pipeline()
