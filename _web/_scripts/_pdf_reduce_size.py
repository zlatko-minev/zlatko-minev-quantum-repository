"""
```sh
python _pdf_reduce_size.py . --output _compressedV2 --dpi 180 --max-width 1800 --max-height 1800 --db db.txt
```
"""
import os
import subprocess
import shutil
import csv
import hashlib
import datetime
from PIL import Image
import tempfile
import PyPDF2
from tqdm import tqdm
import time
import sys

class TempLogger:
    """Temporary logger that overwrites the previous line"""
    def __init__(self, desc="Processing"):
        self.desc = desc
        self.last_msg_length = 0
    
    def update(self, message):
        # Clear the previous message by printing spaces
        sys.stdout.write('\r' + ' ' * self.last_msg_length)
        # Print the new message
        full_message = f"\r{self.desc}: {message}"
        sys.stdout.write(full_message)
        sys.stdout.flush()
        # Update the message length
        self.last_msg_length = len(full_message)
    
    def finish(self):
        # Clear the line when done
        sys.stdout.write('\r' + ' ' * self.last_msg_length + '\r')
        sys.stdout.flush()

def get_file_hash(file_path):
    """Generate a unique hash for a file based on its content"""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read(65536)  # Read in 64k chunks
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def is_already_processed(file_path, processed_db):
    """Check if a file has already been processed using the database"""
    file_hash = get_file_hash(file_path)
    
    for entry in processed_db:
        if entry['file_hash'] == file_hash:
            return True
    
    return False

def update_processed_db(file_path, original_path, processed_db, processed_db_path):
    """Add a processed file to the database"""
    file_hash = get_file_hash(file_path)
    file_size_before = os.path.getsize(original_path) / (1024 * 1024)  # Size in MB
    file_size_after = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
    compression_ratio = file_size_before / file_size_after if file_size_after > 0 else 0
    
    new_entry = {
        'file_hash': file_hash,
        'original_path': original_path,
        'processed_path': file_path,
        'original_filename': os.path.basename(original_path),
        'date_processed': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'original_size_mb': round(file_size_before, 2),
        'processed_size_mb': round(file_size_after, 2),
        'compression_ratio': round(compression_ratio, 2)
    }
    
    processed_db.append(new_entry)
    
    # Write to CSV
    fieldnames = list(new_entry.keys())
    
    # Check if file exists to determine if we need to write headers
    file_exists = os.path.isfile(processed_db_path)
    
    with open(processed_db_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header only if the file is new
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(new_entry)
    
    return processed_db

def load_processed_db(db_path):
    """Load the database of processed files"""
    processed_db = []
    
    if os.path.exists(db_path):
        with open(db_path, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                processed_db.append(row)
    
    return processed_db

def compress_pdf(input_path, output_path, dpi=150, quality=85, max_width=1920, max_height=1080):
    """Compress a PDF file with optimized images"""
    temp_dir = tempfile.mkdtemp()
    logger = TempLogger("Compressing")
    
    try:
        # Extract info about the PDF
        pdf_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        logger.update(f"Analyzing PDF: {os.path.basename(input_path)} ({pdf_size_mb:.2f} MB)")
        
        # Extract images using pdfimages
        logger.update(f"Extracting images from {os.path.basename(input_path)}")
        subprocess.run(
            ['pdfimages', '-all', input_path, os.path.join(temp_dir, 'img')],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Get list of extracted images
        images = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
        
        # Process each image
        if images:
            logger.update(f"Processing {len(images)} images")
            for i, img_file in enumerate(images):
                img_path = os.path.join(temp_dir, img_file)
                try:
                    # Skip non-image files that might have been extracted
                    try:
                        img = Image.open(img_path)
                    except:
                        continue
                    
                    # Update progress
                    progress = (i + 1) / len(images) * 100
                    logger.update(f"Optimizing image {i+1}/{len(images)} ({progress:.1f}%)")
                    
                    # Resize if needed
                    width, height = img.size
                    if width > max_width or height > max_height:
                        # Calculate new dimensions while preserving aspect ratio
                        ratio = min(max_width / width, max_height / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Save with compression
                    img.save(img_path, optimize=True, quality=quality)
                    img.close()
                except Exception as e:
                    logger.update(f"Error with image {img_file}: {str(e)[:50]}...")
                    time.sleep(0.5)  # Let user see the error briefly
        else:
            logger.update("No images found to optimize")
        
        # Use Ghostscript to compress the PDF
        logger.update(f"Applying PDF compression (DPI: {dpi}, Quality: {quality})")
        subprocess.run([
            'gs', '-sDEVICE=pdfwrite', 
            f'-dPDFSETTINGS=/ebook',
            f'-dCompatibilityLevel=1.4',
            f'-dDownsampleColorImages=true',
            f'-dColorImageResolution={dpi}',
            f'-dDownsampleGrayImages=true', 
            f'-dGrayImageResolution={dpi}',
            f'-dDownsampleMonoImages=true',
            f'-dMonoImageResolution={dpi}',
            '-dJPEGQ=85',
            '-dNOPAUSE', '-dQUIET', '-dBATCH',
            f'-sOutputFile={output_path}',
            input_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Final result
        new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        reduction = (1 - (new_size_mb / pdf_size_mb)) * 100 if pdf_size_mb > 0 else 0
        logger.update(f"Completed: {os.path.basename(input_path)} - {pdf_size_mb:.2f} MB → {new_size_mb:.2f} MB ({reduction:.1f}% reduction)")
        time.sleep(1)  # Show the final result briefly
        logger.finish()
        return True
        
    except Exception as e:
        logger.update(f"Error: {str(e)[:100]}")
        time.sleep(1)  # Show the error briefly
        logger.finish()
        # If compression fails, just copy the original
        shutil.copy2(input_path, output_path)
        return False
    
    finally:
        # Clean up temp directory
        logger.finish()
        shutil.rmtree(temp_dir)

def process_pdfs(root_folder, output_folder=None, db_path=None, dpi=150, quality=85, max_width=1920, max_height=1080):
    """Process all PDFs in root_folder and its subfolders"""
    # If no output folder specified, create one
    if output_folder is None:
        output_folder = os.path.join(os.path.dirname(root_folder), 
                                      os.path.basename(root_folder) + "_compressed")
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Set up database path
    if db_path is None:
        db_path = os.path.join(os.path.dirname(root_folder), "pdf_compression_log.csv")
    
    # Load database
    print(f"Loading database from: {db_path}")
    processed_db = load_processed_db(db_path)
    print(f"Found {len(processed_db)} previously processed files in database")
    
    # Find all PDFs first
    print("Scanning directories for PDF files...")
    pdf_files = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.lower().endswith('.pdf'):
                input_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(dirpath, root_folder)
                cur_output_dir = os.path.join(output_folder, rel_path)
                output_path = os.path.join(cur_output_dir, filename)
                pdf_files.append((input_path, output_path, cur_output_dir))
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Process PDFs with a progress bar
    total_pdfs = len(pdf_files)
    compressed_pdfs = 0
    skipped_pdfs = 0
    
    for input_path, output_path, cur_output_dir in tqdm(pdf_files, desc="Overall Progress", unit="file"):
        # Create output directory if it doesn't exist
        os.makedirs(cur_output_dir, exist_ok=True)
        
        # Skip already processed files
        if is_already_processed(input_path, processed_db):
            tqdm.write(f"Skipping: {os.path.basename(input_path)} (already in database)")
            # Just copy the file if it doesn't exist in output
            if not os.path.exists(output_path):
                shutil.copy2(input_path, output_path)
            skipped_pdfs += 1
        else:
            success = compress_pdf(
                input_path, 
                output_path,
                dpi=dpi,
                quality=quality,
                max_width=max_width,
                max_height=max_height
            )
            
            if success:
                # Update database
                processed_db = update_processed_db(output_path, input_path, processed_db, db_path)
                compressed_pdfs += 1
    
    # Print final summary
    print("\n" + "="*50)
    print("Processing Summary:")
    print(f"Total PDFs found: {total_pdfs}")
    print(f"PDFs compressed: {compressed_pdfs}")
    print(f"PDFs skipped (already processed): {skipped_pdfs}")
    print(f"Output folder: {output_folder}")
    print(f"Database: {db_path}")
    
    # Calculate overall space savings
    if compressed_pdfs > 0:
        total_original = sum(float(entry['original_size_mb']) for entry in processed_db[-compressed_pdfs:])
        total_compressed = sum(float(entry['processed_size_mb']) for entry in processed_db[-compressed_pdfs:])
        space_saved = total_original - total_compressed
        percent_saved = (space_saved / total_original) * 100 if total_original > 0 else 0
        
        print("\nSpace Savings:")
        print(f"Original size: {total_original:.2f} MB")
        print(f"Compressed size: {total_compressed:.2f} MB")
        print(f"Space saved: {space_saved:.2f} MB ({percent_saved:.1f}%)")
    print("="*50)

if __name__ == "__main__":
    import argparse
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Default database path is in the script directory
    default_db_path = os.path.join(os.path.dirname(script_dir), "pdf_compression_log.csv")
    
    parser = argparse.ArgumentParser(description="Compress PDFs with optimized images")
    parser.add_argument("input_folder", help="Input folder containing PDFs to compress")
    parser.add_argument("--output", "-o", help="Output folder for compressed PDFs")
    parser.add_argument("--db", help="Path to the CSV database file", default=default_db_path)
    parser.add_argument("--dpi", type=int, default=150, help="DPI for images (default: 150)")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality (0-100, default: 85)")
    parser.add_argument("--max-width", type=int, default=1920, help="Maximum image width (default: 1920)")
    parser.add_argument("--max-height", type=int, default=1080, help="Maximum image height (default: 1080)")
    
    args = parser.parse_args()
    
    # Print script banner
    print("="*50)
    print("PDF Compression Tool")
    print("="*50)
    print(f"Input folder: {args.input_folder}")
    print(f"Output folder: {args.output or 'auto'}")
    print(f"Database: {args.db}")
    print(f"Settings: DPI={args.dpi}, Quality={args.quality}, Max dimensions={args.max_width}x{args.max_height}")
    print("="*50)
    
    # Run the main process
    process_pdfs(
        args.input_folder, 
        args.output,
        args.db,
        dpi=args.dpi,
        quality=args.quality,
        max_width=args.max_width,
        max_height=args.max_height
    )