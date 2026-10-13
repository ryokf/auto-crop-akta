#!/usr/bin/env python3
"""
Auto Crop Akta - Web GUI
Aplikasi web modern berbasis browser lokal untuk upload & auto-crop data pembeli pada akta PDF.
"""

import os
import sys
import json
import base64
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
from akta_cropper import process_akta_pdf

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Auto Crop Akta - Pemotong Otomatis Data Pembeli</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .dropzone {
      border: 2px dashed #cbd5e1;
      transition: all 0.2s ease-in-out;
    }
    .dropzone.dragover {
      border-color: #3b82f6;
      background-color: #eff6ff;
    }
  </style>
</head>
<body class="bg-slate-50 min-h-screen text-slate-800">
  <!-- Header -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white text-xl shadow-md shadow-blue-200">
          <i class="fa-solid fa-crop-simple"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold text-slate-900 leading-tight">Auto Crop Akta</h1>
          <p class="text-xs text-slate-500 font-medium">Pemotong Otomatis Bagian Data Pembeli (Akta Jual Beli / PPAT)</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
          <span class="w-1.5 h-1.5 mr-1.5 bg-emerald-500 rounded-full animate-pulse"></span> RapidOCR Aktif
        </span>
      </div>
    </div>
  </header>

  <main class="max-w-6xl mx-auto px-4 py-8">
    <!-- Upload Section -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-8">
      <div id="dropzone" class="dropzone rounded-xl p-8 text-center cursor-pointer hover:border-blue-400">
        <input type="file" id="fileInput" accept=".pdf" class="hidden">
        <div class="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
          <i class="fa-solid fa-file-pdf"></i>
        </div>
        <h3 class="text-base font-bold text-slate-800 mb-1">Tarik & Letakkan File PDF Akta ke Sini</h3>
        <p class="text-sm text-slate-500 mb-4">atau klik untuk memilih file PDF dari komputer Anda</p>
        <button type="button" onclick="document.getElementById('fileInput').click()" class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all shadow-sm shadow-blue-200">
          <i class="fa-solid fa-arrow-up-from-bracket"></i> Pilih Dokumen PDF
        </button>
      </div>

      <!-- Selected File Info & Controls -->
      <div id="fileInfoBox" class="hidden mt-4 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <i class="fa-solid fa-file-lines text-2xl text-blue-600"></i>
          <div>
            <p id="fileName" class="text-sm font-bold text-slate-800">-</p>
            <p id="fileSize" class="text-xs text-slate-500">-</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <label class="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
            DPI:
            <select id="dpiSelect" class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-medium focus:ring-2 focus:ring-blue-500">
              <option value="150" selected>150 DPI (Cepat & Akurat)</option>
              <option value="300">300 DPI (Kualitas Tinggi)</option>
            </select>
          </label>
          <button id="processBtn" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold shadow-sm shadow-emerald-200 flex items-center gap-2">
            <i class="fa-solid fa-scissors"></i> Potong Data Pembeli
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div id="loadingBox" class="hidden mt-6 text-center py-8">
        <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-blue-500 border-t-transparent mb-3"></div>
        <p class="text-sm font-bold text-slate-800">Sedang Menganalisis Dokumen Akta...</p>
        <p class="text-xs text-slate-500 mt-1">Mendeteksi orientasi, memindai teks, dan mencari lokasi data pembeli.</p>
      </div>
    </div>

    <!-- Error Box -->
    <div id="errorBox" class="hidden mb-8 bg-red-50 border border-red-200 rounded-2xl p-5 text-red-800 text-sm flex items-start gap-3">
      <i class="fa-solid fa-circle-exclamation text-xl text-red-500 mt-0.5"></i>
      <div>
        <h4 class="font-bold">Pemrosesan Gagal</h4>
        <p id="errorMsg" class="mt-0.5 text-red-700 text-xs"></p>
      </div>
    </div>

    <!-- Results Section -->
    <div id="resultsSection" class="hidden space-y-8">
      <!-- Hasil Potongan Utama -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div class="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
          <div>
            <span class="text-xs font-bold uppercase tracking-wider text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md">Hasil Potongan</span>
            <h2 class="text-lg font-bold text-slate-900 mt-1.5">Citra Lokasi Data Pembeli</h2>
            <p id="pageInfo" class="text-xs text-slate-500"></p>
          </div>
          <a id="downloadCropBtn" download="hasil_crop_pembeli.png" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-200 flex items-center gap-2 cursor-pointer">
            <i class="fa-solid fa-download"></i> Unduh Gambar
          </a>
        </div>

        <div class="bg-slate-100 rounded-xl p-4 flex items-center justify-center border border-slate-200 overflow-hidden">
          <img id="cropImgPreview" src="" alt="Potongan Data Pembeli" class="max-w-full rounded-lg shadow-sm border border-slate-300">
        </div>
      </div>

      <!-- Ekstraksi Data Terstruktur -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Informasi Pembeli Card -->
        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <div class="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-address-card text-blue-600"></i> Data Terstruktur Pembeli
            </h3>
            <button onclick="copyAllData()" class="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1">
              <i class="fa-regular fa-copy"></i> Salin Semua
            </button>
          </div>

          <div class="space-y-3 text-sm">
            <div class="bg-slate-50 p-3 rounded-xl border border-slate-100 flex items-start justify-between">
              <div>
                <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Nama Lengkap</span>
                <p id="dataNama" class="font-bold text-slate-800 text-base mt-0.5">-</p>
              </div>
              <button onclick="copyField('dataNama')" class="text-slate-400 hover:text-blue-600 text-xs p-1" title="Salin Nama"><i class="fa-regular fa-copy"></i></button>
            </div>

            <div class="bg-slate-50 p-3 rounded-xl border border-slate-100 flex items-start justify-between">
              <div>
                <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">NIK (Nomor Induk Kependudukan)</span>
                <p id="dataNik" class="font-mono font-bold text-blue-700 text-base mt-0.5">-</p>
              </div>
              <button onclick="copyField('dataNik')" class="text-slate-400 hover:text-blue-600 text-xs p-1" title="Salin NIK"><i class="fa-regular fa-copy"></i></button>
            </div>

            <div class="bg-slate-50 p-3 rounded-xl border border-slate-100">
              <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Tempat & Tanggal Lahir</span>
              <p id="dataTtl" class="font-medium text-slate-800 mt-0.5">-</p>
            </div>

            <div class="bg-slate-50 p-3 rounded-xl border border-slate-100">
              <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Pekerjaan</span>
              <p id="dataPekerjaan" class="font-medium text-slate-800 mt-0.5">-</p>
            </div>

            <div class="bg-slate-50 p-3 rounded-xl border border-slate-100">
              <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Alamat Lengkap</span>
              <p id="dataAlamat" class="font-medium text-slate-800 mt-0.5 leading-relaxed">-</p>
            </div>
          </div>
        </div>

        <!-- Pratinjau Halaman Anotasi -->
        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col">
          <div class="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-magnifying-glass-location text-emerald-600"></i> Posisi Pada Halaman Asli
            </h3>
            <span class="text-xs text-slate-500 font-medium">Kotak oranye menandai hasil crop</span>
          </div>
          <div class="bg-slate-100 rounded-xl p-3 flex-1 flex items-center justify-center border border-slate-200 overflow-auto max-h-[500px]">
            <img id="annotatedImgPreview" src="" alt="Pratinjau Halaman Akta" class="max-h-[460px] object-contain rounded border border-slate-300 shadow-sm">
          </div>
        </div>
      </div>
    </div>
  </main>

  <script>
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const fileInfoBox = document.getElementById('fileInfoBox');
    const fileNameEl = document.getElementById('fileName');
    const fileSizeEl = document.getElementById('fileSize');
    const processBtn = document.getElementById('processBtn');
    const loadingBox = document.getElementById('loadingBox');
    const errorBox = document.getElementById('errorBox');
    const errorMsg = document.getElementById('errorMsg');
    const resultsSection = document.getElementById('resultsSection');
    
    let currentFile = null;

    // Drag and drop handlers
    ['dragenter', 'dragover'].forEach(event => {
      dropzone.addEventListener(event, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(event => {
      dropzone.addEventListener(event, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0 && files[0].name.toLowerCase().endsWith('.pdf')) {
        handleFileSelect(files[0]);
      } else {
        alert('Harap unggah file dokumen berformat PDF.');
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });

    function handleFileSelect(file) {
      currentFile = file;
      fileNameEl.textContent = file.name;
      fileSizeEl.textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
      fileInfoBox.classList.remove('hidden');
      errorBox.classList.add('hidden');
      resultsSection.classList.add('hidden');
    }

    processBtn.addEventListener('click', async () => {
      if (!currentFile) return;

      loadingBox.classList.remove('hidden');
      processBtn.disabled = true;
      errorBox.classList.add('hidden');
      resultsSection.classList.add('hidden');

      const dpi = document.getElementById('dpiSelect').value;
      
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const base64Data = reader.result.split(',')[1];
          const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              pdf_base64: base64Data,
              dpi: parseInt(dpi)
            })
          });

          const data = await response.json();
          loadingBox.classList.add('hidden');
          processBtn.disabled = false;

          if (!data.success) {
            errorBox.classList.remove('hidden');
            errorMsg.textContent = data.error || 'Terjadi kesalahan saat memproses PDF.';
            return;
          }

          renderResults(data);
        } catch (err) {
          loadingBox.classList.add('hidden');
          processBtn.disabled = false;
          errorBox.classList.remove('hidden');
          errorMsg.textContent = 'Gagal memproses PDF: ' + err.message;
        }
      };

      reader.onerror = () => {
        loadingBox.classList.add('hidden');
        processBtn.disabled = false;
        errorBox.classList.remove('hidden');
        errorMsg.textContent = 'Gagal membaca file lokal.';
      };

      reader.readAsDataURL(currentFile);
    });

    function renderResults(data) {
      document.getElementById('pageInfo').textContent = `Ditemukan pada Halaman ${data.page_number} dari ${data.total_pages} (Rotasi otomatis: ${data.rotation_applied}°)`;
      
      const cropSrc = 'data:image/png;base64,' + data.cropped_image_base64;
      document.getElementById('cropImgPreview').src = cropSrc;
      document.getElementById('downloadCropBtn').href = cropSrc;
      document.getElementById('downloadCropBtn').download = `${currentFile.name.replace(/\\.pdf$/i, '')}_crop_pembeli.png`;

      const annSrc = 'data:image/png;base64,' + data.annotated_image_base64;
      document.getElementById('annotatedImgPreview').src = annSrc;

      const buyer = data.buyer_info || {};
      document.getElementById('dataNama').textContent = (buyer.sapaan ? buyer.sapaan + ' ' : '') + (buyer.nama || '-');
      document.getElementById('dataNik').textContent = buyer.nik || '-';
      document.getElementById('dataTtl').textContent = buyer.ttl || '-';
      document.getElementById('dataPekerjaan').textContent = buyer.pekerjaan || '-';
      document.getElementById('dataAlamat').textContent = buyer.alamat || '-';

      resultsSection.classList.remove('hidden');
      resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function copyField(elementId) {
      const text = document.getElementById(elementId).textContent;
      navigator.clipboard.writeText(text);
      alert('Teks berhasil disalin: ' + text);
    }

    function copyAllData() {
      const nama = document.getElementById('dataNama').textContent;
      const nik = document.getElementById('dataNik').textContent;
      const ttl = document.getElementById('dataTtl').textContent;
      const pekerjaan = document.getElementById('dataPekerjaan').textContent;
      const alamat = document.getElementById('dataAlamat').textContent;

      const all = `Nama: ${nama}\\nNIK: ${nik}\\nTTL: ${ttl}\\nPekerjaan: ${pekerjaan}\\nAlamat: ${alamat}`;
      navigator.clipboard.writeText(all);
      alert('Semua data pembeli berhasil disalin ke clipboard!');
    }
  </script>
</body>
</html>
"""

class AktaHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/process":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length).decode("utf-8")
                req_json = json.loads(raw_body)

                pdf_b64 = req_json.get("pdf_base64")
                if not pdf_b64:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "pdf_base64 wajib diisi."}).encode())
                    return

                pdf_bytes = base64.b64decode(pdf_b64)
                dpi = int(req_json.get("dpi", 150))

                import cv2
                res = process_akta_pdf(pdf_input=pdf_bytes, dpi=dpi)

                if not res.get("success"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(res).encode())
                    return

                # Encode gambar ke base64
                _, crop_buffer = cv2.imencode(".png", res["cropped_image"])
                crop_base64 = base64.b64encode(crop_buffer).decode("utf-8")

                _, ann_buffer = cv2.imencode(".png", res["annotated_page"])
                ann_base64 = base64.b64encode(ann_buffer).decode("utf-8")

                response_data = {
                    "success": True,
                    "page_number": res["page_number"],
                    "total_pages": res["total_pages"],
                    "rotation_applied": res["rotation_applied"],
                    "bbox": res["bbox"],
                    "buyer_info": res["buyer_info"],
                    "raw_text": res["raw_text"],
                    "cropped_image_base64": crop_base64,
                    "annotated_image_base64": ann_base64
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = 5050, open_browser: bool = True):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, AktaHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"  Auto Crop Akta Web GUI Berjalan!")
    print(f"  Silakan buka di browser: {url}")
    print(f"  Tekan Ctrl+C di terminal ini untuk berhenti.")
    print(f"=======================================================\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
        httpd.server_close()

if __name__ == "__main__":
    port = 5050
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port=port)
