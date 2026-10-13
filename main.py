#!/usr/bin/env python3
"""
Auto Crop Akta - CLI Tool
Program otomatis memotong bagian data pembeli pada dokumen akta (PDF).

Contoh Penggunaan:
    python main.py input.pdf -o hasil_crop.png
    python main.py ./folder_akta/ --out-dir ./hasil_crop/
    python main.py input.pdf --json --annotated
"""

import os
import sys
import argparse
import json
from pathlib import Path
from akta_cropper import process_akta_pdf

def process_single_file(pdf_path: str, output_path: str, annotated_path: str, save_json: bool, dpi: int):
    print(f"\n[MEMPROSES] {pdf_path} ...")
    res = process_akta_pdf(
        pdf_input=pdf_path,
        output_image_path=output_path,
        annotated_output_path=annotated_path,
        dpi=dpi
    )
    
    if not res.get("success"):
        print(f"[GAGAL] {res.get('error')}")
        return False

    print(f"[BERHASIL]")
    print(f"  * Ditemukan di Halaman: {res['page_number']} dari {res['total_pages']}")
    print(f"  * Rotasi Otomatis    : {res['rotation_applied']} derajat")
    print(f"  * Koordinat Bbox     : {res['bbox']}")
    print(f"  * Disimpan ke        : {output_path}")
    if annotated_path:
        print(f"  * Halaman Anotasi    : {annotated_path}")

    buyer = res.get("buyer_info", {})
    print("\n--- Data Pembeli Terdeteksi ---")
    print(f"  Nama      : {buyer.get('sapaan') or ''} {buyer.get('nama') or '-'}")
    print(f"  NIK       : {buyer.get('nik') or '-'}")
    print(f"  TTL       : {buyer.get('ttl') or '-'}")
    print(f"  Pekerjaan : {buyer.get('pekerjaan') or '-'}")
    print(f"  Alamat    : {buyer.get('alamat') or '-'}")

    if save_json:
        json_path = str(Path(output_path).with_suffix(".json"))
        data_to_save = {
            "file": os.path.basename(pdf_path),
            "halaman": res["page_number"],
            "bbox": res["bbox"],
            "data_pembeli": buyer,
            "raw_text": res["raw_text"]
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        print(f"  * Metadata JSON      : {json_path}")

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Program Otomatis Memotong Bagian Data Pembeli pada Dokumen Akta (PDF)."
    )
    parser.add_argument("input", help="Path ke file PDF akta atau folder berisi file PDF.")
    parser.add_argument("-o", "--output", help="Path file output gambar hasil crop (default: [nama_pdf]_crop_pembeli.png).")
    parser.add_argument("--out-dir", help="Folder tujuan untuk pemrosesan banyak file PDF sekaligus.")
    parser.add_argument("--annotated", action="store_true", help="Simpan juga gambar satu halaman penuh dengan highlight kotak penanda.")
    parser.add_argument("--json", action="store_true", help="Simpan metadata data pembeli ke file .json.")
    parser.add_argument("--dpi", type=int, default=150, help="Resolusi render PDF (default: 150 DPI).")
    parser.add_argument("--gui", action="store_true", help="Jalankan Web GUI interaktif di browser.")

    args = parser.parse_args()

    if args.gui:
        import web_app
        web_app.run_server()
        return

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Jalur input '{args.input}' tidak ditemukan.")
        sys.exit(1)

    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            print(f"Error: File '{args.input}' bukan file PDF.")
            sys.exit(1)

        out_img = args.output or str(input_path.with_name(f"{input_path.stem}_crop_pembeli.png"))
        ann_img = str(input_path.with_name(f"{input_path.stem}_annotated.png")) if args.annotated else None

        success = process_single_file(
            pdf_path=str(input_path),
            output_path=out_img,
            annotated_path=ann_img,
            save_json=args.json,
            dpi=args.dpi
        )
        sys.exit(0 if success else 1)

    elif input_path.is_dir():
        pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
        if not pdf_files:
            print(f"Tidak ada file PDF ditemukan di folder '{args.input}'.")
            sys.exit(0)

        out_dir = Path(args.out_dir) if args.out_dir else input_path / "hasil_crop"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"Ditemukan {len(pdf_files)} file PDF. Menyimpan hasil ke: {out_dir}")
        success_count = 0

        for pdf in pdf_files:
            out_img = str(out_dir / f"{pdf.stem}_crop_pembeli.png")
            ann_img = str(out_dir / f"{pdf.stem}_annotated.png") if args.annotated else None

            if process_single_file(str(pdf), out_img, ann_img, args.json, args.dpi):
                success_count += 1

        print(f"\n[SELESAI] {success_count} dari {len(pdf_files)} file berhasil diproses.")

if __name__ == "__main__":
    main()
