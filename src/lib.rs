pub mod parser;

use std::path::Path;
use image::{imageops, DynamicImage, Rgba, RgbaImage};
use serde::{Deserialize, Serialize};
use windows::core::HSTRING;
use windows::Data::Pdf::{PdfDocument, PdfPageRenderOptions};
use windows::Graphics::Imaging::BitmapDecoder;
use windows::Media::Ocr::OcrEngine;
use windows::Storage::StorageFile;
use windows::Storage::Streams::{DataReader, InMemoryRandomAccessStream};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundingBox {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CropResult {
    pub success: bool,
    pub page_number: usize,
    pub total_pages: usize,
    pub rotation_applied: u32,
    pub bbox: BoundingBox,
    pub raw_text: String,
    pub buyer_info: parser::BuyerInfo,
    #[serde(skip)]
    pub cropped_image: RgbaImage,
    #[serde(skip)]
    pub annotated_page: RgbaImage,
}

#[derive(Debug, Clone)]
struct OcrWordInfo {
    _text: String,
    x: f32,
    y: f32,
    w: f32,
    h: f32,
}

#[derive(Debug, Clone)]
struct OcrLineInfo {
    text: String,
    words: Vec<OcrWordInfo>,
}

/// Render halaman PDF spesifik ke citra DynamicImage menggunakan Windows.Data.Pdf
async fn render_pdf_page(doc: &PdfDocument, page_index: u32, scale: f32) -> Result<DynamicImage, Box<dyn std::error::Error>> {
    let page = doc.GetPage(page_index)?;
    let size = page.Size()?;

    let mem_stream = InMemoryRandomAccessStream::new()?;
    let options = PdfPageRenderOptions::new()?;
    options.SetDestinationWidth((size.Width * scale) as u32)?;
    options.SetDestinationHeight((size.Height * scale) as u32)?;
    page.RenderWithOptionsToStreamAsync(&mem_stream, &options)?.await?;

    let stream_size = mem_stream.Size()? as usize;
    mem_stream.Seek(0)?;
    let reader = DataReader::CreateDataReader(&mem_stream)?;
    reader.LoadAsync(stream_size as u32)?.await?;
    let mut bytes = vec![0u8; stream_size];
    reader.ReadBytes(&mut bytes)?;

    let dyn_img = image::load_from_memory(&bytes)?;
    Ok(dyn_img)
}

/// Jalankan OCR pada citra RGBA
async fn run_ocr_on_image(img: &RgbaImage) -> Result<Vec<OcrLineInfo>, Box<dyn std::error::Error>> {
    let temp_file = std::env::temp_dir().join(format!("ocr_tmp_{}.png", std::process::id()));
    img.save(&temp_file)?;

    let abs_path = std::fs::canonicalize(&temp_file)?;
    let path_str = abs_path.to_str().unwrap().trim_start_matches(r"\\?\");
    let file = StorageFile::GetFileFromPathAsync(&HSTRING::from(path_str))?.await?;
    let stream = file.OpenAsync(windows::Storage::FileAccessMode::Read)?.await?;
    let decoder = BitmapDecoder::CreateAsync(&stream)?.await?;
    let bitmap = decoder.GetSoftwareBitmapAsync()?.await?;

    let engine = OcrEngine::TryCreateFromUserProfileLanguages()?;
    let result = engine.RecognizeAsync(&bitmap)?.await?;
    let _ = std::fs::remove_file(&temp_file);

    let mut lines_out = Vec::new();
    for line in result.Lines()? {
        let text = line.Text()?.to_string();
        let mut words_out = Vec::new();
        for word in line.Words()? {
            let rect = word.BoundingRect()?;
            words_out.push(OcrWordInfo {
                _text: word.Text()?.to_string(),
                x: rect.X,
                y: rect.Y,
                w: rect.Width,
                h: rect.Height,
            });
        }
        lines_out.push(OcrLineInfo { text, words: words_out });
    }

    Ok(lines_out)
}

/// Gambar kotak anotasi pada halaman
fn draw_bounding_box(img: &mut RgbaImage, bbox: &BoundingBox) {
    let color = Rgba([255, 140, 0, 255]); // Oranye
    let thickness = 4u32;
    let (w, h) = img.dimensions();

    let x1 = bbox.x;
    let y1 = bbox.y;
    let x2 = (bbox.x + bbox.width).min(w - 1);
    let y2 = (bbox.y + bbox.height).min(h - 1);

    // Garis horizontal atas & bawah
    for t in 0..thickness {
        if y1 + t < h {
            for x in x1..=x2 {
                img.put_pixel(x, y1 + t, color);
            }
        }
        if y2 >= t {
            for x in x1..=x2 {
                img.put_pixel(x, y2 - t, color);
            }
        }
    }

    // Garis vertikal kiri & kanan
    for t in 0..thickness {
        if x1 + t < w {
            for y in y1..=y2 {
                img.put_pixel(x1 + t, y, color);
            }
        }
        if x2 >= t {
            for y in y1..=y2 {
                img.put_pixel(x2 - t, y, color);
            }
        }
    }
}

/// Fungsi utama: Proses dokumen PDF akta dan potong lokasi data pembeli
pub async fn process_akta_pdf(pdf_path: &Path, scale: f32) -> Result<CropResult, Box<dyn std::error::Error>> {
    let abs_pdf = std::fs::canonicalize(pdf_path)?;
    let pdf_path_str = abs_pdf.to_str().unwrap().trim_start_matches(r"\\?\");

    let file = StorageFile::GetFileFromPathAsync(&HSTRING::from(pdf_path_str))?.await?;
    let doc = PdfDocument::LoadFromFileAsync(&file)?.await?;
    let total_pages = doc.PageCount()? as usize;

    for page_idx in 0..total_pages {
        let dyn_img = render_pdf_page(&doc, page_idx as u32, scale).await?;
        let (raw_w, raw_h) = (dyn_img.width(), dyn_img.height());

        // Koreksi orientasi jika dokumen landscape
        let (upright_img, rotation_applied) = if raw_w > raw_h {
            (imageops::rotate270(&dyn_img), 270)
        } else {
            (dyn_img.to_rgba8(), 0)
        };

        // Jalankan OCR
        let lines = run_ocr_on_image(&upright_img).await?;

        // Cari penutup frasa pembeli
        let mut end_line_idx = None;
        for (i, line) in lines.iter().enumerate() {
            let lower = line.text.to_lowercase();
            if lower.contains("pihak kedua/pembeli")
                || lower.contains("pihak kedua / pembeli")
                || lower.contains("pihak kedua/ pembeli")
                || lower.contains("pembeli\"")
                || (lower.contains("pihak kedua") && lower.contains("disebut"))
            {
                end_line_idx = Some(i);
                break;
            }
        }

        if let Some(end_idx) = end_line_idx {
            // Cari baris awal data pembeli
            let mut start_line_idx = 0;
            for i in (0..end_idx).rev() {
                let lower = lines[i].text.to_lowercase();
                if lower.contains("pihak pertama/penjual")
                    || lower.contains("pihak pertama/ penjual")
                    || lower.contains("pihak pertama")
                {
                    start_line_idx = i + 1;
                    break;
                }
                let trimmed = lines[i].text.trim();
                if trimmed.starts_with("II.") || trimmed.starts_with("11.") || trimmed.starts_with("2.") {
                    start_line_idx = i;
                    break;
                }
            }

            if start_line_idx > end_idx {
                start_line_idx = end_idx.saturating_sub(6);
            }

            // Hitung Bounding Box dari kata-kata yang terdeteksi
            let mut min_x = f32::MAX;
            let mut min_y = f32::MAX;
            let mut max_x = f32::MIN;
            let mut max_y = f32::MIN;

            let mut raw_lines_vec = Vec::new();
            for i in start_line_idx..=end_idx {
                let line = &lines[i];
                raw_lines_vec.push(line.text.clone());
                for word in &line.words {
                    if word.x < min_x { min_x = word.x; }
                    if word.y < min_y { min_y = word.y; }
                    if word.x + word.w > max_x { max_x = word.x + word.w; }
                    if word.y + word.h > max_y { max_y = word.y + word.h; }
                }
            }

            // Padding simetris dan rapi
            let pad_left = 30.0f32 * (scale / 2.0);
            let pad_right = 35.0f32 * (scale / 2.0);
            let pad_top = 18.0f32 * (scale / 2.0);
            let pad_bottom = 20.0f32 * (scale / 2.0);

            let (up_w, up_h) = upright_img.dimensions();
            let crop_x = (min_x - pad_left).max(0.0) as u32;
            let crop_y = (min_y - pad_top).max(0.0) as u32;
            let crop_w = ((max_x + pad_right) - (crop_x as f32)).min((up_w - crop_x) as f32) as u32;
            let crop_h = ((max_y + pad_bottom) - (crop_y as f32)).min((up_h - crop_y) as f32) as u32;

            let bbox = BoundingBox {
                x: crop_x,
                y: crop_y,
                width: crop_w,
                height: crop_h,
            };

            let cropped_image = imageops::crop_imm(&upright_img, crop_x, crop_y, crop_w, crop_h).to_image();
            
            let mut annotated_page = upright_img.clone();
            draw_bounding_box(&mut annotated_page, &bbox);

            let raw_text = raw_lines_vec.join("\n");
            let buyer_info = parser::parse_buyer_info(&raw_text);

            return Ok(CropResult {
                success: true,
                page_number: page_idx + 1,
                total_pages,
                rotation_applied,
                bbox,
                raw_text,
                buyer_info,
                cropped_image,
                annotated_page,
            });
        }
    }

    Err("Bagian data pembeli tidak ditemukan dalam dokumen akta.".into())
}
