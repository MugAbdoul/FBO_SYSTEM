import io
import base64
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter, legal
from reportlab.lib.colors import Color, black, white, blue, darkblue, gray, lightgrey, darkgreen
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
import textwrap
import math


class ModernCertificateGenerator:
    """
    Modern, professional certificate PDF generator with enhanced design,
    responsive layout, and improved signature/QR alignment.
    """
    
    def __init__(self, pagesize=A4):
        self.pagesize = pagesize
        self.width, self.height = pagesize
        
        # Reduced margins for more space
        self.margin_ratio = 0.035
        self.margin_x = self.width * self.margin_ratio
        self.margin_y = self.height * self.margin_ratio
        
        # Content area
        self.content_width = self.width - (2 * self.margin_x)
        self.content_height = self.height - (2 * self.margin_y)
        
        # Modern color palette - Rwanda government theme
        self.colors = {
            'rwanda_blue': Color(0.02, 0.24, 0.47),
            'rwanda_green': Color(0.0, 0.45, 0.23),
            'rwanda_yellow': Color(1.0, 0.82, 0.0),
            'primary': Color(0.02, 0.24, 0.47),
            'secondary': Color(0.25, 0.4, 0.65),
            'accent': Color(0.0, 0.45, 0.23),
            'gold': Color(0.85, 0.65, 0.13),
            'text_primary': Color(0.15, 0.15, 0.15),
            'text_secondary': Color(0.4, 0.4, 0.4),
            'background': Color(0.98, 0.98, 0.98),
            'card_bg': Color(0.97, 0.97, 0.99),
            'border_light': Color(0.85, 0.85, 0.85),
            'white': Color(1, 1, 1),
            'shadow': Color(0.9, 0.9, 0.9)
        }
        
        # Reduced font sizes
        self.font_sizes = self._calculate_font_sizes()
        
        # Reduced design constants
        self.border_radius = 6
        self.shadow_offset = 1
        self.line_height_ratio = 1.2
        
    def _calculate_font_sizes(self):
        """Calculate smaller, more compact font sizes"""
        base_size = min(self.width, self.height) / 70
        scale_ratio = 1.15
        
        return {
            'display': int(base_size * (scale_ratio ** 3)),
            'title': int(base_size * (scale_ratio ** 2.5)),
            'heading': int(base_size * (scale_ratio ** 2)),
            'subheading': int(base_size * (scale_ratio ** 1.5)),
            'body': int(base_size * scale_ratio),
            'small': int(base_size * 0.9),
            'caption': int(base_size * 0.8),
            'micro': int(base_size * 0.7)
        }
    
    def _draw_gradient_rect(self, canvas, x, y, width, height, color1, color2, vertical=True):
        """Draw a gradient rectangle with fewer steps for performance"""
        steps = 25
        if vertical:
            step_height = height / steps
            for i in range(steps):
                ratio = i / steps
                r = color1.red + (color2.red - color1.red) * ratio
                g = color1.green + (color2.green - color1.green) * ratio
                b = color1.blue + (color2.blue - color1.blue) * ratio
                canvas.setFillColor(Color(r, g, b))
                canvas.rect(x, y + i * step_height, width, step_height, fill=1, stroke=0)
    
    def _draw_watermark(self, canvas):
        """Draw subtle, smaller security watermark"""
        canvas.saveState()
        canvas.setFillColor(Color(0.97, 0.97, 0.97, alpha=0.4))
        canvas.setFont("Helvetica-Bold", 36)
        
        canvas.translate(self.width/2, self.height/2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 10, "AUTHENTICATED")
        canvas.drawCentredString(0, -30, "CERTIFICATE")
        
        canvas.restoreState()
    
    def _draw_modern_border(self, canvas):
        """Draw compact modern border"""
        # Outer frame
        frame_width = 4
        canvas.setStrokeColor(self.colors['primary'])
        canvas.setLineWidth(frame_width)
        canvas.roundRect(self.margin_x, self.margin_y, 
                        self.content_width, self.content_height, 
                        self.border_radius)
        
        # Inner frame
        inner_margin = 10
        canvas.setStrokeColor(self.colors['gold'])
        canvas.setLineWidth(1)
        canvas.roundRect(self.margin_x + inner_margin, self.margin_y + inner_margin,
                        self.content_width - (2 * inner_margin), 
                        self.content_height - (2 * inner_margin), 
                        self.border_radius - 2)
        
        # Smaller corner emblems
        corner_size = 15
        emblem_margin = 18
        corners = [
            (self.margin_x + emblem_margin, self.height - self.margin_y - emblem_margin),
            (self.width - self.margin_x - emblem_margin, self.height - self.margin_y - emblem_margin),
            (self.margin_x + emblem_margin, self.margin_y + emblem_margin),
            (self.width - self.margin_x - emblem_margin, self.margin_y + emblem_margin)
        ]
        
        canvas.setFillColor(self.colors['gold'])
        canvas.setStrokeColor(self.colors['primary'])
        canvas.setLineWidth(1)
        
        for x, y in corners:
            canvas.circle(x, y, corner_size/2, fill=1, stroke=1)
            canvas.setFillColor(self.colors['primary'])
            canvas.circle(x, y, corner_size/3, fill=1, stroke=0)
            canvas.setFillColor(self.colors['gold'])
    
    def _draw_enhanced_header(self, canvas, y_position):
        """Draw compact enhanced header"""
        header_height = 75
        header_margin = 25
        
        # Header background
        self._draw_gradient_rect(canvas, 
                               self.margin_x + header_margin, 
                               y_position - header_height,
                               self.content_width - (2 * header_margin), 
                               header_height,
                               self.colors['white'], 
                               self.colors['card_bg'])
        
        canvas.setStrokeColor(self.colors['border_light'])
        canvas.setLineWidth(1)
        canvas.roundRect(self.margin_x + header_margin, y_position - header_height,
                        self.content_width - (2 * header_margin), header_height,
                        self.border_radius, fill=0, stroke=1)
        
        current_y = y_position - 15
        
        # Government title
        canvas.setFillColor(self.colors['primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['title'])
        canvas.drawCentredString(self.width / 2, current_y, "REPUBLIC OF RWANDA")
        current_y -= self.font_sizes['title'] * 1.1
        
        # Flag colors accent line - smaller
        flag_line_width = 150
        flag_x = (self.width - flag_line_width) / 2
        flag_height = 3
        
        canvas.setFillColor(self.colors['rwanda_blue'])
        canvas.rect(flag_x, current_y, flag_line_width/3, flag_height, fill=1)
        canvas.setFillColor(self.colors['rwanda_yellow'])
        canvas.rect(flag_x + flag_line_width/3, current_y, flag_line_width/3, flag_height, fill=1)
        canvas.setFillColor(self.colors['rwanda_green'])
        canvas.rect(flag_x + 2*flag_line_width/3, current_y, flag_line_width/3, flag_height, fill=1)
        
        current_y -= 12
        
        # Organization name
        canvas.setFillColor(self.colors['text_primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['heading'])
        canvas.drawCentredString(self.width / 2, current_y, "RWANDA GOVERNANCE BOARD")
        current_y -= self.font_sizes['heading'] * 1.0
        
        # Motto
        canvas.setFillColor(self.colors['text_secondary'])
        canvas.setFont("Helvetica-Oblique", self.font_sizes['small'])
        canvas.drawCentredString(self.width / 2, current_y, "Unity • Work • Progress")
        
        return y_position - header_height - 15
    
    def _draw_certificate_title_card(self, canvas, y_position):
        """Draw compact certificate title card"""
        card_height = 55
        card_margin = 40
        
        # Card shadow - smaller
        canvas.setFillColor(self.colors['shadow'])
        canvas.roundRect(self.margin_x + card_margin + 1, 
                        y_position - card_height - 1,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=1, stroke=0)
        
        # Main card
        self._draw_gradient_rect(canvas,
                               self.margin_x + card_margin, 
                               y_position - card_height,
                               self.content_width - (2 * card_margin), 
                               card_height,
                               self.colors['primary'], 
                               self.colors['secondary'])
        
        canvas.setStrokeColor(self.colors['primary'])
        canvas.setLineWidth(2)
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=0, stroke=1)
        
        # Title text
        canvas.setFillColor(self.colors['white'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['display'])
        canvas.drawCentredString(self.width / 2, y_position - card_height * 0.35, 
                               "CERTIFICATE OF AUTHORIZATION")
        
        canvas.setFont("Helvetica", self.font_sizes['body'])
        canvas.drawCentredString(self.width / 2, y_position - card_height * 0.7, 
                               "Religious Organization Operation License")
        
        return y_position - card_height - 15
    
    def _draw_info_card(self, canvas, application, y_position):
        """Draw compact certificate information card"""
        card_height = 50
        card_margin = 35
        
        canvas.setFillColor(self.colors['card_bg'])
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=1, stroke=0)
        
        canvas.setStrokeColor(self.colors['border_light'])
        canvas.setLineWidth(1)
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=0, stroke=1)
        
        # Content layout
        left_x = self.margin_x + card_margin + 15
        right_x = self.width - self.margin_x - card_margin - 15
        content_y = y_position - 18
        
        # Left column
        canvas.setFillColor(self.colors['text_secondary'])
        canvas.setFont("Helvetica", self.font_sizes['small'])
        canvas.drawString(left_x, content_y, "Certificate No:")
        canvas.drawString(left_x, content_y - 15, "Issue Date:")
        
        canvas.setFillColor(self.colors['text_primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['small'])
        canvas.drawString(left_x + 85, content_y, application.certificate_number)
        canvas.drawString(left_x + 85, content_y - 15, 
                         application.certificate_issued_at.strftime('%B %d, %Y'))
        
        # Right column
        canvas.setFillColor(self.colors['text_secondary'])
        canvas.setFont("Helvetica", self.font_sizes['small'])
        canvas.drawRightString(right_x - 60, content_y, "Status:")
        canvas.drawRightString(right_x - 60, content_y - 15, "Validity:")
        
        canvas.setFillColor(self.colors['accent'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['small'])
        canvas.drawRightString(right_x, content_y, "ACTIVE")
        canvas.setFillColor(self.colors['text_primary'])
        canvas.drawRightString(right_x, content_y - 15, "Indefinite")
        
        return y_position - card_height - 12
    
    def _draw_section_header(self, canvas, title, y_position, icon_char="●"):
        """Draw compact section header"""
        canvas.setFillColor(self.colors['primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['small'])
        canvas.drawString(self.margin_x + 50, y_position, icon_char)
        
        canvas.setFont("Helvetica-Bold", self.font_sizes['subheading'])
        canvas.drawString(self.margin_x + 65, y_position, title)
        
        # Decorative underline
        line_width = len(title) * self.font_sizes['subheading'] * 0.5
        canvas.setStrokeColor(self.colors['gold'])
        canvas.setLineWidth(2)
        canvas.line(self.margin_x + 65, y_position - 3, 
                   self.margin_x + 65 + line_width, y_position - 3)
        
        return y_position - self.font_sizes['subheading'] * 1.2
    
    def _draw_organization_card(self, canvas, application, y_position):
        """Draw compact organization details card"""
        card_height = 85
        card_margin = 35
        
        y_position -= 10
        
        # Section header
        y_position = self._draw_section_header(canvas, "ORGANIZATION DETAILS", y_position, "🏛")
        y_position -= 8
        
        # Card background
        canvas.setFillColor(self.colors['white'])
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=1, stroke=0)
        
        # Left border accent
        canvas.setFillColor(self.colors['accent'])
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        4, card_height, 2, fill=1, stroke=0)
        
        canvas.setStrokeColor(self.colors['border_light'])
        canvas.setLineWidth(1)
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=0, stroke=1)
        
        # Content
        content_x = self.margin_x + card_margin + 20
        content_y = y_position - 18
        line_spacing = 18
        
        details = [
            ("Organization:", application.organization_name, self.colors['primary']),
            ("Representative:", f"{application.applicant.title} {application.applicant.firstname} {application.applicant.lastname}", self.colors['text_primary']),
            ("Address:", application.address, self.colors['text_primary']),
            ("Cluster:", getattr(application.cluster_information, 'cluster_of_intervention', 'General Religious Activities') if application.cluster_information else 'General Religious Activities', self.colors['accent'])
        ]
        
        for i, (label, value, color) in enumerate(details):
            y = content_y - (i * line_spacing)
            
            # Label
            canvas.setFillColor(self.colors['text_secondary'])
            canvas.setFont("Helvetica", self.font_sizes['small'])
            canvas.drawString(content_x, y, label)
            
            # Value
            value_x = content_x + 100
            available_width = self.content_width - card_margin * 2 - 125
            wrapped_lines = self._wrap_text(str(value), available_width, "Helvetica-Bold", self.font_sizes['small'])
            
            canvas.setFillColor(color)
            canvas.setFont("Helvetica-Bold", self.font_sizes['small'])
            
            for j, line in enumerate(wrapped_lines[:1]):  # Limit to 1 line
                canvas.drawString(value_x, y - (j * 10), line)
        
        return y_position - card_height - 15
    
    def _draw_authorization_card(self, canvas, y_position):
        """Draw compact authorization statement card"""
        card_height = 70
        card_margin = 35
        
        y_position -= 10
        
        # Section header
        y_position = self._draw_section_header(canvas, "AUTHORIZATION", y_position, "✓")
        y_position -= 8
        
        # Card
        self._draw_gradient_rect(canvas,
                               self.margin_x + card_margin, 
                               y_position - card_height,
                               self.content_width - (2 * card_margin), 
                               card_height,
                               Color(0.98, 1.0, 0.98), 
                               self.colors['white'])
        
        canvas.setStrokeColor(self.colors['accent'])
        canvas.setLineWidth(2)
        canvas.roundRect(self.margin_x + card_margin, y_position - card_height,
                        self.content_width - (2 * card_margin), card_height, 
                        self.border_radius, fill=0, stroke=1)
        
        # Authorization text
        canvas.setFillColor(self.colors['text_primary'])
        canvas.setFont("Helvetica", self.font_sizes['small'])
        
        statements = [
            "This organization is hereby AUTHORIZED to operate as a religious organization",
            "in Rwanda per Law N° 06/2012 of 17/09/2012 relating to Non-Profit Organizations.",
            "This authorization remains valid subject to continuous legal compliance."
        ]
        
        text_y = y_position - 30
        for statement in statements:
            canvas.drawCentredString(self.width / 2, text_y, statement)
            text_y -= self.font_sizes['small'] * 1.3
        
        return y_position - card_height - 15
    
    def _draw_signature_and_verification_section(self, canvas, application, y_position):
        """Draw well-aligned signature section with QR code verification"""
        section_height = 150
        section_margin = 35
        
        y_position -= 10
        
        # Section header
        y_position = self._draw_section_header(canvas, "DIGITAL AUTHORIZATION & VERIFICATION", y_position, "🔒")
        y_position -= 8
        
        # Main container
        container_x = self.margin_x + section_margin
        container_width = self.content_width - (2 * section_margin)
        container_y = y_position - section_height
        
        # Left side - Digital Signature (60% of container)
        sig_width = container_width * 0.6
        sig_x = container_x + 15
        sig_y = y_position - 20
        
        # Signature title
        canvas.setFillColor(self.colors['primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['small'])
        canvas.drawString(sig_x, sig_y, "DIGITALLY AUTHORIZED BY:")
        
        # Signature line
        canvas.setStrokeColor(self.colors['text_secondary'])
        canvas.setLineWidth(0.6)
        # canvas.line(sig_x, sig_y - 20, sig_x + sig_width - 30, sig_y - 20)
        
        # Signatory name
        canvas.setFillColor(self.colors['text_primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['body'])
        canvas.drawString(sig_x, sig_y - 20, "Prof. Anastase SHYAKA")
        
        # Position and organization
        canvas.setFont("Helvetica", self.font_sizes['small'])
        canvas.drawString(sig_x, sig_y - 32, "Chief Executive Officer")
        canvas.drawString(sig_x, sig_y - 42, "Rwanda Governance Board")
        
        # Digital timestamp
        canvas.setFillColor(self.colors['text_secondary'])
        canvas.setFont("Helvetica", self.font_sizes['caption'])
        timestamp_text = f"Digitally signed: {application.certificate_issued_at.strftime('%B %d, %Y at %H:%M UTC')}"
        canvas.drawString(sig_x, sig_y - 55, timestamp_text)
        
        # Right side - QR Code and Verification (40% of container)
        qr_section_width = container_width * 0.4
        qr_section_x = container_x + sig_width + 10
        qr_section_y = y_position - 15
        
        # QR Code area background
        qr_bg_width = qr_section_width - 20
        qr_bg_height = section_height - 20
        # canvas.setFillColor(self.colors['white'])
        # canvas.roundRect(qr_section_x, container_y + 10, qr_bg_width, qr_bg_height, 
        #                 4, fill=1, stroke=0)
        
        # canvas.setStrokeColor(self.colors['border_light'])
        # canvas.setLineWidth(1)
        # canvas.roundRect(qr_section_x, container_y + 10, qr_bg_width, qr_bg_height, 
        #                 4, fill=0, stroke=1)
        
        # QR Code
        if hasattr(application, 'qr_code_data') and application.qr_code_data:
            try:
                qr_size = 65
                qr_x = qr_section_x + (qr_bg_width - qr_size) / 2
                qr_y = container_y + qr_bg_height - qr_size - 5
                
                qr_data = base64.b64decode(application.qr_code_data)
                qr_buffer = io.BytesIO(qr_data)
                qr_image = ImageReader(qr_buffer)
                canvas.drawImage(qr_image, qr_x, qr_y, width=qr_size, height=qr_size)
                
                # QR Code label
                canvas.setFillColor(self.colors['primary'])
                canvas.setFont("Helvetica-Bold", self.font_sizes['caption'])
                canvas.drawCentredString(qr_section_x + qr_bg_width/2, qr_y - 8, "SCAN TO VERIFY")
                
                # Verification instructions
                canvas.setFillColor(self.colors['text_secondary'])
                canvas.setFont("Helvetica", self.font_sizes['micro'])
                canvas.drawCentredString(qr_section_x + qr_bg_width/2, qr_y - 18, "Scan QR code to verify")
                canvas.drawCentredString(qr_section_x + qr_bg_width/2, qr_y - 28, "certificate authenticity")
                
            except Exception as e:
                # Fallback if QR code fails
                canvas.setFillColor(self.colors['text_secondary'])
                canvas.setFont("Helvetica", self.font_sizes['small'])
                canvas.drawCentredString(qr_section_x + qr_bg_width/2, qr_section_y - 30, "QR CODE")
                canvas.drawCentredString(qr_section_x + qr_bg_width/2, qr_section_y - 45, "VERIFICATION")
        
        # Official seal in the signature area
        seal_size = 30
        seal_x = sig_x + sig_width - 240
        seal_y = sig_y - 92
        
        # Seal background
        canvas.setFillColor(self.colors['gold'])
        canvas.circle(seal_x, seal_y, seal_size + 2, fill=1, stroke=0)
        
        # Main seal
        canvas.setStrokeColor(self.colors['primary'])
        canvas.setFillColor(self.colors['white'])
        canvas.setLineWidth(2)
        canvas.circle(seal_x, seal_y, seal_size, fill=1, stroke=1)
        
        # Inner seal ring
        canvas.setLineWidth(1)
        canvas.circle(seal_x, seal_y, seal_size * 0.75, fill=0, stroke=1)
        
        # Seal text
        canvas.setFillColor(self.colors['primary'])
        canvas.setFont("Helvetica-Bold", self.font_sizes['micro'])
        canvas.drawCentredString(seal_x, seal_y + 8, "REPUBLIC")
        canvas.drawCentredString(seal_x, seal_y, "OF")
        canvas.drawCentredString(seal_x, seal_y - 8, "RWANDA")
        canvas.setFont("Helvetica", self.font_sizes['micro'])
        canvas.drawCentredString(seal_x, seal_y - 18, "OFFICIAL SEAL")
        
        return y_position - section_height - 15
    
    def _draw_modern_footer(self, canvas, application):
        """Draw compact modern footer"""
        footer_height = 35
        footer_y = self.margin_y
        
        # Security information
        canvas.setFillColor(self.colors['text_secondary'])
        canvas.setFont("Helvetica", self.font_sizes['micro'])
        
        security_lines = [
            f"SECURITY: Digital certificate with ID: CERT-{application.certificate_number} | VERIFY: http://localhost:3000//verify/{application.certificate_number}",
            f"LEGAL: Unauthorized reproduction prohibited | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | Rwanda Governance Board"
        ]
        
        current_y = footer_y + footer_height - 8
        for line in security_lines:
            canvas.drawCentredString(self.width / 2, current_y, line)
            current_y -= self.font_sizes['micro'] * 2
    
    def _wrap_text(self, text, max_width, font_name, font_size):
        """Enhanced text wrapping"""
        if not text:
            return [""]
        
        char_width = font_size * 0.55
        max_chars = int(max_width / char_width)
        
        if len(text) <= max_chars:
            return [text]
        
        wrapper = textwrap.TextWrapper(
            width=max_chars, 
            break_long_words=False,
            break_on_hyphens=True,
            expand_tabs=False
        )
        return wrapper.wrap(text)
    
    def create_certificate_pdf(self, application, include_qr=True, pagesize=None):
        """Generate modern certificate PDF with improved signature alignment"""
        if pagesize:
            self.__init__(pagesize)
        
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=self.pagesize)
        
        # Background and watermark
        p.setFillColor(self.colors['white'])
        p.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self._draw_watermark(p)
        
        # Modern border design
        self._draw_modern_border(p)
        
        # Layout with careful spacing
        current_y = self.height - self.margin_y - 25
        
        # Enhanced header
        current_y = self._draw_enhanced_header(p, current_y)
        
        # Certificate title card
        current_y = self._draw_certificate_title_card(p, current_y)
        
        # Certificate info card
        current_y = self._draw_info_card(p, application, current_y)
        
        # Organization details card
        current_y = self._draw_organization_card(p, application, current_y)
        
        # Authorization statement card
        current_y = self._draw_authorization_card(p, current_y)
        
        # Combined signature and verification section
        current_y = self._draw_signature_and_verification_section(p, application, current_y)
        
        # Modern footer
        self._draw_modern_footer(p, application)
        
        # Finalize PDF
        p.showPage()
        p.save()
        buffer.seek(0)
        
        return buffer


# Convenience functions
def create_modern_certificate_pdf(application, include_qr=True, pagesize=A4):
    """Create modern, well-aligned certificate PDF"""
    generator = ModernCertificateGenerator(pagesize=pagesize)
    return generator.create_certificate_pdf(application, include_qr, pagesize)


# Backward compatibility
ResponsiveCertificateGenerator = ModernCertificateGenerator
create_enhanced_certificate_pdf = create_modern_certificate_pdf