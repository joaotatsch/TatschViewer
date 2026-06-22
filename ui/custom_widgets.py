# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class LabelImagemResponsiva(QLabel):
    """
    Subclasse de QLabel projetada especificamente para exibir o infográfico 
    de boas-vindas de maneira responsiva. 
    """
    def __init__(self, parent=None, image_path=""):
        super().__init__(parent)
        self.image_path = image_path
        self._pixmap = QPixmap(image_path)
        self.setMinimumSize(1, 1) # Permite reduzir de forma responsiva sem quebrar o layout
        self.setStyleSheet("background-color: #121212;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
    def resizeEvent(self, event):
        if not self._pixmap.isNull():
            scaled_pixmap = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        super().resizeEvent(event)
