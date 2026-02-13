"""
PDF Image Extraction and Cloudinary Upload Utility
Extracts images from PDF files, converts them to WebP format, and uploads to Cloudinary.
"""
import os
import tempfile
from typing import List, Dict, Optional
from io import BytesIO

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False


class PDFImageExtractor:
    """Extract images from PDF files and upload to Cloudinary"""
    
    def __init__(self):
        """Initialize PDF image extractor"""
        if not PYMUPDF_AVAILABLE:
            raise ImportError(
                "PyMuPDF (fitz) is not installed. Install it: pip install PyMuPDF"
            )
        if not PILLOW_AVAILABLE:
            raise ImportError(
                "Pillow is not installed. Install it: pip install Pillow"
            )
        if not CLOUDINARY_AVAILABLE:
            raise ImportError(
                "Cloudinary is not installed. Install it: pip install cloudinary"
            )
        
        # Configure Cloudinary from environment variables
        self._configure_cloudinary()
    
    def _configure_cloudinary(self):
        """Configure Cloudinary from environment variables"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', ''),
            api_key=os.getenv('CLOUDINARY_API_KEY', ''),
            api_secret=os.getenv('CLOUDINARY_API_SECRET', ''),
            secure=True
        )
        
        # Verify configuration
        if not all([
            cloudinary.config().cloud_name,
            cloudinary.config().api_key,
            cloudinary.config().api_secret
        ]):
            raise ValueError(
                "Cloudinary credentials not configured. "
                "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET environment variables."
            )
    
    def extract_images(self, pdf_path: str, min_size: int = 1000) -> List[Dict[str, any]]:
        """
        Extract images from PDF file
        
        Args:
            pdf_path: Path to PDF file
            min_size: Minimum image size in pixels (width or height) to include
            
        Returns:
            List of dicts with 'image_data', 'page_num', 'x0', 'y0', 'x1', 'y1', 'width', 'height'
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        images = []
        
        try:
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Get image position on page
                        image_rects = page.get_image_rects(xref)
                        if image_rects:
                            rect = image_rects[0]
                        else:
                            # Fallback: use page dimensions
                            rect = page.rect
                        
                        # Convert to PIL Image to get dimensions
                        image = Image.open(BytesIO(image_bytes))
                        width, height = image.size
                        
                        # Filter by minimum size
                        if width >= min_size or height >= min_size:
                            images.append({
                                'image_data': image_bytes,
                                'image_format': image_ext,
                                'page_num': page_num + 1,
                                'x0': rect.x0,
                                'y0': rect.y0,
                                'x1': rect.x1,
                                'y1': rect.y1,
                                'width': width,
                                'height': height,
                                'image': image,  # PIL Image object
                            })
                    except Exception as e:
                        # Skip images that can't be processed
                        print(f"Warning: Could not process image {img_index} on page {page_num + 1}: {str(e)}")
                        continue
            
            pdf_document.close()
            
        except Exception as e:
            raise Exception(f"Error extracting images from PDF: {str(e)}")
        
        return images
    
    def convert_to_webp(self, image: Image.Image, quality: int = 85) -> bytes:
        """
        Convert PIL Image to WebP format
        
        Args:
            image: PIL Image object
            quality: WebP quality (1-100, default 85)
            
        Returns:
            WebP image bytes
        """
        if not isinstance(image, Image.Image):
            raise ValueError("Input must be a PIL Image object")
        
        # Convert RGBA to RGB if necessary (WebP supports RGBA, but we'll convert for compatibility)
        if image.mode == 'RGBA':
            # Create white background
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            image = rgb_image
        elif image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Convert to WebP
        webp_buffer = BytesIO()
        image.save(webp_buffer, format='WEBP', quality=quality, method=6)
        webp_buffer.seek(0)
        
        return webp_buffer.getvalue()
    
    def upload_to_cloudinary(
        self, 
        image_bytes: bytes, 
        folder: str = 'pdf-lessons',
        public_id_prefix: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Upload image to Cloudinary
        
        Args:
            image_bytes: Image bytes (should be WebP format)
            folder: Cloudinary folder path
            public_id_prefix: Optional prefix for public_id (e.g., lesson slug)
            
        Returns:
            Dict with 'url', 'public_id', 'secure_url'
        """
        import uuid
        
        # Generate unique public_id
        unique_id = str(uuid.uuid4())[:8]
        if public_id_prefix:
            public_id = f"{folder}/{public_id_prefix}_{unique_id}"
        else:
            public_id = f"{folder}/{unique_id}"
        
        try:
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_bytes,
                public_id=public_id,
                folder=folder,
                format='webp',
                resource_type='image',
                overwrite=False,
            )
            
            return {
                'url': result.get('url', ''),
                'secure_url': result.get('secure_url', ''),
                'public_id': result.get('public_id', ''),
                'width': result.get('width', 0),
                'height': result.get('height', 0),
            }
        except Exception as e:
            raise Exception(f"Error uploading image to Cloudinary: {str(e)}")
    
    def extract_and_upload_images(
        self, 
        pdf_path: str, 
        folder: str = 'pdf-lessons',
        public_id_prefix: Optional[str] = None,
        min_size: int = 1000,
        quality: int = 85
    ) -> List[Dict[str, any]]:
        """
        Extract images from PDF, convert to WebP, and upload to Cloudinary
        
        Args:
            pdf_path: Path to PDF file
            folder: Cloudinary folder path
            public_id_prefix: Optional prefix for public_id
            min_size: Minimum image size in pixels
            quality: WebP quality (1-100)
            
        Returns:
            List of dicts with Cloudinary URLs and metadata
        """
        extracted_images = self.extract_images(pdf_path, min_size=min_size)
        uploaded_images = []
        
        for img_data in extracted_images:
            try:
                # Convert to WebP
                webp_bytes = self.convert_to_webp(img_data['image'], quality=quality)
                
                # Upload to Cloudinary
                upload_result = self.upload_to_cloudinary(
                    webp_bytes,
                    folder=folder,
                    public_id_prefix=public_id_prefix
                )
                
                # Combine metadata
                uploaded_images.append({
                    'url': upload_result['secure_url'],
                    'public_id': upload_result['public_id'],
                    'page_num': img_data['page_num'],
                    'width': upload_result['width'],
                    'height': upload_result['height'],
                    'x0': img_data['x0'],
                    'y0': img_data['y0'],
                    'x1': img_data['x1'],
                    'y1': img_data['y1'],
                })
                
            except Exception as e:
                print(f"Warning: Could not upload image from page {img_data['page_num']}: {str(e)}")
                continue
        
        return uploaded_images

