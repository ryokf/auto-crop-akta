use std::path::{Path, PathBuf};
use clap::Parser;
use auto_crop_akta::process_akta_pdf;

#[derive(Parser, Debug)]
#[command(name = "auto-crop-akta")]
#[command(author = "DeepMind Pair Programming")]
#[command(version = "0.1.0")]
#[command(about = "Program Pemotong Otomatis Lokasi Data Pembeli pada Akta Tanah / PPAT (PDF) dalam Rust")]
struct Cli {
    /// Jalur file PDF akta atau folder berisi berkas PDF
    #[arg(required = true)]
    input: PathBuf,

    /// Jalur file gambar hasil potongan (default: [nama_file]_crop_pembeli.png)
    #[arg(short, long)]
    output: Option<PathBuf>,

    /// Folder tujuan penyimpanan jika memproses banyak file PDF sekaligus
    #[arg(long)]
    out_dir: Option<PathBuf>,

    /// Simpan juga gambar satu halaman penuh dengan highlight kotak penanda
    #[arg(long, default_value_t = false)]
    annotated: bool,

    /// Simpan data pembeli ke file format JSON sesuai spesifikasi
    #[arg(long, default_value_t = false)]
    json: bool,

    /// Nilai ID kustom untuk output JSON (default: "12345")
    #[arg(long)]
    id: Option<String>,

    /// Skala resolusi rendering PDF (default: 2.0)
    #[arg(long, default_value_t = 2.0)]
    scale: f32,
}

async fn handle_single_pdf(
    pdf_path: &Path,
    output_path: &Path,
    annotated_path: Option<&Path>,
    save_json: bool,
    custom_id: Option<&str>,
    scale: f32,
) -> Result<(), Box<dyn std::error::Error>> {
    println!("\n[MEMPROSES] {} ...", pdf_path.display());

    let result = process_akta_pdf(pdf_path, scale, custom_id).await?;

    // Simpan gambar hasil crop
    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    result.cropped_image.save(output_path)?;

    println!("[BERHASIL]");
    println!("  * Halaman Ditemukan  : Halaman {} dari {}", result.page_number, result.total_pages);
    println!("  * Rotasi Otomatis    : {} derajat", result.rotation_applied);
    println!("  * Koordinat Bounding : x={}, y={}, w={}, h={}", result.bbox.x, result.bbox.y, result.bbox.width, result.bbox.height);
    println!("  * Hasil Potongan     : {}", output_path.display());

    if let Some(ann_path) = annotated_path {
        result.annotated_page.save(ann_path)?;
        println!("  * Halaman Beranotasi : {}", ann_path.display());
    }

    let json_output_str = serde_json::to_string_pretty(&result.buyer_info)?;
    println!("\n--- JSON Data Pembeli ---");
    println!("{}", json_output_str);

    if save_json {
        let json_path = output_path.with_extension("json");
        std::fs::write(&json_path, &json_output_str)?;
        println!("\n  * File JSON Disimpan : {}", json_path.display());
    }

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Cli::parse();

    if !args.input.exists() {
        eprintln!("Error: Jalur input '{}' tidak ditemukan.", args.input.display());
        std::process::exit(1);
    }

    if args.input.is_file() {
        let file_stem = args.input.file_stem().unwrap().to_str().unwrap();
        let default_out = args.input.with_file_name(format!("{}_crop_pembeli.png", file_stem));
        let out_path = args.output.unwrap_or(default_out);

        let ann_path = if args.annotated {
            Some(args.input.with_file_name(format!("{}_annotated.png", file_stem)))
        } else {
            None
        };

        if let Err(e) = handle_single_pdf(
            &args.input,
            &out_path,
            ann_path.as_deref(),
            args.json,
            args.id.as_deref(),
            args.scale,
        ).await {
            eprintln!("[GAGAL] Terjadi kesalahan: {}", e);
            std::process::exit(1);
        }
    } else if args.input.is_dir() {
        let out_dir = args.out_dir.unwrap_or_else(|| args.input.join("hasil_crop"));
        std::fs::create_dir_all(&out_dir)?;

        let mut entries = Vec::new();
        for entry in std::fs::read_dir(&args.input)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() {
                if let Some(ext) = path.extension() {
                    if ext.to_string_lossy().to_lowercase() == "pdf" {
                        entries.push(path);
                    }
                }
            }
        }

        if entries.is_empty() {
            println!("Tidak ada file PDF ditemukan di folder '{}'.", args.input.display());
            return Ok(());
        }

        println!("Ditemukan {} file PDF. Menyimpan hasil ke: {}", entries.len(), out_dir.display());
        let mut success_count = 0;

        for pdf in &entries {
            let file_stem = pdf.file_stem().unwrap().to_str().unwrap();
            let out_file = out_dir.join(format!("{}_crop_pembeli.png", file_stem));
            let ann_file = if args.annotated {
                Some(out_dir.join(format!("{}_annotated.png", file_stem)))
            } else {
                None
            };

            match handle_single_pdf(
                pdf,
                &out_file,
                ann_file.as_deref(),
                args.json,
                args.id.as_deref(),
                args.scale,
            ).await {
                Ok(_) => success_count += 1,
                Err(e) => eprintln!("[GAGAL] {} : {}", pdf.display(), e),
            }
        }

        println!("\n[SELESAI] {} dari {} file berhasil diproses.", success_count, entries.len());
    }

    Ok(())
}
