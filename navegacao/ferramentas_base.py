# -*- coding: utf-8 -*-
class FerramentaBase:
    """
    Interface base para todas as ferramentas de interação de mouse no VTK.
    Implementa o State Pattern para encapsular a lógica de cada modo de interação.
    """
    def on_mouse_press(self, event, filtro) -> bool:
        """Chamado quando um botão do mouse é pressionado."""
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        """Chamado quando o mouse se move."""
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        """Chamado quando um botão do mouse é solto."""
        return False

    def on_enter(self, filtro):
        """Chamado quando a ferramenta é ativada."""
        pass

    def on_exit(self, filtro):
        """Chamado quando a ferramenta é desativada."""
        pass
