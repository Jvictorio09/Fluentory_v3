from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO
from datetime import datetime
import os
import cloudinary
import cloudinary.uploader


def generate_certificate_pdf(user_name, course_name, issued_date, certificate_id=None, modules=None):
    """
    Generate a PDF certificate for course completion.
    
    Args:
        user_name: Full name of the student
        course_name: Name of the completed course
        issued_date: Date when certificate was issued (datetime object)
        certificate_id: Optional certificate ID/number
        modules: Optional list of module names to display on certificate
        
    Returns:
        BytesIO object containing the PDF certificate
    """
    buffer = BytesIO()
    # Use landscape orientation - swap width and height
    width, height = landscape(A4)

    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # ===== Background Border =====
    margin = 40
    c.setStrokeColor(colors.HexColor("#d4af37"))  # gold tone
    c.setLineWidth(4)
    c.rect(margin, margin, width - 2*margin, height - 2*margin)

    inner_margin = 60
    c.setLineWidth(1)
    c.rect(inner_margin, inner_margin, width - 2*inner_margin, height - 2*inner_margin)

    # ===== Title - Use course name, make it uppercase for certificate style =====
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(colors.HexColor("#1e293b"))
    # Truncate if too long, or use a shorter version
    title_text = course_name.upper()
    if len(title_text) > 50:
        # Try to use a shorter version or split
        title_text = course_name.upper()[:47] + "..."
    c.drawCentredString(width / 2, height - 100, title_text)

    # ===== Subtitle =====
    c.setFont("Helvetica", 18)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawCentredString(width / 2, height - 140, "HAS SUCCESSFULLY COMPLETED THE")

    # Course name subtitle - truncate if needed
    course_subtitle = course_name.upper()
    if len(course_subtitle) > 60:
        course_subtitle = course_subtitle[:57] + "..."
    c.drawCentredString(width / 2, height - 170, course_subtitle)

    # ===== Student Name =====
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor("#000000"))
    c.drawCentredString(width / 2, height - 230, user_name)

    # ===== Course Content Block (Modules) =====
    if modules and len(modules) > 0:
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor("#374151"))
        
        # In landscape, we can fit more modules side by side or in columns
        y_position = height - 280
        max_modules = 12  # Can fit more in landscape
        
        for i, module in enumerate(modules[:max_modules]):
            # Format: "Module X - Module Name" or just "Module Name"
            module_text = module
            if len(module_text) > 70:
                module_text = module_text[:67] + "..."
            c.drawCentredString(width / 2, y_position, module_text)
            y_position -= 16

    # ===== Date & Certificate ID =====
    date_str = issued_date.strftime("%B %d, %Y")

    c.setFont("Helvetica", 12)
    c.drawString(inner_margin + 20, inner_margin + 40, f"Date: {date_str}")

    if certificate_id:
        c.drawRightString(width - inner_margin - 20, inner_margin + 40,
                          f"Certificate ID: {certificate_id}")

    # ===== Signature Line =====
    c.line(width - 250, inner_margin + 80, width - 100, inner_margin + 80)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width - 175, inner_margin + 65, "Authorized Signature")

    c.save()
    buffer.seek(0)
    return buffer


def upload_certificate_to_cloudinary(pdf_buffer, user_id, course_slug):
    """
    Upload certificate PDF to Cloudinary.
    
    Args:
        pdf_buffer: BytesIO object containing the PDF
        user_id: User ID for organizing files
        course_slug: Course slug for organizing files
        
    Returns:
        Dictionary with 'url' and 'public_id' of uploaded certificate
    """
    try:
        # Configure Cloudinary if not already configured
        if not cloudinary.config().cloud_name:
            cloudinary.config(
                cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                api_key=os.getenv('CLOUDINARY_API_KEY'),
                api_secret=os.getenv('CLOUDINARY_API_SECRET')
            )
        
        # Upload PDF to Cloudinary
        upload_result = cloudinary.uploader.upload(
            pdf_buffer,
            resource_type='raw',  # PDFs are raw files
            folder=f'certificates/{course_slug}',
            public_id=f'cert_{user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            format='pdf',
            overwrite=False
        )
        
        return {
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id']
        }
    except Exception as e:
        print(f"Error uploading certificate to Cloudinary: {str(e)}")
        return None


def generate_certificate(user, course, issued_date=None, upload_to_cloudinary=True):
    """
    Generate a certificate for a user and course.
    
    Args:
        user: User object
        course: Course object
        issued_date: Optional datetime (defaults to now)
        upload_to_cloudinary: Whether to upload to Cloudinary (default True)
        
    Returns:
        Dictionary with certificate URL and certificate ID, or None if error
    """
    if issued_date is None:
        issued_date = datetime.now()
    
    # Generate certificate ID
    certificate_id = f"CERT-{course.slug.upper()}-{user.id}-{issued_date.strftime('%Y%m%d')}"
    
    # Get user's full name
    user_name = user.get_full_name() or user.username
    
    # Get course modules dynamically
    modules = []
    try:
        course_modules = course.modules.all().order_by('order', 'id')
        modules = [f"Module {i+1} - {module.name}" for i, module in enumerate(course_modules)]
    except Exception:
        # If modules don't exist or error, just use empty list
        pass
    
    # Generate PDF
    pdf_buffer = generate_certificate_pdf(
        user_name=user_name,
        course_name=course.name,
        issued_date=issued_date,
        certificate_id=certificate_id,
        modules=modules
    )
    
    # Upload to Cloudinary if requested
    if upload_to_cloudinary:
        upload_result = upload_certificate_to_cloudinary(
            pdf_buffer,
            user.id,
            course.slug
        )
        
        if upload_result:
            return {
                'certificate_url': upload_result['url'],
                'certificate_id': certificate_id,
                'public_id': upload_result['public_id']
            }
        else:
            # If upload fails, return None
            return None
    else:
        # Return PDF buffer for direct download
        return {
            'pdf_buffer': pdf_buffer,
            'certificate_id': certificate_id
        }
