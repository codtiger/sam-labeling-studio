from PyQt6.QtGui import QImage
from PIL import Image, ImageQt


def pil_to_qimage(pil_image):
    """Convert a PIL Image to a QImage."""
    qt_image = ImageQt.ImageQt(pil_image)
    return qt_image
