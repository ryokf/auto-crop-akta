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
    pub buyer_info: parser::BuyerJsonOutput,
    #[serde(skip)]
    pub cropped_image: RgbaImage,
    #[serde(skip)]
    pub annotated_page: RgbaImage,
}

#[derive(Debug, Clone)]
pub struct OcrWordInfo {
    pub text: String,
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
}

#[derive(Debug, Clone)]
pub struct OcrLineInfo {
    pub text: String,
    pub words: Vec<OcrWordInfo>,
}

/// Render halaman PDF ke citra DynamicImage menggunakan Windows.Data.Pdf
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

/// Jalankan OCR pada citra RGBA menggunakan Windows.Media.Ocr
async fn run_ocr_on_image(img: &RgbaImage, engine: &OcrEngine, page_idx: usize) -> Result<Vec<OcrLineInfo>, Box<dyn std::error::Error>> {
    let temp_file = std::env::temp_dir().join(format!("ocr_tmp_{}_{}.png", std::process::id(), page_idx));
    img.save(&temp_file)?;

    let abs_path = std::fs::canonicalize(&temp_file)?;
    let path_str = abs_path.to_str().unwrap().trim_start_matches(r"\\?\");
    let file = StorageFile::GetFileFromPathAsync(&HSTRING::from(path_str))?.await?;
    let stream = file.OpenAsync(windows::Storage::FileAccessMode::Read)?.await?;
    let decoder = BitmapDecoder::CreateAsync(&stream)?.await?;
    let bitmap = decoder.GetSoftwareBitmapAsync()?.await?;

    let result = engine.RecognizeAsync(&bitmap)?.await?;
    let _ = std::fs::remove_file(&temp_file);

    let mut lines_out = Vec::new();
    for line in result.Lines()? {
        let text = line.Text()?.to_string();
        let mut words_out = Vec::new();
        for word in line.Words()? {
            let rect = word.BoundingRect()?;
            words_out.push(OcrWordInfo {
                text: word.Text()?.to_string(),
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
pub fn draw_bounding_box(img: &mut RgbaImage, bbox: &BoundingBox) {
    let color = Rgba([255, 140, 0, 255]); // Oranye
    let thickness = 4u32;
    let (w, h) = img.dimensions();

    let x1 = bbox.x;
    let y1 = bbox.y;
    let x2 = (bbox.x + bbox.width).min(w - 1);
    let y2 = (bbox.y + bbox.height).min(h - 1);

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

fn is_buyer_conclusion(text: &str) -> bool {
    let lower = text.to_lowercase();
    lower.contains("pihak kedua/pembeli")
        || lower.contains("pihak kedua / pembeli")
        || lower.contains("pihak kedua/ pembeli")
        || lower.contains("pembeli\"")
        || (lower.contains("pihak kedua") && (lower.contains("disebut") || lower.contains("singkat")))
}

fn is_buyer_start(text: &str) -> bool {
    let trimmed = text.trim();
    let lower = text.to_lowercase();
    trimmed.starts_with("II.")
        || trimmed.starts_with("11.")
        || trimmed.starts_with("2.")
        || trimmed.starts_with("II-")
        || trimmed.starts_with("11-")
        || trimmed.starts_with("2-")
        || ((lower.starts_with("tuan ") || lower.starts_with("nona ") || lower.starts_with("nyonya ")) 
            && (lower.contains("warga negara") || lower.contains("lahir di")))
}

fn is_seller_conclusion(text: &str) -> bool {
    let lower = text.to_lowercase();
    lower.contains("pihak pertama/penjual")
        || lower.contains("pihak pertama / penjual")
        || lower.contains("pihak pertama/ penjual")
        || lower.contains("pihak pertama")
}

fn is_footer_line(text: &str) -> bool {
    let lower = text.to_lowercase();
    lower.contains("akta jual beli")
        || lower.contains("akta juaz beti")
        || lower.contains("akta juat beti")
        || lower.contains("halaman ")
        || lower.contains("daerah kerja")
        || lower.contains("lembar ")
}

/// Hitung bounding box dari sekumpulan baris OCR
fn compute_lines_bbox(lines: &[&OcrLineInfo], img_w: u32, img_h: u32, scale: f32) -> BoundingBox {
    let mut min_x = f32::MAX;
    let mut min_y = f32::MAX;
    let mut max_x = f32::MIN;
    let mut max_y = f32::MIN;

    for line in lines {
        for word in &line.words {
            if word.x < min_x { min_x = word.x; }
            if word.y < min_y { min_y = word.y; }
            if word.x + word.w > max_x { max_x = word.x + word.w; }
            if word.y + word.h > max_y { max_y = word.y + word.h; }
        }
    }

    let pad_left = 30.0f32 * (scale / 2.0);
    let pad_right = 35.0f32 * (scale / 2.0);
    let pad_top = 16.0f32 * (scale / 2.0);
    let pad_bottom = 16.0f32 * (scale / 2.0);

    let crop_x = (min_x - pad_left).max(0.0) as u32;
    let crop_y = (min_y - pad_top).max(0.0) as u32;
    let crop_w = ((max_x + pad_right) - (crop_x as f32)).min((img_w - crop_x) as f32) as u32;
    let crop_h = ((max_y + pad_bottom) - (crop_y as f32)).min((img_h - crop_y) as f32) as u32;

    BoundingBox {
        x: crop_x,
        y: crop_y,
        width: crop_w,
        height: crop_h,
    }
}

/// Fungsi utama: Proses dokumen PDF akta dan potong lokasi data pembeli
pub async fn process_akta_pdf(
    pdf_path: &Path,
    scale: f32,
    custom_id: Option<&str>,
) -> Result<CropResult, Box<dyn std::error::Error>> {
    let abs_pdf = std::fs::canonicalize(pdf_path)?;
    let pdf_path_str = abs_pdf.to_str().unwrap().trim_start_matches(r"\\?\");

    let file = StorageFile::GetFileFromPathAsync(&HSTRING::from(pdf_path_str))?.await?;
    let doc = PdfDocument::LoadFromFileAsync(&file)?.await?;
    let total_pages = doc.PageCount()? as usize;
    let engine = OcrEngine::TryCreateFromUserProfileLanguages()?;

    // 1. Render dan OCR semua halaman
    let mut pages_data = Vec::new();
    for page_idx in 0..total_pages {
        let dyn_img = render_pdf_page(&doc, page_idx as u32, scale).await?;
        let (raw_w, raw_h) = (dyn_img.width(), dyn_img.height());

        let (upright_img, rot) = if raw_w > raw_h {
            (imageops::rotate270(&dyn_img), 270)
        } else {
            (dyn_img.to_rgba8(), 0)
        };

        let lines = run_ocr_on_image(&upright_img, &engine, page_idx).await?;
        pages_data.push((upright_img, lines, rot));
    }

    // 2. Temukan penutup identitas pembeli: "Pihak Kedua/Pembeli"
    let mut end_location: Option<(usize, usize)> = None; // (page_idx, line_idx)
    for (p_idx, (_img, lines, _rot)) in pages_data.iter().enumerate() {
        for (l_idx, line) in lines.iter().enumerate() {
            if is_buyer_conclusion(&line.text) {
                end_location = Some((p_idx, l_idx));
                break;
            }
        }
        if end_location.is_some() {
            break;
        }
    }

    let (end_page_idx, end_line_idx) = end_location.ok_or("Bagian data pembeli tidak ditemukan dalam dokumen akta.")?;

    // 3. Tentukan apakah awal pembeli ada di halaman yang sama atau halaman sebelumnya
    let (upright_end, lines_end, rot_applied) = &pages_data[end_page_idx];

    let mut start_line_same_page = None;
    for l_idx in (0..end_line_idx).rev() {
        if is_seller_conclusion(&lines_end[l_idx].text) {
            start_line_same_page = Some(l_idx + 1);
            break;
        }
        if is_buyer_start(&lines_end[l_idx].text) {
            start_line_same_page = Some(l_idx);
            break;
        }
    }

    // KASUS A: Seluruh data pembeli berada pada SATU halaman yang sama
    if let Some(start_line_idx) = start_line_same_page {
        let selected_lines: Vec<&OcrLineInfo> = (start_line_idx..=end_line_idx)
            .map(|i| &lines_end[i])
            .collect();

        let (w, h) = upright_end.dimensions();
        let bbox = compute_lines_bbox(&selected_lines, w, h, scale);

        let cropped_image = imageops::crop_imm(upright_end, bbox.x, bbox.y, bbox.width, bbox.height).to_image();
        let mut annotated_page = upright_end.clone();
        draw_bounding_box(&mut annotated_page, &bbox);

        let raw_text = selected_lines.iter().map(|l| l.text.as_str()).collect::<Vec<_>>().join("\n");
        let buyer_info = parser::parse_buyer_to_custom_json(&raw_text, custom_id);

        return Ok(CropResult {
            success: true,
            page_number: end_page_idx + 1,
            total_pages,
            rotation_applied: *rot_applied,
            bbox,
            raw_text,
            buyer_info,
            cropped_image,
            annotated_page,
        });
    }

    // KASUS B: Data pembeli TERPOTONG DUA HALAMAN (Dimulai di halaman sebelumnya dan selesai di halaman ini)
    if end_page_idx > 0 {
        let start_page_idx = end_page_idx - 1;
        let (upright_start, lines_start, _) = &pages_data[start_page_idx];

        // 1. Cari penutup pihak penjual di halaman sebelumnya
        let mut seller_end_idx = None;
        for (l_idx, line) in lines_start.iter().enumerate() {
            if is_seller_conclusion(&line.text) {
                seller_end_idx = Some(l_idx);
            }
        }

        // 2. Awal pembeli dimulai setelah penjual atau baris II.-
        let mut start_line_prev = None;
        if let Some(s_end) = seller_end_idx {
            for l_idx in (s_end + 1)..lines_start.len() {
                if is_buyer_start(&lines_start[l_idx].text) {
                    start_line_prev = Some(l_idx);
                    break;
                }
            }
            if start_line_prev.is_none() {
                start_line_prev = Some(s_end + 1);
            }
        } else {
            for (l_idx, line) in lines_start.iter().enumerate() {
                if is_buyer_start(&line.text) {
                    start_line_prev = Some(l_idx);
                    break;
                }
            }
        }

        let start_line_idx = start_line_prev.unwrap_or(0);

        // Ambil semua baris pembeli di halaman sebelumnya sebelum footer
        let mut selected_lines_p1: Vec<&OcrLineInfo> = Vec::new();
        for l_idx in start_line_idx..lines_start.len() {
            if is_footer_line(&lines_start[l_idx].text) {
                break;
            }
            selected_lines_p1.push(&lines_start[l_idx]);
        }

        // Ambil baris pembeli di halaman penutup (dari baris 0 s/d end_line_idx)
        let selected_lines_p2: Vec<&OcrLineInfo> = (0..=end_line_idx)
            .map(|i| &lines_end[i])
            .collect();

        // Hitung BBox potongan 1 (Halaman sebelumnya)
        let (w1, h1) = upright_start.dimensions();
        let bbox1 = compute_lines_bbox(&selected_lines_p1, w1, h1, scale);
        let crop1 = imageops::crop_imm(upright_start, bbox1.x, bbox1.y, bbox1.width, bbox1.height).to_image();

        // Hitung BBox potongan 2 (Halaman penutup)
        let (w2, h2) = upright_end.dimensions();
        let bbox2 = compute_lines_bbox(&selected_lines_p2, w2, h2, scale);
        let crop2 = imageops::crop_imm(upright_end, bbox2.x, bbox2.y, bbox2.width, bbox2.height).to_image();

        // Gabungkan kedua potongan secara vertikal (stitching)
        let out_w = bbox1.width.max(bbox2.width);
        let out_h = bbox1.height + bbox2.height;
        let mut stitched = RgbaImage::from_pixel(out_w, out_h, Rgba([255, 255, 255, 255]));

        imageops::overlay(&mut stitched, &crop1, 0, 0);
        imageops::overlay(&mut stitched, &crop2, 0, bbox1.height as i64);

        let mut annotated_page = upright_start.clone();
        draw_bounding_box(&mut annotated_page, &bbox1);

        // Gabungkan teks dari kedua halaman
        let mut raw_lines = Vec::new();
        for l in &selected_lines_p1 {
            raw_lines.push(l.text.clone());
        }
        for l in &selected_lines_p2 {
            raw_lines.push(l.text.clone());
        }
        let raw_text = raw_lines.join("\n");
        let buyer_info = parser::parse_buyer_to_custom_json(&raw_text, custom_id);

        return Ok(CropResult {
            success: true,
            page_number: start_page_idx + 1, // Dimulai dari halaman awal pembeli
            total_pages,
            rotation_applied: *rot_applied,
            bbox: BoundingBox {
                x: bbox1.x,
                y: bbox1.y,
                width: out_w,
                height: out_h,
            },
            raw_text,
            buyer_info,
            cropped_image: stitched,
            annotated_page,
        });
    }

    Err("Gagal menentukan batas awal data pembeli pada dokumen akta.".into())
}
